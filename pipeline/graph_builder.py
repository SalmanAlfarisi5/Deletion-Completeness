"""Build a dependency graph over facts and derived artifacts (networkx DiGraph).

Nodes: one per fact (target + context) and one per derived artifact.
Edges:
  DERIVED_FROM  : source_fact -> artifact   (from the artifact tracer)
  ENTAILS       : surviving_fact -> target   (from the entailment detector)
A target is recoverable if any surviving node has a path to it.
"""
from __future__ import annotations

import networkx as nx


class DependencyGraphBuilder:
    def __init__(self, entailment_detector=None):
        self.entailment_detector = entailment_detector
        self.G = nx.DiGraph()

    def add_fact(self, fact_id: str, fact_text: str, is_target: bool = False) -> None:
        self.G.add_node(fact_id, text=fact_text, node_type="fact",
                        is_target=is_target, deleted=False)

    def add_artifact(self, artifact_id: str, artifact_data: dict,
                     artifact_type: str) -> None:
        self.G.add_node(artifact_id, data=artifact_data, node_type="artifact",
                        artifact_type=artifact_type, deleted=False)

    def add_derivation_edge(self, artifact_id: str, source_fact_id: str) -> None:
        self.G.add_edge(source_fact_id, artifact_id, edge_type="DERIVED_FROM")

    def add_entailment_edge(self, surviving_fact_id: str, target_fact_id: str,
                            confidence: float) -> None:
        self.G.add_edge(surviving_fact_id, target_fact_id,
                        edge_type="ENTAILS", confidence=confidence)

    def build_entailment_edges(self, target_fact_id: str,
                               surviving_facts: list[dict],
                               threshold: float = 0.5) -> None:
        """Ask the entailment detector which surviving facts entail the target."""
        if self.entailment_detector is None:
            raise RuntimeError("No entailment detector configured")
        target_text = self.G.nodes[target_fact_id]["text"]
        for fact in surviving_facts:
            conf = self.entailment_detector.check(fact["text"], target_text)
            if conf > threshold:
                if fact["id"] not in self.G:
                    self.add_fact(fact["id"], fact["text"])
                self.add_entailment_edge(fact["id"], target_fact_id, conf)

    def mark_deleted(self, node_id: str) -> None:
        if node_id in self.G:
            self.G.nodes[node_id]["deleted"] = True

    def get_recovery_paths(self, target_fact_id: str) -> list[list[str]]:
        """All paths from a surviving (non-deleted) node to the target."""
        paths = []
        for node in self.G.nodes:
            if node == target_fact_id or self.G.nodes[node].get("deleted"):
                continue
            if nx.has_path(self.G, node, target_fact_id):
                paths.append(nx.shortest_path(self.G, node, target_fact_id))
        return paths
