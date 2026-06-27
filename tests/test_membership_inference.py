"""Unit tests for auc (probes/membership_inference.py).

auc = P(member score > twin score), computed from the Mann-Whitney U statistic
with average-rank tie handling. It is the headline membership-inference number
reported with a bootstrap CI. Contract: it must equal sklearn's
roc_auc_score (which scores ties at 0.5) to within 1e-6, otherwise the reported
membership AUC is wrong.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from probes.membership_inference import auc


def _sklearn_auc(member, twin) -> float:
    y = [1] * len(member) + [0] * len(twin)
    scores = np.concatenate([np.asarray(member, float), np.asarray(twin, float)])
    return float(roc_auc_score(y, scores))


@pytest.mark.parametrize("seed", [0, 7, 123])
def test_matches_sklearn_random_continuous(seed):
    rng = np.random.default_rng(seed)
    member = rng.normal(0.5, 1.0, size=40)
    twin = rng.normal(0.0, 1.0, size=55)
    assert abs(auc(member, twin) - _sklearn_auc(member, twin)) < 1e-6


def test_matches_sklearn_with_ties():
    # overlapping integer scores -> ties; rank-based AUC must score ties at 0.5
    member = [1.0, 2.0, 3.0]
    twin = [2.0, 2.0, 4.0]
    assert auc(member, twin) == pytest.approx(1 / 3)
    assert abs(auc(member, twin) - _sklearn_auc(member, twin)) < 1e-6


def test_empty_member_is_nan():
    assert math.isnan(auc([], [1.0, 2.0]))


def test_empty_twin_is_nan():
    assert math.isnan(auc([1.0, 2.0], []))
