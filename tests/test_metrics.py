"""Unit tests for cohens_kappa (evaluation/metrics.py).

Cohen's kappa is the human-vs-judge agreement reported on the certificate
(human_judge_agreement) and in the paper. The load-bearing contract: on a
CONSTANT rater (all labels identical) chance-agreement variance vanishes
(pe == 1) and kappa is UNDEFINED -> it must be NaN, NEVER 1.0. Reporting 1.0
would advertise a degenerate annotation as perfect agreement.
"""
from __future__ import annotations

import math

import pytest

from evaluation.metrics import cohens_kappa


def test_constant_rater_all_ones_is_nan():
    # THE contract: constant rater -> NaN, not 1.0
    assert math.isnan(cohens_kappa([1, 1, 1, 1], [1, 1, 1, 1]))


def test_constant_rater_all_zeros_is_nan():
    assert math.isnan(cohens_kappa([0, 0, 0, 0], [0, 0, 0, 0]))


def test_perfect_agreement_with_variance_is_one():
    # perfect agreement but NOT constant -> well-defined kappa == 1.0
    assert cohens_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == pytest.approx(1.0)


def test_known_partial_value():
    # hand-computed: po=4/6, pe=0.5 -> kappa = (4/6 - 1/2)/(1 - 1/2) = 1/3
    assert cohens_kappa([1, 1, 0, 0, 1, 0], [1, 0, 0, 0, 1, 1]) == pytest.approx(1 / 3)


def test_matches_sklearn_on_nondegenerate():
    from sklearn.metrics import cohen_kappa_score

    a = [1, 1, 0, 0, 1, 0, 1, 0, 0, 1]
    b = [1, 0, 0, 0, 1, 1, 1, 0, 1, 1]
    assert cohens_kappa(a, b) == pytest.approx(cohen_kappa_score(a, b))


def test_empty_is_nan():
    assert math.isnan(cohens_kappa([], []))
