"""Build and persist deletion-completeness certificates from probe/planner output."""
from __future__ import annotations

import uuid
from pathlib import Path

import config
from certificate.schema import DeletionCertificate

DEFAULT_THREAT_MODEL = (
    "Adversary has full read/query access to the memory store and black-box access "
    "to the base model (no training-time access). Recovery counts if any probe "
    "surfaces a ground-truth surface form of the deleted value."
)

# Recovery-judge recall from evaluation/judge.py (1 - false_reject_rate). A
# COMPLETE certificate is only "complete modulo" this recall.
DEFAULT_JUDGE_RECALL = 0.78


def make_certificate(*, fact: dict, system: str, residual: float, rederivation: float,
                     rho: float, probe_scores: dict | None = None,
                     heuristic: str = "none", artifacts_purged: list | None = None,
                     facts_co_deleted: list | None = None,
                     final_recoverability: float | None = None,
                     threat_model: str | None = None,
                     probe_battery: list | None = None, tau: float | None = None,
                     judge_recall: float | None = None,
                     system_version: str = "mem0ai-2.0.7") -> DeletionCertificate:
    tau = config.TAU if tau is None else tau
    final = (final_recoverability if final_recoverability is not None
             else max(residual, rederivation, rho))
    # floor-reaching: the deletable channels are closed (Def. 5). Erasure is
    # certified only if additionally the (worst-adversary) floor rho < tau.
    floor_reaching = max(residual, rederivation) < tau
    certified = final < tau
    if certified:
        status = "COMPLETE"
    elif final < 0.5:
        status = "PARTIAL"
    else:
        status = "INCOMPLETE"
    return DeletionCertificate(
        certificate_id=f"cert-{fact['id']}-{uuid.uuid4().hex[:6]}",
        fact_id=fact["id"], fact_text=fact["text"], system=system,
        system_version=system_version,
        threat_model=threat_model or DEFAULT_THREAT_MODEL,
        probe_battery=probe_battery or [],
        status=status, residual_survival_score=residual,
        re_derivation_score=rederivation, parametric_risk_rho=rho,
        probe_scores=probe_scores or {}, heuristic_used=heuristic,
        artifacts_purged=artifacts_purged or [],
        facts_co_deleted=facts_co_deleted or [],
        collateral_k=len(facts_co_deleted or []),
        final_recoverability=final, floor_reaching=floor_reaching,
        completeness_certified=certified,
        judge_recall=DEFAULT_JUDGE_RECALL if judge_recall is None else judge_recall,
    )


def save_certificate(cert: DeletionCertificate, results_dir: Path | None = None) -> Path:
    d = (results_dir or config.RESULTS_DIR) / "certificates"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{cert.certificate_id}.json"
    path.write_text(cert.model_dump_json(indent=2))
    return path
