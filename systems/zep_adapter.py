"""Zep/Graphiti adapter (secondary system) over a local Neo4j.

Graphiti is async + bi-temporal. We wrap it on a dedicated event loop and use a
sync Neo4j driver for direct Cypher reads (the KG-residual probe needs to inspect
entity/community summaries and edge temporal fields).

Empirically (graphiti-core 0.29.2): `remove_episode` HARD-deletes the episode and
its RELATES_TO edges + orphaned entities, but a SURVIVING entity's `summary`
(generated when the fact was added) is NOT recomputed -> the deleted fact persists
in that summary. Community summaries behave the same. Those are the structural
KG-residual channels (by design, not a bug).
"""
from __future__ import annotations

import asyncio
import datetime

import config
from systems.base import MemorySystemAdapter


def _llm_client():
    """Pinned gpt-4o-mini for Graphiti's extraction (cost + reproducibility)."""
    try:
        from graphiti_core.llm_client.config import LLMConfig
        from graphiti_core.llm_client.openai_client import OpenAIClient
        cfg = LLMConfig(api_key=config.OPENAI_API_KEY, model="gpt-4o-mini-2024-07-18",
                        small_model="gpt-4o-mini-2024-07-18")
        return OpenAIClient(config=cfg)
    except Exception:
        return None  # fall back to Graphiti defaults


class ZepGraphitiAdapter(MemorySystemAdapter):
    name = "zep"

    def __init__(self) -> None:
        from graphiti_core import Graphiti
        from neo4j import GraphDatabase

        self._loop = asyncio.new_event_loop()
        llm = _llm_client()
        self.client = (Graphiti(config.NEO4J_URI, config.NEO4J_USER, config.NEO4J_PASSWORD,
                                llm_client=llm) if llm
                       else Graphiti(config.NEO4J_URI, config.NEO4J_USER, config.NEO4J_PASSWORD))
        self._driver = GraphDatabase.driver(config.NEO4J_URI,
                                            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
        try:
            self._run(self.client.build_indices_and_constraints())
        except Exception:
            pass  # indices already exist

    def _run(self, coro):
        return self._loop.run_until_complete(coro)

    def _cypher(self, query: str, **params) -> list[dict]:
        with self._driver.session() as s:
            return s.run(query, **params).data()

    def supports_graph(self) -> bool:
        return True

    # ---- writes ------------------------------------------------------------
    def inject_fact(self, user_id: str, conversation: list[dict], infer: bool = True) -> dict:
        from graphiti_core.nodes import EpisodeType
        body = "\n".join(m.get("content", "") for m in conversation)
        res = self._run(self.client.add_episode(
            name=f"ep-{datetime.datetime.now().timestamp()}", episode_body=body,
            source_description="injected fact", reference_time=_utcnow(),
            source=EpisodeType.text, group_id=user_id))
        return {"episode_uuid": res.episode.uuid,
                "memory_ids": [res.episode.uuid],
                "edges": [{"uuid": e.uuid, "fact": e.fact} for e in res.edges],
                "nodes": [{"uuid": n.uuid, "name": n.name} for n in res.nodes]}

    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """memory_id is an episode uuid (Graphiti deletes by episode)."""
        self._run(self.client.remove_episode(memory_id))
        return True

    def delete_all_memories(self, user_id: str) -> bool:
        self._cypher("MATCH (n {group_id:$g}) DETACH DELETE n", g=user_id)
        return True

    def build_communities(self, user_id: str):
        return self._run(self.client.build_communities(group_ids=[user_id]))

    # ---- reads -------------------------------------------------------------
    def query(self, user_id: str, query: str, top_k: int = 10, threshold: float = 0.0) -> dict:
        edges = self._run(self.client.search(query, group_ids=[user_id], num_results=top_k))
        return {"results": [{"id": e.uuid, "fact": e.fact, "memory": e.fact,
                             "expired_at": str(e.expired_at), "invalid_at": str(e.invalid_at)}
                            for e in edges]}

    def list_memories(self, user_id: str) -> list[dict]:
        """Surviving RELATES_TO edges (the 'facts')."""
        rows = self._cypher(
            "MATCH ()-[r:RELATES_TO]->() WHERE r.group_id=$g "
            "RETURN r.uuid AS id, r.fact AS fact, toString(r.expired_at) AS expired_at, "
            "toString(r.invalid_at) AS invalid_at", g=user_id)
        for r in rows:
            r["memory"] = r.get("fact")
        return rows

    def list_graph(self, user_id: str) -> dict[str, list[dict]]:
        """Entity + Community nodes (with summaries) and RELATES_TO edges (with
        temporal fields). The summaries are the residual-survival surface."""
        nodes = self._cypher(
            "MATCH (n {group_id:$g}) WHERE n:Entity OR n:Community "
            "RETURN n.uuid AS id, labels(n) AS labels, n.name AS name, n.summary AS summary",
            g=user_id)
        edges = self._cypher(
            "MATCH ()-[r:RELATES_TO]->() WHERE r.group_id=$g "
            "RETURN r.uuid AS id, r.fact AS fact, toString(r.expired_at) AS expired_at, "
            "toString(r.invalid_at) AS invalid_at", g=user_id)
        return {"nodes": nodes, "edges": edges}

    def get_memory_metadata(self, user_id: str, memory_id: str) -> dict:
        rows = self._cypher("MATCH ()-[r:RELATES_TO {uuid:$u}]->() RETURN properties(r) AS p",
                            u=memory_id)
        return rows[0]["p"] if rows else {}

    def close(self) -> None:
        try:
            self._run(self.client.close())
        finally:
            self._driver.close()
            self._loop.close()


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)
