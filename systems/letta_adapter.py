"""MemGPT/Letta adapter (tertiary system) — LLM-paging architecture.

Each user_id maps to a Letta agent, which has TWO memory surfaces neither Mem0
nor Graphiti expose the same way:
  - CORE memory blocks (human/persona) the agent rewrites in-context via
    memory_insert / memory_replace tool calls
  - ARCHIVAL vector store (passages)

Deletion in Letta is usually AGENT-MEDIATED: you ask the agent to forget and it
*decides* which memory-edit tool to call. `agent_forget` exercises that path;
`delete_memory` does the direct (faithful) op. `list_memories` returns BOTH
surfaces tagged by layer so probes can locate residue.

Empirically (0.16.8): archival delete is destructive; a conversational "forget"
made gpt-4o-mini call memory_replace and scrub the value — but faithfulness is
the experiment, not an assumption.
"""
from __future__ import annotations

import config
from systems.base import MemorySystemAdapter


class LettaAdapter(MemorySystemAdapter):
    name = "letta"

    def __init__(self, base_url: str | None = None, model: str | None = None,
                 embedding: str | None = None) -> None:
        from letta_client import Letta

        self.client = Letta(base_url=base_url or config.LETTA_BASE_URL)
        self.model = model or config.LETTA_MODEL
        self.embedding = embedding or config.LETTA_EMBEDDING
        self._agents: dict[str, str] = {}

    def _agent(self, user_id: str) -> str:
        if user_id not in self._agents:
            name = f"dc-{user_id}"
            # Reuse a same-named server-side agent stranded by a prior run instead of
            # leaking a fresh one every time (RF4 L-16).
            existing = None
            try:
                for a in (self.client.agents.list(name=name) or []):
                    if getattr(a, "name", None) == name:
                        existing = a.id
                        break
            except Exception:  # noqa: BLE001 -- list filter unsupported / transient
                existing = None
            if existing:
                self._agents[user_id] = existing
            else:
                a = self.client.agents.create(
                    name=name,
                    memory_blocks=[
                        {"label": "human", "value": "(no information about the user yet)"},
                        {"label": "persona", "value": "You are a helpful assistant that "
                         "faithfully stores and manages the user's information."}],
                    model=self.model, embedding=self.embedding)
                self._agents[user_id] = a.id
        return self._agents[user_id]

    def _tool_calls(self, resp) -> list[str]:
        return [m.tool_call.name for m in resp.messages
                if getattr(m, "message_type", "") == "tool_call_message"]

    # ---- writes ------------------------------------------------------------
    def inject_fact(self, user_id: str, conversation: list[dict], infer: bool = True) -> dict:
        aid = self._agent(user_id)
        text = " ".join(m.get("content", "") for m in conversation if m.get("role") == "user")
        resp = self.client.agents.messages.create(
            agent_id=aid, input=f"Please remember the following information: {text}")
        return {"agent_id": aid, "memory_ids": [], "tool_calls": self._tool_calls(resp)}

    def archival_insert(self, user_id: str, text: str) -> list[str]:
        """Directly seed an archival passage (simulating a fact already in the
        vector store the agent didn't itself write). Returns the created passage
        id(s) so a caller can build a fact->row map for faithful, direct deletion
        (long text may be chunked into several passages)."""
        res = self.client.agents.passages.create(agent_id=self._agent(user_id), text=text)
        items = res if isinstance(res, list) else getattr(res, "passages", None) or [res]
        return [p.id for p in items if getattr(p, "id", None)]

    def agent_forget(self, user_id: str, instruction: str) -> dict:
        """Agent-mediated deletion: the agent decides how to comply."""
        aid = self._agent(user_id)
        resp = self.client.agents.messages.create(agent_id=aid, input=instruction)
        return {"tool_calls": self._tool_calls(resp)}

    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """Direct (faithful) op: core block overwrite or archival passage delete."""
        aid = self._agent(user_id)
        if memory_id.startswith("block:"):
            self.client.agents.blocks.update(memory_id.split(":", 1)[1], agent_id=aid,
                                             value="(removed)")
        else:
            self.client.agents.passages.delete(memory_id, agent_id=aid)
        return True

    def delete_all_memories(self, user_id: str) -> bool:
        # Delete the tracked agent AND any same-named agent stranded server-side by a
        # crashed/--keep run, so agents (and their Postgres rows) don't accumulate
        # across processes (RF4 L-16).
        name = f"dc-{user_id}"
        ids = set()
        popped = self._agents.pop(user_id, None)
        if popped:
            ids.add(popped)
        try:
            for a in (self.client.agents.list(name=name) or []):
                if getattr(a, "name", None) == name:
                    ids.add(a.id)
        except Exception:  # noqa: BLE001
            pass
        for aid in ids:
            try:
                self.client.agents.delete(aid)
            except Exception:  # noqa: BLE001
                pass
        return True

    # ---- reads -------------------------------------------------------------
    def list_memories(self, user_id: str) -> list[dict]:
        """Both surfaces: core blocks + archival passages, tagged by layer."""
        aid = self._agent(user_id)
        rows = []
        for b in self.client.agents.blocks.list(aid):
            rows.append({"id": f"block:{b.label}", "layer": "core_block",
                         "label": b.label, "memory": b.value or "", "text": b.value or ""})
        for p in self.client.agents.passages.list(aid):
            rows.append({"id": p.id, "layer": "archival", "memory": p.text, "text": p.text})
        return rows

    def query(self, user_id: str, query: str, top_k: int = 10, threshold: float = 0.0) -> dict:
        aid = self._agent(user_id)
        try:
            res = self.client.agents.passages.search(agent_id=aid, query=query)
            return {"results": [{"id": p.id, "memory": p.text, "text": p.text} for p in res]}
        except Exception:
            return {"results": self.list_memories(user_id)}

    def get_memory_metadata(self, user_id: str, memory_id: str) -> dict:
        return {}

    def core_blocks(self, user_id: str) -> dict[str, str]:
        aid = self._agent(user_id)
        return {b.label: (b.value or "") for b in self.client.agents.blocks.list(aid)}

    def set_core_block(self, user_id: str, label: str, value: str) -> None:
        """Overwrite a core memory block directly (faithful, non-agent-mediated).
        Used to seed the agent's known user identity (the default human block says
        '(no information about the user yet)', which otherwise tells a re-derivation
        adversary nothing is known about 'the user')."""
        self.client.agents.blocks.update(label, agent_id=self._agent(user_id), value=value)
