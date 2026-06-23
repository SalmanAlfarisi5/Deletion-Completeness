"""KG-node residue probe (for graph systems like Zep/Graphiti).

Scans the surviving knowledge graph for the deleted value across the structural
residual channels:
  - entity_summary    : a surviving Entity node whose generated summary still
                        states the fact (not recomputed on deletion)
  - community_summary : a Community summary built pre-deletion, never recomputed
  - invalidated_edge  : an edge marked expired/invalid (bi-temporal) but still
                        present with its fact text
  - active_edge       : an edge that still actively carries the fact

Returns recoverable + which channels fired.
"""
from __future__ import annotations

from probes.base_probe import BaseProbe, ProbeResult, normalize_values


def _set(v) -> bool:
    return v not in (None, "None", "")


class KGNodeResidueProbe(BaseProbe):
    name = "kg_node_residue"

    def run(self, adapter, user_id: str, fact: dict) -> ProbeResult:
        if not adapter.supports_graph():
            return ProbeResult(self.name, fact["id"], False, 0.0,
                               detail={"note": "system has no graph layer"})
        vals = [v.lower() for v in normalize_values(fact.get("probe_value"))]
        g = adapter.list_graph(user_id)
        hits, channels = [], set()
        for n in g.get("nodes", []):
            text = (n.get("summary") or "")
            if any(v in text.lower() for v in vals):
                ch = "community_summary" if "Community" in (n.get("labels") or []) else "entity_summary"
                channels.add(ch)
                hits.append({"channel": ch, "node": n.get("name"), "text": text})
        for e in g.get("edges", []):
            text = (e.get("fact") or "")
            if any(v in text.lower() for v in vals):
                ch = ("invalidated_edge" if (_set(e.get("expired_at")) or _set(e.get("invalid_at")))
                      else "active_edge")
                channels.add(ch)
                hits.append({"channel": ch, "fact": text, "expired_at": e.get("expired_at")})
        recoverable = len(hits) > 0
        return ProbeResult(self.name, fact["id"], recoverable, 1.0 if recoverable else 0.0,
                           layer="|".join(sorted(channels)) if channels else None,
                           evidence=hits, detail={"channels": sorted(channels)})
