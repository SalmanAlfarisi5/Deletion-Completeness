"""Trace which derived artifacts a fact injection produced (snapshot + diff)."""
from __future__ import annotations


class ArtifactTracer:
    """Snapshot memory state before/after an injection and diff to find new
    artifacts. Each artifact is then classified by layer.
    """

    def __init__(self, adapter):
        self.adapter = adapter
        self._snapshots: dict[str, dict] = {}

    def snapshot(self, user_id: str, label: str) -> dict:
        memories = self.adapter.list_memories(user_id)
        self._snapshots[label] = {m["id"]: m for m in memories if m.get("id")}
        return self._snapshots[label]

    def diff(self, before_label: str, after_label: str) -> list[dict]:
        before = set(self._snapshots[before_label])
        after = self._snapshots[after_label]
        return [after[i] for i in (set(after) - before)]

    def classify_artifact(self, artifact: dict) -> str:
        """Layer of a Mem0 artifact. Graph nodes/edges only appear when graph
        memory is enabled; basic OSS Mem0 yields extracted `memory` rows.
        """
        if "source" in artifact and "target" in artifact:
            return "kg_edge"
        if "name" in artifact and "memory" not in artifact:
            return "kg_node"
        if "memory" in artifact:
            return "memory"
        return "raw_text"
