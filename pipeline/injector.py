"""Inject controlled facts into a memory system as realistic conversation turns.

Captures, per fact, the memory IDs the system created/updated so that later a
*naive* deletion can target exactly the records the system associated with that
fact (rather than sweeping every row that mentions the value).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import config

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

    def inject(self, user_id: str, fact: dict, infer: bool = True) -> dict:
        convo = to_conversation(fact)
        if not infer:
            convo = convo[:1]  # store just the fact utterance; the ack is noise
        res = self.adapter.inject_fact(user_id, convo, infer=infer)
        results = res.get("results", []) if isinstance(res, dict) else (res or [])
        events = [
            {"id": r.get("id"), "event": r.get("event"), "memory": r.get("memory")}
            for r in results if isinstance(r, dict)
        ]
        # Memory IDs this fact is responsible for (newly added or updated).
        owned = [e["id"] for e in events
                 if e["id"] and (e["event"] in (None, "ADD", "UPDATE"))]
        return {"fact_id": fact["id"], "memory_ids": owned, "events": events, "raw": res}

    def inject_many(self, user_id: str, facts: list[dict], progress=None,
                    settle_seconds: float | None = None,
                    infer: bool = True) -> dict[str, dict]:
        """Inject a list of facts; returns {fact_id: injection_record}.

        Pauses `settle_seconds` after each injection so Mem0 indexes the new row
        before the next ADD-vs-UPDATE decision (avoids duplicate-row artifacts).
        With infer=False there is no extraction race, so settle can be 0.
        """
        settle = config.INJECT_SETTLE_SECONDS if settle_seconds is None else settle_seconds
        out: dict[str, dict] = {}
        it = progress(facts) if progress else facts
        for f in it:
            out[f["id"]] = self.inject(user_id, f, infer=infer)
            if settle:
                time.sleep(settle)
        return out
