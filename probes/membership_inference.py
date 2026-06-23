"""Membership-inference probe (retrieval-score, never-stored prior).

Operationalizes the never-stored prior directly: for the deleted fact's queries,
compare the retrieval-score distribution against a MEMBER store (corpus + the
fact, then deleted) vs a matched CONTROL store (the same corpus, fact NEVER
inserted). If deletion is complete, the two are indistinguishable (AUC ~ 0.5);
a residual trace makes member scores stochastically larger (AUC -> 1).

Reported: Mann-Whitney U one-sided (member > control), AUC = U/(n_m*n_c) (the
effect size = P(member score > control score)), and the score means.

Note: embedding retrieval is insensitive to the exact value token (a phone
number vs another phone number embed alike), so this probe detects TOPIC/record-
level residual presence; exact_match remains the value-level probe.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import mannwhitneyu


def collect_scores(adapter, user_id: str, queries: list[str], top_k: int = 5) -> list[float]:
    scores: list[float] = []
    for q in queries:
        res = adapter.query(user_id, q, top_k=top_k, threshold=0.0)
        mems = res.get("results", []) if isinstance(res, dict) else (res or [])
        scores += [m["score"] for m in mems[:top_k] if m.get("score") is not None]
    return scores


def membership_test(adapter, member_uid: str, control_uid: str,
                    queries: list[str], top_k: int = 5) -> dict:
    sM = collect_scores(adapter, member_uid, queries, top_k)
    sC = collect_scores(adapter, control_uid, queries, top_k)
    out = {"n_member": len(sM), "n_control": len(sC),
           "mean_member": float(np.mean(sM)) if sM else float("nan"),
           "mean_control": float(np.mean(sC)) if sC else float("nan")}
    if len(sM) < 2 or len(sC) < 2:
        out.update(auc=float("nan"), p_value=float("nan"))
        return out
    U, p = mannwhitneyu(sM, sC, alternative="greater")
    out.update(auc=float(U / (len(sM) * len(sC))), p_value=float(p))
    return out
