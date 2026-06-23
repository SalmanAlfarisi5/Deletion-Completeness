"""Mem0 adapter — supports open-source (`Memory`) and hosted (`MemoryClient`).

Targets mem0ai 2.0.7, whose API differs from older docs: `search()` and
`get_all()` take `filters={"user_id": ...}` rather than a positional user_id,
and return `{"results": [...]}`. Memory rows expose the text under `memory`.
"""
from __future__ import annotations

import config
from systems.base import MemorySystemAdapter


class Mem0Adapter(MemorySystemAdapter):
    name = "mem0"

    def __init__(self) -> None:
        self.mode = config.MEM0_MODE
        if self.mode == "oss":
            from mem0 import Memory

            self.client = Memory.from_config(config.mem0_oss_config())
        elif self.mode == "hosted":
            from mem0 import MemoryClient

            self.client = MemoryClient(api_key=config.MEM0_API_KEY)
        else:
            raise ValueError(f"Unknown MEM0_MODE: {self.mode!r}")

    # ---- writes ------------------------------------------------------------
    def inject_fact(self, user_id: str, conversation: list[dict]) -> dict:
        return self.client.add(conversation, user_id=user_id)

    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        self.client.delete(memory_id)
        return True

    def delete_all_memories(self, user_id: str) -> bool:
        self.client.delete_all(user_id=user_id)
        return True

    # ---- reads -------------------------------------------------------------
    def query(self, user_id: str, query: str, top_k: int = 10,
              threshold: float = 0.0) -> dict:
        if self.mode == "oss":
            return self.client.search(
                query, filters={"user_id": user_id}, top_k=top_k, threshold=threshold
            )
        res = self.client.search(query, user_id=user_id)
        return res if isinstance(res, dict) else {"results": res}

    def list_memories(self, user_id: str) -> list[dict]:
        if self.mode == "oss":
            res = self.client.get_all(filters={"user_id": user_id}, top_k=10000)
        else:
            res = self.client.get_all(user_id=user_id)
        if isinstance(res, dict):
            return res.get("results", [])
        return res

    def get_memory_metadata(self, user_id: str, memory_id: str) -> dict:
        return self.client.get(memory_id)
