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
    judge_recall: float | None = None           # recovery-judge recall (sensitivity)
    # floor_reaching: deletable channels closed (residual=re-derivation<tau), i.e. as
    # erased as deletion can make it. completeness_certified additionally requires the
    # (irreducible, worst-adversary) parametric floor rho<tau. floor_reaching && !certified
    # is the limit result (e.g. R11): forgotten from the store, still world-inferable.
    floor_reaching: bool = False
    completeness_certified: bool = False

    # ---- Audit evidence (proof traces) -------------------------------------
    # These make the certificate auditable rather than a bare verdict:
    #   entailment_structure  -- the boolean re-derivation formula, its leaves, and the
    #                            deletion-propagation optimum k* (the ground-truth reason
    #                            the co-deletion set is what it is).
    #   co_deletion_justifications -- per co-deleted fact, WHY it was removed: it lies on
    #                            a re-derivation path, and whether dropping it from the
    #                            plan would re-open the channel (its necessity).
    #   operands_spared       -- entailers deliberately NOT deleted (minimality evidence:
    #                            proof the planner did not over-delete).
    #   minimality            -- collateral k vs optimum k* (gap, is_minimum).
    #   probe_trace           -- per-channel evidence (probe, score, supporting detail).
    #   reliability           -- what lets a user weigh the verdict: validated judge
    #                            false-accept / recall, adversary panel, per-adversary
    #                            world recall, sample sizes.
    entailment_structure: dict | None = None
    co_deletion_justifications: list[dict] = Field(default_factory=list)
    operands_spared: list[dict] = Field(default_factory=list)
    minimality: dict | None = None
    probe_trace: list[dict] = Field(default_factory=list)
    reliability: dict = Field(default_factory=dict)

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
            f"  Floor-reaching : {'YES' if self.floor_reaching else 'NO'}  "
            f"(deletable channels closed)",
            f"  Erasure-certified : {'YES' if self.completeness_certified else 'NO'}  "
            f"(also rho<tau, worst adversary)",
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
        ]
        if self.minimality:
            m = self.minimality
            lines.append(f"    collateral vs optimum : k={m.get('collateral_k')} "
                         f"vs k*={m.get('k_star')} (gap {m.get('gap')}; "
                         f"{'MINIMUM' if m.get('is_minimum') else 'above optimum'})")
        if self.co_deletion_justifications:
            lines.append("-" * 64)
            lines.append("  Why each co-deletion was necessary")
            for j in self.co_deletion_justifications:
                tag = ("necessary" if j.get("necessary_for_plan")
                       else "redundant-in-set" if j.get("on_rederivation_path")
                       else "residual-copy")
                lines.append(f"    - {j.get('fact_id')} [{tag}]: {j.get('explanation','')}")
        if self.operands_spared:
            lines.append("  Entailers spared (minimality)")
            for s in self.operands_spared:
                lines.append(f"    - {s.get('fact_id')}: {s.get('reason','')}")
        lines += [
            "-" * 64,
            f"  Threat model   : {self.threat_model}",
            f"  Probes run     : {', '.join(self.probe_battery)}",
        ]
        if self.reliability:
            r = self.reliability
            if r.get("recovery_judge_false_accept") is not None:
                lines.append(f"  Recovery judge : {r.get('recovery_judge')} "
                             f"(false-accept {r.get('recovery_judge_false_accept')}, "
                             f"recall {r.get('recovery_judge_recall')})")
            if r.get("rho_per_adversary"):
                lines.append(f"  World recall by adversary: {r.get('rho_per_adversary')}")
        if self.human_judge_agreement is not None:
            lines.append(f"  Judge kappa    : {self.human_judge_agreement:.3f}")
        if self.completeness_certified and self.judge_recall is not None:
            lines.append(f"  CAVEAT         : COMPLETE is modulo recovery-judge recall "
                         f"~{self.judge_recall:.0%}; a missed recovery is possible.")
        lines.append("=" * 64)
        return "\n".join(lines)
