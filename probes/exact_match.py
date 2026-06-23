"""Exact-match probe = residual-survival ground truth.

Scans every memory in the store for any surface form of the fact's value. If
the value is physically present in a surviving record, the fact survived
deletion (residual survival), independent of whether retrieval would surface it.
"""
from __future__ import annotations

from probes.base_probe import BaseProbe, ProbeResult, normalize_values


class ExactMatchProbe(BaseProbe):
    name = "exact_match"

    def run(self, adapter, user_id: str, fact: dict) -> ProbeResult:
        values = normalize_values(fact.get("probe_value"))
        memories = adapter.list_memories(user_id)
        hits = []
        for m in memories:
            text = adapter.memory_text(m)
            low = text.lower()
            for v in values:
                if v.lower() in low:
                    hits.append({"memory_id": m.get("id"), "text": text, "matched": v})
                    break
        recoverable = len(hits) > 0
        return ProbeResult(
            probe=self.name, fact_id=fact["id"], recoverable=recoverable,
            score=1.0 if recoverable else 0.0,
            layer="memory_text" if recoverable else None,
            evidence=hits, detail={"scanned": len(memories), "values": values},
        )
