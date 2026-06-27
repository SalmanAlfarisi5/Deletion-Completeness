"""Unit tests for make_certificate status boundaries (certificate/emitter.py).

COMPLETE / PARTIAL / INCOMPLETE is the headline certificate verdict. Boundary
semantics, as implemented:

    final < tau          -> COMPLETE     (strict; final == tau is NOT complete)
    tau <= final < 0.5   -> PARTIAL
    final >= 0.5         -> INCOMPLETE   (0.5 itself is INCOMPLETE)

`final` is driven exactly via final_recoverability and tau is set explicitly, so
the thresholds are exercised at their literal boundary values.

NOTE: a concurrent change touches how this file sources `judge_recall` (a
constant), NOT the status logic. These tests assert only status /
completeness_certified / floor_reaching / final_recoverability and never depend
on judge_recall.
"""
from __future__ import annotations

import pytest

import config
from certificate.emitter import make_certificate

FACT = {"id": "f-test", "text": "test fact"}
EPS = 1e-9


def _make(final=None, tau=None, residual=0.0, rederivation=0.0, rho=0.0):
    return make_certificate(
        fact=FACT, system="mem0",
        residual=residual, rederivation=rederivation, rho=rho,
        final_recoverability=final, tau=tau,
    )


@pytest.mark.parametrize("final,expected", [
    (0.0, "COMPLETE"),
    (0.05, "COMPLETE"),
    (0.10 - EPS, "COMPLETE"),    # just below tau
    (0.10, "PARTIAL"),           # exactly tau -> strict '<' means NOT complete
    (0.10 + EPS, "PARTIAL"),     # just above tau
    (0.30, "PARTIAL"),
    (0.5 - EPS, "PARTIAL"),      # just below 0.5
    (0.5, "INCOMPLETE"),         # exactly 0.5 -> INCOMPLETE
    (0.5 + EPS, "INCOMPLETE"),   # just above 0.5
    (1.0, "INCOMPLETE"),
])
def test_status_boundaries(final, expected):
    cert = _make(final=final, tau=0.10)
    assert cert.status == expected
    assert cert.completeness_certified is (expected == "COMPLETE")
    assert cert.final_recoverability == pytest.approx(final)


def test_tau_defaults_to_config_tau():
    # tau omitted -> uses config.TAU for the COMPLETE boundary
    assert _make(final=config.TAU - EPS).status == "COMPLETE"
    assert _make(final=config.TAU).status == "PARTIAL"


def test_final_defaults_to_max_channel():
    # final_recoverability omitted -> final = max(residual, rederivation, rho)
    cert = _make(residual=0.6, rederivation=0.2, rho=0.1, tau=0.10)
    assert cert.final_recoverability == pytest.approx(0.6)
    assert cert.status == "INCOMPLETE"


def test_floor_reaching_but_not_certified():
    # R11 limit case: deletable channels closed (max(residual, rederivation) < tau)
    # but the parametric floor rho keeps final >= tau -> floor_reaching yet NOT
    # erasure-certified, status PARTIAL.
    cert = _make(residual=0.05, rederivation=0.05, rho=0.30, tau=0.10)
    assert cert.floor_reaching is True
    assert cert.completeness_certified is False
    assert cert.status == "PARTIAL"
