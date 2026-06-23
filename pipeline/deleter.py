"""Delete memory records and verify the raw deletion actually took effect."""
from __future__ import annotations


class Deleter:
    def __init__(self, adapter):
        self.adapter = adapter

    def delete_records(self, user_id: str, memory_ids: list[str]) -> dict:
        """Delete the given records (those that still exist). Returns a report."""
        existing = {m["id"] for m in self.adapter.list_memories(user_id)}
        targeted = [m for m in memory_ids if m in existing]
        deleted, failed = [], []
        for mid in targeted:
            try:
                self.adapter.delete_memory(user_id, mid)
                deleted.append(mid)
            except Exception as e:  # noqa: BLE001 - record, don't crash the run
                failed.append({"id": mid, "error": str(e)})
        return {
            "requested": memory_ids,
            "targeted": targeted,           # existed at delete time
            "deleted": deleted,
            "failed": failed,
            "skipped_absent": [m for m in memory_ids if m not in existing],
        }

    def verify_deleted(self, user_id: str, memory_ids: list[str]) -> dict[str, bool]:
        """True == record is gone."""
        remaining = {m["id"] for m in self.adapter.list_memories(user_id)}
        return {mid: mid not in remaining for mid in memory_ids}

    # ---- content/search-based targeting (robust to Mem0's async/dup quirks) --
    def rows_with_value(self, user_id: str, values: list[str]) -> list[dict]:
        """All memory rows whose text contains any of the given surface forms."""
        vals = [v.lower() for v in values]
        return [m for m in self.adapter.list_memories(user_id)
                if any(v in self.adapter.memory_text(m).lower() for v in vals)]

    def delete_value_rows(self, user_id: str, values: list[str],
                          exclude: set[str] | None = None) -> dict:
        """Artifact-aware: delete EVERY row carrying the value."""
        exclude = exclude or set()
        ids = [m["id"] for m in self.rows_with_value(user_id, values)
               if m.get("id") not in exclude]
        return self.delete_records(user_id, ids)

    def delete_top_match(self, user_id: str, query_text: str,
                         values: list[str] | None = None) -> dict:
        """Naive: delete the SINGLE record the system surfaces for this fact
        (top retrieval hit, preferring one that actually carries the value)."""
        res = self.adapter.query(user_id, query_text, top_k=10)
        mems = res.get("results", []) if isinstance(res, dict) else (res or [])
        if not mems:
            return {"deleted": [], "targeted": []}
        chosen = None
        if values:
            vals = [v.lower() for v in values]
            chosen = next((m for m in mems
                           if any(v in self.adapter.memory_text(m).lower() for v in vals)),
                          None)
        chosen = chosen or mems[0]
        return self.delete_records(user_id, [chosen["id"]])
