"""Paraphrase retrieval probe.

An adversary rarely knows the exact stored wording. Generate N paraphrases of
the fact, query the system with each, and measure how often retrieval surfaces
a memory that contains the fact's value. Score = hit rate across paraphrases.
"""
from __future__ import annotations

import config
import llm
from probes.base_probe import BaseProbe, ProbeResult, normalize_values


class ParaphraseProbe(BaseProbe):
    name = "paraphrase"

    def __init__(self, n: int | None = None, top_k: int = 10):
        self.n = n or config.N_PARAPHRASES
        self.top_k = top_k

    def run(self, adapter, user_id: str, fact: dict) -> ProbeResult:
        values = normalize_values(fact.get("probe_value"))
        queries = llm.paraphrase(fact["text"], self.n)
        hits, evidence = 0, []
        for q in queries:
            res = adapter.query(user_id, q, top_k=self.top_k)
            mems = res.get("results", []) if isinstance(res, dict) else (res or [])
            found = False
            for m in mems:
                text = adapter.memory_text(m)
                if any(v.lower() in text.lower() for v in values):
                    found = True
                    evidence.append({"query": q, "memory_id": m.get("id"),
                                     "text": text, "score": m.get("score")})
                    break
            hits += int(found)
        score = hits / len(queries) if queries else 0.0
        return ProbeResult(
            probe=self.name, fact_id=fact["id"], recoverable=score > 0, score=score,
            layer="retrieval" if score > 0 else None, evidence=evidence,
            detail={"n_queries": len(queries), "hits": hits, "queries": queries},
        )
