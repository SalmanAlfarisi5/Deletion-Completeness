"""Unit tests for the numeric recovery re-scorer (evaluation/recovery.py).

These functions decide whether a model's answer RECOVERED a deleted value, and
they feed the recoverability numbers reported in the paper (exp04 re-derivation,
exp07 rho tolerance sweep). A parsing or boundary bug silently shifts those
reported recovery rates.

The documented "home-loan" case comes from evaluation/judge.py (a few-shot row)
and paper/CLAIMS_LEDGER.md: ground-truth "SGD 3,200" vs answer "SGD 3,142". The
EXACT re-scorer conservatively REJECTS it (the documented false-reject), while a
>=2% tolerance band ACCEPTS it.
"""
from __future__ import annotations

import pytest

from evaluation.recovery import numeric_recovered, parse_number, value_segment


# --------------------------------------------------------------------------- #
# parse_number — comma / 'k' suffix / SGD-$ currency handling
# --------------------------------------------------------------------------- #
class TestParseNumber:
    def test_comma_thousands(self):
        assert parse_number("3,142") == 3142.0

    def test_k_suffix_750k(self):
        # documented intent (docstring: 150k -> 150000): trailing 'k' x1000
        assert parse_number("750k") == 750_000.0

    def test_k_suffix_docstring_example_150k(self):
        assert parse_number("150k") == 150_000.0

    def test_dollar_prefix_with_k(self):
        assert parse_number("$750k") == 750_000.0

    def test_sgd_prefix(self):
        assert parse_number("SGD 8,500") == 8500.0

    def test_sgd_suffix(self):
        # SGD is stripped wherever it appears (global replace), so suffix works too
        assert parse_number("3,142 SGD") == 3142.0

    def test_documented_home_loan_3142(self):
        assert parse_number("approximately SGD 3,142") == 3142.0

    def test_documented_home_loan_3200(self):
        assert parse_number("about SGD 3,200.") == 3200.0

    def test_empty_returns_none(self):
        assert parse_number("") is None

    def test_none_returns_none(self):
        assert parse_number(None) is None

    def test_no_digits_returns_none(self):
        assert parse_number("no number here") is None


# --------------------------------------------------------------------------- #
# numeric_recovered — exact (tol==0) vs relative-tolerance band boundary
# --------------------------------------------------------------------------- #
class TestNumericRecovered:
    def test_exact_match_recovered(self):
        assert numeric_recovered(["1000"], "1000", 0.0) is True

    def test_exact_off_by_one_not_recovered(self):
        assert numeric_recovered(["1000"], "1001", 0.0) is False

    def test_tolerance_just_inside_recovered(self):
        # 1099 is 9.9% off 1000 -> inside the 10% band
        assert numeric_recovered(["1000"], "1099", 0.10) is True

    def test_tolerance_at_boundary_recovered(self):
        # exactly 10% off -> boundary is inclusive (<=) -> RECOVERED
        assert numeric_recovered(["1000"], "1100", 0.10) is True

    def test_tolerance_just_outside_not_recovered(self):
        # 1101 is 10.1% off -> just OUTSIDE the 10% band
        assert numeric_recovered(["1000"], "1101", 0.10) is False

    def test_documented_homeloan_exact_rejects(self):
        # CLAIMS_LEDGER: the exact re-scorer REJECTS "SGD 3,142" for target 3,200
        assert numeric_recovered(["SGD 3,200"], "approximately SGD 3,142", 0.0) is False

    def test_documented_homeloan_tolerance_accepts(self):
        # 3,142 is ~1.8% off 3,200 -> recovered within the 5% band
        assert numeric_recovered(["SGD 3,200"], "approximately SGD 3,142", 0.05) is True

    def test_value_segment_is_applied(self):
        # numeric_recovered scores the number AFTER the last 'Value:' marker,
        # NOT the earlier 99 -> exact match on 42.
        assert value_segment("99 Value: 42").strip() == "42"
        assert numeric_recovered(["42"], "99 Value: 42", 0.0) is True

    def test_no_number_in_answer_not_recovered(self):
        assert numeric_recovered(["1000"], "I cannot determine", 0.10) is False

    def test_empty_targets_not_recovered(self):
        assert numeric_recovered([], "1000", 0.10) is False
