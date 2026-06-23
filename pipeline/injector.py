"""Inject controlled facts into a memory system as realistic conversation turns.

Captures, per fact, the memory IDs the system created/updated so that later a
*naive* deletion can target exactly the records the system associated with that
fact (rather than sweeping every row that mentions the value).
"""
from __future__ import annotations

import json
from pathlib import Path

ACK = "Got it — I've noted that for you."


def load_facts(path: str | Path) -> list[dict]:
    return json.loads(Path(path).read_text())["facts"]


def to_conversation(fact: dict) -> list[dict]:
    """Wrap a fact's natural utterance into a user/assistant turn."""
    return [
        {"role": "user", "content": fact["utterance"]},
        {"role": "assistant", "content": ACK},
    ]


class Injector:
    def __init__(self, adapter):
        self.adapter = adapter

    def inject(self, user_id: str, fact: dict) -> dict:
        res = self.adapter.inject_fact(user_id, to_conversation(fact))
        results = res.get("results", []) if isinstance(res, dict) else (res or [])
        events = [
            {"id": r.get("id"), "event": r.get("event"), "memory": r.get("memory")}
            for r in results if isinstance(r, dict)
        ]
        # Memory IDs this fact is responsible for (newly added or updated).
        owned = [e["id"] for e in events
                 if e["id"] and (e["event"] in (None, "ADD", "UPDATE"))]
        return {"fact_id": fact["id"], "memory_ids": owned, "events": events, "raw": res}

    def inject_many(self, user_id: str, facts: list[dict],
                    progress=None) -> dict[str, dict]:
        """Inject a list of facts; returns {fact_id: injection_record}."""
        out: dict[str, dict] = {}
        it = progress(facts) if progress else facts
        for f in it:
            out[f["id"]] = self.inject(user_id, f)
        return out
