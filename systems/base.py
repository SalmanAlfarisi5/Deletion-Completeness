"""Abstract base class for memory-system adapters.

Every target system (Mem0, Zep/Graphiti, Letta) is wrapped in a subclass that
exposes the same interface so the rest of the pipeline is system-agnostic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MemorySystemAdapter(ABC):
    """Abstract base for all memory system adapters."""

    #: Short system identifier, e.g. "mem0", "zep", "letta".
    name: str = "abstract"

    @abstractmethod
    def inject_fact(self, user_id: str, conversation: list[dict]) -> dict:
        """Feed a conversation turn to the memory system. Returns system response."""
        raise NotImplementedError

    @abstractmethod
    def query(self, user_id: str, query: str) -> dict:
        """Query the memory system. Returns retrieved memories + (optional) answer."""
        raise NotImplementedError

    @abstractmethod
    def list_memories(self, user_id: str) -> list[dict]:
        """List all stored memories for a user. Returns raw memory objects."""
        raise NotImplementedError

    @abstractmethod
    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """Delete a specific memory by ID. Returns True if successful."""
        raise NotImplementedError

    @abstractmethod
    def delete_all_memories(self, user_id: str) -> bool:
        """Wipe all memories for a user (cleanup between experiments)."""
        raise NotImplementedError

    @abstractmethod
    def get_memory_metadata(self, user_id: str, memory_id: str) -> dict:
        """Get raw metadata for a memory object (embeddings, timestamps, etc.)."""
        raise NotImplementedError

    # ---- optional capabilities (override where supported) -------------------

    def list_graph(self, user_id: str) -> dict[str, list[dict]]:
        """Return graph artifacts as {"nodes": [...], "edges": [...]}.

        Default: empty. Override for systems with a knowledge graph (Mem0 graph
        memory, Zep/Graphiti). This is where re-derivation-relevant artifacts
        (entities/relations) live, distinct from the text memory rows.
        """
        return {"nodes": [], "edges": []}

    def supports_graph(self) -> bool:
        return False

    @staticmethod
    def memory_text(memory: dict[str, Any]) -> str:
        """Best-effort extraction of the human-readable text from a memory object.

        Adapters store/return memories in slightly different shapes; probes call
        this so they don't need to know each system's field names.
        """
        for key in ("memory", "text", "content", "data", "fact", "summary"):
            val = memory.get(key)
            if isinstance(val, str) and val.strip():
                return val
        return str(memory)
