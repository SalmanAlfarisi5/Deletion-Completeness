"""Membership-inference probe (retrieval-score, never-stored prior).

Per fact we take ONE continuous retrieval score: the top-1 similarity of the
fact's exact-text query against the (post-deletion) store. MEMBERS are the real
facts (stored, then deleted); CONTROLS are matched never-stored near-twins (same
template, different value). The test: do member scores stochastically exceed
twin scores?

AUC = P(member score > twin score) = Mann-Whitney U / (n_m * n_t), computed from
the CONTINUOUS scores (no thresholding — that would destroy the rank info).
Reported with a bootstrap 95% CI (resampling facts) and a label-permutation
p-value, so a small effect near 0.5 is not over-claimed.
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


def bootstrap_ci(member: list[float], twin: list[float], n_boot: int = 1000,
                 seed: int = 42, level: float = 0.95) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    m, t = np.asarray(member, float), np.asarray(twin, float)
    aucs = [auc(rng.choice(m, len(m), replace=True), rng.choice(t, len(t), replace=True))
            for _ in range(n_boot)]
    lo, hi = (1 - level) / 2 * 100, (1 + level) / 2 * 100
    return float(np.percentile(aucs, lo)), float(np.percentile(aucs, hi))


def permutation_p(member: list[float], twin: list[float], n_perm: int = 1000,
                  seed: int = 42) -> float:
    """One-sided p: P(permuted AUC >= observed) under the null (labels exchangeable)."""
    rng = np.random.default_rng(seed)
    m, t = np.asarray(member, float), np.asarray(twin, float)
    obs = auc(m, t)
    pooled = np.concatenate([m, t])
    n = len(m)
    ge = 0
    for _ in range(n_perm):
        perm = rng.permutation(pooled)
        ge += int(auc(perm[:n], perm[n:]) >= obs)
    return (ge + 1) / (n_perm + 1)


def membership_auc(member: list[float], twin: list[float], n_boot: int = 1000,
                   n_perm: int = 1000, seed: int = 42) -> dict:
    a = auc(member, twin)
    lo, hi = bootstrap_ci(member, twin, n_boot, seed)
    return {"auc": round(a, 3), "ci95": [round(lo, 3), round(hi, 3)],
            "p_perm": round(permutation_p(member, twin, n_perm, seed), 4),
            "n_member": len(member), "n_twin": len(twin),
            "mean_member": round(float(np.mean(member)), 3) if member else float("nan"),
            "mean_twin": round(float(np.mean(twin)), 3) if twin else float("nan"),
            "ci_includes_half": bool(lo <= 0.5 <= hi)}
