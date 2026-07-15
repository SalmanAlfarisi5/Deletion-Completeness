"""Build and persist deletion-completeness certificates from probe/planner output."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import config
from certificate.schema import DeletionCertificate

DEFAULT_THREAT_MODEL = (
    "Adversary has full read/query access to the memory store and black-box access "
    "to the base model (no training-time access). Recovery counts if any probe "
    "surfaces a ground-truth surface form of the deleted value."
)

# Recovery-judge recall = (1 - false_reject_rate). A COMPLETE certificate is only
# "complete modulo" this recall. Resolved at runtime from the latest
# data/results/judge_validation_*.json by _resolve_judge_recall(); this constant
# is the documented fallback used when no validation file is available.
DEFAULT_JUDGE_RECALL = 0.78


def _latest_judge_validation() -> dict | None:
    """Parse the most recent data/results/judge_validation_*.json (latest by mtime)."""
    try:
        files = list(config.RESULTS_DIR.glob("judge_validation_*.json"))
        if not files:
            return None
        latest = max(files, key=lambda p: p.stat().st_mtime)
        return json.loads(latest.read_text())
    except (OSError, ValueError, TypeError):
        return None


def _production_recovery_stats(data: dict) -> dict | None:
    """Locate the PRODUCTION recovery judge's validated stats inside a
    judge_validation payload. Schema: {"recovery": {<model>: {...}},
    "recovery_judge_selection": {"production": <model>}}."""
    rec = data.get("recovery")
    if not isinstance(rec, dict) or not rec:
        return None
    sel = (data.get("recovery_judge_selection") or {}).get("production")
    model = sel if sel in rec else next(iter(rec))
    stats = rec.get(model) or {}
    return {"model": model, **stats} if stats else None


def _resolve_judge_recall() -> float:
    """Recovery-judge recall = (1 - false_reject_rate) of the PRODUCTION judge, read at
    runtime from the most recent judge_validation_*.json. Falls back to the documented
    DEFAULT_JUDGE_RECALL when no validation file exists or it cannot be parsed.

    NOTE: earlier versions looked for a non-existent top-level ``recovery_judge`` key and
    so always fell back to DEFAULT_JUDGE_RECALL; the real path is
    ``recovery[<production_model>]["false_reject"]["rate"]``."""
    data = _latest_judge_validation()
    stats = _production_recovery_stats(data) if data else None
    try:
        return 1.0 - float(stats["false_reject"]["rate"])
    except (TypeError, KeyError, ValueError):
        return DEFAULT_JUDGE_RECALL


def build_reliability(*, rho_per_adversary: dict | None = None,
                      rho_n_samples: int | None = None,
                      context_lift: dict | None = None,
                      refusals: dict | None = None) -> dict:
    """Assemble the reliability block a user needs to WEIGH a verdict: the validated
    production-judge false-accept / recall, the adversary panel, and (for world-recall
    facts) per-adversary rho, sample size, context-lift, and refusal counts. Pure file
    IO -- no API calls."""
    out: dict = {}
    data = _latest_judge_validation()
    if data:
        rstats = _production_recovery_stats(data)
        if rstats:
            fa = rstats.get("false_accept", {})
            out["recovery_judge"] = rstats.get("model")
            out["recovery_judge_false_accept"] = fa.get("rate")
            out["recovery_judge_false_accept_ci95"] = fa.get("ci95")
            out["recovery_judge_recall"] = (rstats.get("recall") or {}).get("rate")
            out["recovery_judge_gold_n"] = rstats.get("n")
        esel = (data.get("entailment_judge_selection") or {}).get("production")
        if esel:
            out["entailment_judge"] = esel
            ent = (data.get("entailment") or {}).get(esel) or {}
            if "near_miss_false_fire" in ent:
                out["entailment_judge_near_miss_false_fire"] = ent["near_miss_false_fire"]
        if data.get("models"):
            out["adversary_panel"] = data["models"]
    if rho_per_adversary is not None:
        out["rho_per_adversary"] = rho_per_adversary
        out["worst_adversary"] = (max(rho_per_adversary, key=rho_per_adversary.get)
                                  if rho_per_adversary else None)
    if rho_n_samples is not None:
        out["rho_n_samples"] = rho_n_samples
    if context_lift is not None:
        out["context_lift"] = context_lift
    if refusals is not None:
        out["refusals"] = refusals
    out["caveat"] = ("COMPLETE is complete modulo the recovery judge's recall; "
                     "INCOMPLETE and aggregate figures are conservative lower bounds.")
    return out


def entailment_evidence(fact: dict, co_deleted: list[str],
                        operands_required: list[str] | None = None) -> dict:
    """Deterministically derive the co-deletion PROOF TRACE from the fact's boolean
    entailment DAG (planner/entailment_dag) -- no API, no live probe. Answers 'why was
    each co-deletion necessary' and 'what was spared' straight from the ground-truth
    formula, so the certificate carries an auditable justification, not just a verdict.

    Returns a dict with keys: entailment_structure, co_deletion_justifications,
    operands_spared, minimality. Empty/degenerate for facts with no operands."""
    from planner.entailment_dag import (dag_of, min_codelete_size, min_hitting_sets,
                                         is_hitting_set, leaf_labels)
    dag = dag_of(fact)
    leaves, formula = dag["leaves"], dag["formula"]
    if not leaves:                       # isolated / no re-derivation structure
        return {"entailment_structure": None, "co_deletion_justifications": [],
                "operands_spared": [], "minimality": None}
    id_to_label = {cid: lbl for lbl, cid in leaves.items()}
    k_star = min_codelete_size(formula)
    topology = (fact.get("entailment_dag") or {}).get("topology", "flat")
    structure = {
        "topology": topology,
        "formula": formula,
        "leaves": leaves,
        "k_star": k_star,
        "min_hitting_sets_ids": [sorted(leaves[l] for l in hs)
                                 for hs in min_hitting_sets(formula)],
    }
    chosen = {id_to_label[c] for c in co_deleted if c in id_to_label}
    justifications = []
    for cid in co_deleted:
        lbl = id_to_label.get(cid)
        if lbl is None:
            justifications.append({
                "fact_id": cid, "on_rederivation_path": False,
                "explanation": ("removed as a residual copy of the target value, "
                                "not an entailment operand")})
            continue
        necessary = not is_hitting_set(formula, chosen - {lbl})
        justifications.append({
            "fact_id": cid, "label": lbl, "on_rederivation_path": True,
            "necessary_for_plan": necessary,
            "explanation": (
                f"operand '{lbl}' lies on a re-derivation path; with it kept, the "
                f"entailment formula is still satisfiable, so the target re-derives -- "
                f"its deletion is required to close the channel"
                if necessary else
                f"operand '{lbl}' entails the target, but the other co-deletions already "
                f"close every re-derivation path, so it is redundant within this set")})
    req = set(operands_required) if operands_required else set(leaves.values())
    spared = [{"fact_id": cid, "label": id_to_label[cid],
               "reason": ("entails the target but is redundant given the chosen minimum "
                          "hitting set; sparing it keeps collateral minimal (no over-deletion)")}
              for cid in sorted(req) if cid not in co_deleted and cid in id_to_label]
    k = len(co_deleted)
    minimality = {"collateral_k": k, "k_star": k_star, "gap": k - k_star,
                  "is_minimum": k == k_star}
    return {"entailment_structure": structure, "co_deletion_justifications": justifications,
            "operands_spared": spared, "minimality": minimality}


def make_certificate(*, fact: dict, system: str, residual: float, rederivation: float,
                     rho: float, probe_scores: dict | None = None,
                     heuristic: str = "none", artifacts_purged: list | None = None,
                     facts_co_deleted: list | None = None,
                     final_recoverability: float | None = None,
                     threat_model: str | None = None,
                     probe_battery: list | None = None, tau: float | None = None,
                     judge_recall: float | None = None,
                     system_version: str = "mem0ai-2.0.7",
                     operands_required: list | None = None,
                     probe_trace: list | None = None,
                     reliability: dict | None = None,
                     rho_per_adversary: dict | None = None,
                     rho_n_samples: int | None = None,
                     evidence: bool = True) -> DeletionCertificate:
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

    # Auditable proof trace (deterministic, no API): the co-deletion justification is
    # derived from the fact's known entailment DAG, so the certificate records WHY each
    # co-deletion was necessary and what was spared -- not just the verdict.
    ev = (entailment_evidence(fact, facts_co_deleted or [], operands_required)
          if evidence else {"entailment_structure": None,
                            "co_deletion_justifications": [], "operands_spared": [],
                            "minimality": None})
    rel = reliability if reliability is not None else build_reliability(
        rho_per_adversary=rho_per_adversary, rho_n_samples=rho_n_samples)

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
        judge_recall=_resolve_judge_recall() if judge_recall is None else judge_recall,
        entailment_structure=ev["entailment_structure"],
        co_deletion_justifications=ev["co_deletion_justifications"],
        operands_spared=ev["operands_spared"], minimality=ev["minimality"],
        probe_trace=probe_trace or [], reliability=rel,
    )


def save_certificate(cert: DeletionCertificate, results_dir: Path | None = None) -> Path:
    d = (results_dir or config.RESULTS_DIR) / "certificates"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{cert.certificate_id}.json"
    path.write_text(cert.model_dump_json(indent=2))
    return path
