"""Aggregate metrics for deletion-completeness experiments."""
from __future__ import annotations

import numpy as np


def recoverability(residual: float, rederivation: float, rho: float) -> float:
    """Overall recoverability = worst-case across recovery channels."""
    return max(residual, rederivation, rho)


def mean(values) -> float:
    xs = [v for v in values if v is not None]
    return float(np.mean(xs)) if xs else float("nan")


def rate(scores, threshold: float = 0.5) -> float:
    """Fraction of scores at/above a recoverability threshold."""
    xs = [s for s in scores if s is not None]
    return float(np.mean([s >= threshold for s in xs])) if xs else float("nan")


def cohens_kappa(a: list[int], b: list[int]) -> float:
    """Cohen's kappa between two binary label sequences (e.g., judge vs oracle)."""
    a, b = np.asarray(a), np.asarray(b)
    if len(a) == 0:
        return float("nan")
    po = float(np.mean(a == b))
    pa1, pb1 = a.mean(), b.mean()
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    return float((po - pe) / (1 - pe)) if pe != 1 else 1.0
