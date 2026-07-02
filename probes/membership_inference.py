"""Membership-inference probe (retrieval-score, never-stored prior).

Per fact we take ONE continuous retrieval score: the top-1 similarity of the
fact's exact-text query against the (post-deletion) store. MEMBERS are the real
facts (stored, then deleted); CONTROLS are matched never-stored near-twins (same
template, different value). The test: do member scores stochastically exceed
twin scores?

AUC = P(member score > twin score) = Mann-Whitney U / (n_m * n_t), computed from
the CONTINUOUS scores (no thresholding — that would destroy the rank info).
The design is MATCHED/CLUSTERED — each member fact owns its own near-twins — so the
reported bootstrap 95% CI resamples FACTS (clusters), and the label-permutation
p-value relabels member-vs-twin WITHIN each fact, not over the pooled scores; a
small effect near 0.5 is thus judged on fact-level (not pseudo-replicated) variability.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import rankdata


def top1_scores(adapter, user_id: str, queries: list[str]) -> list[float]:
    """Top-1 retrieval similarity for each query (0.0 if nothing retrieved)."""
    out = []
    for q in queries:
        res = adapter.query(user_id, q, top_k=1, threshold=0.0)
        mems = res.get("results", []) if isinstance(res, dict) else (res or [])
        out.append(float(mems[0]["score"]) if mems and mems[0].get("score") is not None else 0.0)
    return out


def auc(member: list[float], twin: list[float]) -> float:
    """AUC = P(member > twin) via the Mann-Whitney U statistic on continuous scores."""
    m, t = np.asarray(member, float), np.asarray(twin, float)
    if len(m) == 0 or len(t) == 0:
        return float("nan")
    r = rankdata(np.concatenate([m, t]))
    u = r[:len(m)].sum() - len(m) * (len(m) + 1) / 2.0
    return float(u / (len(m) * len(t)))


def _twin_blocks(member: list[float], twin: list[float],
                 twins_per_member: int | None = None):
    """Group the flat twin scores into one matched block per member fact.

    The MIA is a MATCHED/CLUSTERED design: member fact ``i`` owns the twins
    ``twin[i*k:(i+1)*k]`` (``k`` = ``twins_per_member``), all sharing its template.
    Resampling/permuting the pooled scores iid would be pseudo-replication (CI too
    narrow, permutation p mis-calibrated), so the UNIT must be the fact/cluster; the
    twins are reshaped into ``(n_member, k)`` blocks here. ``k`` is recovered from
    ``len(twin)//len(member)`` when not supplied (``llm.value_twins`` emits exactly
    k twins per member, so the array is balanced and evenly blocked).
    """
    m = np.asarray(member, float)
    t = np.asarray(twin, float)
    n_m = len(m)
    if twins_per_member is None:
        twins_per_member = (len(t) // n_m) if n_m else 0
    k = int(twins_per_member)
    t_mat = (t[:n_m * k].reshape(n_m, k) if n_m and k > 0
             else np.empty((n_m, max(k, 0)), float))
    return m, t_mat, n_m, k


def bootstrap_ci(member: list[float], twin: list[float], n_boot: int = 1000,
                 seed: int = 42, level: float = 0.95,
                 twins_per_member: int | None = None) -> tuple[float, float]:
    """Percentile bootstrap CI for the AUC, resampling FACTS (clusters) with
    replacement: each resampled fact contributes its member score AND its own matched
    twins as one block, so the matched design is respected. Resampling members/twins
    iid & separately treats the k twins as independent controls and breaks the
    member-twin matching -> a mis-calibrated CI (pseudo-replication)."""
    rng = np.random.default_rng(seed)
    m, t_mat, n_m, k = _twin_blocks(member, twin, twins_per_member)
    if n_m == 0 or k == 0:
        return float("nan"), float("nan")
    aucs = []
    for _ in range(n_boot):
        idx = rng.integers(0, n_m, size=n_m)              # resample FACT indices
        aucs.append(auc(m[idx], t_mat[idx].ravel()))      # member + its OWN twins block
    lo, hi = (1 - level) / 2 * 100, (1 + level) / 2 * 100
    return float(np.percentile(aucs, lo)), float(np.percentile(aucs, hi))


def permutation_p(member: list[float], twin: list[float], n_perm: int = 1000,
                  seed: int = 42, twins_per_member: int | None = None) -> float:
    """One-sided p: P(permuted AUC >= observed) under the MATCHED null.

    Exchangeability holds WITHIN a fact (cluster), not over the pooled scores: each
    permutation relabels, per fact, which of the {member} + k twins is the 'member'
    (the rest become twins). This respects the matched design instead of treating all
    scores as pooled-exchangeable (which would mis-calibrate the p-value)."""
    rng = np.random.default_rng(seed)
    m, t_mat, n_m, k = _twin_blocks(member, twin, twins_per_member)
    if n_m == 0 or k == 0:
        return 1.0
    obs = auc(member, twin)
    cluster = np.column_stack([m, t_mat])                 # (n_m, k+1): col0 member, 1..k twins
    rows = np.arange(n_m)
    ge = 0
    for _ in range(n_perm):
        pick = rng.integers(0, k + 1, size=n_m)           # per fact: which score is 'member'
        perm_member = cluster[rows, pick]
        mask = np.ones(cluster.shape, dtype=bool)
        mask[rows, pick] = False
        perm_twin = cluster[mask]                         # remaining k per fact -> twins
        ge += int(auc(perm_member, perm_twin) >= obs)
    return (ge + 1) / (n_perm + 1)


def membership_auc(member: list[float], twin: list[float], n_boot: int = 1000,
                   n_perm: int = 1000, seed: int = 42,
                   twins_per_member: int | None = None) -> dict:
    # Matched/clustered MIA: each member fact owns twins_per_member near-twins that
    # share its template (recovered as len(twin)//len(member) when not given). The
    # bootstrap CI and permutation p resample/relabel at the FACT (cluster) level, not
    # iid over pooled scores, so both reflect fact-level (not pseudo-replicated) variability.
    a = auc(member, twin)
    k = twins_per_member if twins_per_member is not None else (
        (len(twin) // len(member)) if member else 0)
    lo, hi = bootstrap_ci(member, twin, n_boot, seed, twins_per_member=k)
    return {"auc": round(a, 3), "ci95": [round(lo, 3), round(hi, 3)],
            "p_perm": round(permutation_p(member, twin, n_perm, seed,
                                          twins_per_member=k), 4),
            "n_member": len(member), "n_twin": len(twin),
            "mean_member": round(float(np.mean(member)), 3) if member else float("nan"),
            "mean_twin": round(float(np.mean(twin)), 3) if twin else float("nan"),
            "ci_includes_half": bool(lo <= 0.5 <= hi)}
