"""Greedy heuristics for minimal co-deletion (the Opt-P2E2 problem).

All heuristics operate on a LIVE system: they delete records and re-probe to
measure recoverability. They return a PlanResult. `heuristic_threshold` is the
recommended default (purge own artifacts, then co-delete entailing facts in
confidence order, re-probing after each).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import config


@dataclass
class PlanResult:
    heuristic: str
    facts_co_deleted: list[str] = field(default_factory=list)
    artifacts_purged: list[str] = field(default_factory=list)
    residual_recoverability: float = 0.0   # the max over channels (overall recoverability)
    final_residual: float = 0.0            # residual-survival channel, post-plan
    final_rederivation: float = 0.0        # re-derivation channel, post-plan
    parametric_risk: float = 0.0
    collateral_k: int = 0
    achieved_completeness: bool = False
    recovery_paths_remaining: list = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)


class GreedyPlanner:
    def __init__(self, adapter, deleter, exact_probe, param_probe,
                 entailment_detector, threshold_tau: float | None = None):
        self.adapter = adapter
        self.deleter = deleter
        self.exact = exact_probe
        self.param = param_probe
        self.entail = entailment_detector
        self.tau = config.TAU if threshold_tau is None else threshold_tau

    # -- recoverability of a target given the current live store ------------
    def _recoverability(self, user_id: str, fact: dict) -> tuple[float, float, float]:
        residual = self.exact.run(self.adapter, user_id, fact).score
        rederiv = self.param.run_rederivation(self.adapter, user_id, fact).score
        rho = self.param.run_parametric(fact).score
        return residual, rederiv, rho

    def _purge_value_artifacts(self, user_id: str, fact: dict,
                               exclude: set[str]) -> list[str]:
        """Delete every surviving row containing the target's OWN value.

        Uses the narrow `delete_value` (not the broad recovery `probe_value`) so
        residual-cleanup does not accidentally remove entailing operands — those
        are stage-3's job to co-delete.
        """
        from probes.base_probe import normalize_values
        values = [v.lower() for v in
                  normalize_values(fact.get("delete_value", fact.get("probe_value")))]
        purged = []
        for m in self.adapter.list_memories(user_id):
            if m.get("id") in exclude:
                continue
            text = self.adapter.memory_text(m).lower()
            if any(v in text for v in values):
                self.adapter.delete_memory(user_id, m["id"])
                purged.append(m["id"])
        return purged

    def heuristic_threshold(self, user_id: str, target_fact: dict,
                            candidates: list[dict], inj_map: dict) -> PlanResult:
        """Stage 1 probe -> Stage 2 purge own artifacts -> Stage 3 co-delete
        entailing facts (highest confidence first), re-probing after each."""
        pr = PlanResult(heuristic="threshold")
        own_ids = set(inj_map.get(target_fact["id"], {}).get("memory_ids", []))

        # Stage 1
        residual, rederiv, rho = self._recoverability(user_id, target_fact)
        pr.trace.append({"stage": "probe", "residual": residual,
                         "rederiv": rederiv, "rho": rho})
        pr.parametric_risk = rho
        if max(residual, rederiv) < self.tau:
            return self._finalize(pr, user_id, target_fact)

        # Stage 2: delete the target's own records + any artifact carrying the value
        self.deleter.delete_records(user_id, list(own_ids))
        pr.artifacts_purged = list(own_ids) + self._purge_value_artifacts(
            user_id, target_fact, exclude=own_ids)
        residual, rederiv, rho = self._recoverability(user_id, target_fact)
        pr.trace.append({"stage": "purge_artifacts", "residual": residual,
                         "rederiv": rederiv})
        if max(residual, rederiv) < self.tau:
            return self._finalize(pr, user_id, target_fact)

        # Stage 3: rank candidates by entailment confidence, co-delete greedily
        ranked = sorted(
            candidates,
            key=lambda c: self.entail.check(c["text"], target_fact["text"]),
            reverse=True,
        )
        for c in ranked:
            conf = self.entail.check(c["text"], target_fact["text"])
            if conf <= self.tau:
                break
            ids = inj_map.get(c["id"], {}).get("memory_ids", [])
            self.deleter.delete_records(user_id, ids)
            pr.facts_co_deleted.append(c["id"])
            residual, rederiv, rho = self._recoverability(user_id, target_fact)
            pr.trace.append({"stage": "co_delete", "fact": c["id"],
                             "conf": conf, "rederiv": rederiv})
            if max(residual, rederiv) < self.tau:
                break

        return self._finalize(pr, user_id, target_fact)

    def heuristic_depth_first(self, user_id: str, target_fact: dict,
                              candidates: list[dict], inj_map: dict) -> PlanResult:
        """Most aggressive: delete the target's records and every candidate that
        entails it above tau, in one shot (max collateral, min probing cost)."""
        pr = PlanResult(heuristic="depth_first")
        # LIMITATION (deliberately-naive comparator, do not "fix"): this deletes
        # ONLY the inj_map memory_ids for the target and each co-deleted candidate.
        # Unlike heuristic_threshold it runs NO Stage-2 own-artifact/value purge, so
        # any surviving row carrying the target's value but not tracked in inj_map is
        # left behind. It is therefore NOT coverage-equivalent to heuristic_threshold
        # under infer=True; kept as-is on purpose as the aggressive baseline.
        self.deleter.delete_records(
            user_id, inj_map.get(target_fact["id"], {}).get("memory_ids", []))
        for c in candidates:
            if self.entail.check(c["text"], target_fact["text"]) > self.tau:
                self.deleter.delete_records(
                    user_id, inj_map.get(c["id"], {}).get("memory_ids", []))
                pr.facts_co_deleted.append(c["id"])
        return self._finalize(pr, user_id, target_fact)

    def _finalize(self, pr: PlanResult, user_id: str, target_fact: dict) -> PlanResult:
        residual, rederiv, rho = self._recoverability(user_id, target_fact)
        pr.residual_recoverability = max(residual, rederiv, rho)
        pr.final_residual = residual
        pr.final_rederivation = rederiv
        pr.parametric_risk = rho
        pr.collateral_k = len(pr.facts_co_deleted)
        # Floor-reaching (plan success) = deletable channels only (residual + re-derivation) < tau; the non-deletable parametric floor rho is a certification concern, kept separately as parametric_risk (mirrors certificate emitter's floor_reaching).
        pr.achieved_completeness = max(pr.final_residual, pr.final_rederivation) < self.tau
        return pr
