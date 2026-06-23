"""Pydantic schema for the deletion-completeness certificate."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DeletionCertificate(BaseModel):
    # ---- Identity ----------------------------------------------------------
    certificate_id: str
    issued_at: datetime = Field(default_factory=_utcnow)
    fact_id: str
    fact_text: str           # REDACTED in production; kept for research
    system: str              # "mem0" | "zep" | "letta"
    system_version: str = "unknown"

    # ---- Threat model ------------------------------------------------------
    threat_model: str
    probe_battery: list[str] = Field(default_factory=list)

    # ---- Results -----------------------------------------------------------
    status: str              # "COMPLETE" | "INCOMPLETE" | "PARTIAL"
    residual_survival_score: float   # 0 = none survived, 1 = fully survived
    re_derivation_score: float       # 0 = not entailed, 1 = fully entailed
    parametric_risk_rho: float       # base-model floor
    probe_scores: dict[str, float] = Field(default_factory=dict)

    # ---- Planner output ----------------------------------------------------
    heuristic_used: str = "none"
    artifacts_purged: list[str] = Field(default_factory=list)
    facts_co_deleted: list[str] = Field(default_factory=list)
    collateral_k: int = 0
    final_recoverability: float = 0.0

    # ---- Validation --------------------------------------------------------
    human_judge_agreement: float | None = None  # Cohen's kappa, if computed
    completeness_certified: bool = False

    def to_text(self) -> str:
        """Human-readable certificate."""
        lines = [
            "=" * 64,
            "  DELETION-COMPLETENESS CERTIFICATE",
            "=" * 64,
            f"  Certificate ID : {self.certificate_id}",
            f"  Issued at      : {self.issued_at.isoformat()}",
            f"  System         : {self.system} (v{self.system_version})",
            f"  Fact           : [{self.fact_id}] {self.fact_text}",
            "-" * 64,
            f"  STATUS         : {self.status}",
            f"  Certified      : {'YES' if self.completeness_certified else 'NO'}",
            "-" * 64,
            "  Recoverability decomposition",
            f"    residual survival   : {self.residual_survival_score:.3f}",
            f"    re-derivation       : {self.re_derivation_score:.3f}",
            f"    parametric risk (rho): {self.parametric_risk_rho:.3f}",
            f"    final recoverability : {self.final_recoverability:.3f}",
            "-" * 64,
            "  Planner",
            f"    heuristic         : {self.heuristic_used}",
            f"    artifacts purged  : {len(self.artifacts_purged)}",
            f"    collateral facts k: {self.collateral_k} {self.facts_co_deleted}",
            "-" * 64,
            f"  Threat model   : {self.threat_model}",
            f"  Probes run     : {', '.join(self.probe_battery)}",
        ]
        if self.human_judge_agreement is not None:
            lines.append(f"  Judge kappa    : {self.human_judge_agreement:.3f}")
        lines.append("=" * 64)
        return "\n".join(lines)
