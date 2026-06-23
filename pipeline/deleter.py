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
