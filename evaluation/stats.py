"""Confidence intervals for the deletion-completeness metrics.

Two estimators, one per kind of number the experiments report:

- ``wilson_ci(k, n)`` — Wilson score interval for a PROPORTION k/n (residual-survival
  rate, completeness rate, per-bin re-derivation rate, per-tier / headline
  certifiable rate). Preferred over the normal approximation because it stays
  inside [0, 1] and is still sensible at k=0 / k=n and small n.
- ``bootstrap_mean_ci(values)`` — percentile bootstrap CI for a MEAN (e.g. mean
  collateral k). Mirrors ``probes.membership_inference.bootstrap_ci``: same RNG
  (``np.random.default_rng(seed)``), same percentile convention, same (lo, hi)
  return shape.

These only ADD credibility bounds to existing point estimates; they never change
a measurement.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import norm

import config


def wilson_ci(k: int, n: int, level: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a proportion k/n, clamped to [0, 1].

    n=0 -> (nan, nan). k=0 and k=n are handled by the score formula itself: it
    stays non-degenerate and inside [0, 1] exactly where the normal approximation
    would collapse to a zero-width interval.
    """
    if n <= 0:
        return (float("nan"), float("nan"))
    z = float(norm.ppf((1 + level) / 2))
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * np.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return (float(max(0.0, center - half)), float(min(1.0, center + half)))


def bootstrap_mean_ci(values, n_boot: int = 2000, seed: int = config.GLOBAL_SEED,
                      level: float = 0.95) -> tuple[float, float]:
    """Percentile bootstrap CI for the mean of ``values`` (resampling observations)."""
    rng = np.random.default_rng(seed)
    v = np.asarray([x for x in values if x is not None], float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return (float("nan"), float("nan"))
    means = [float(np.mean(rng.choice(v, len(v), replace=True))) for _ in range(n_boot)]
    lo, hi = (1 - level) / 2 * 100, (1 + level) / 2 * 100
    return (float(np.percentile(means, lo)), float(np.percentile(means, hi)))
