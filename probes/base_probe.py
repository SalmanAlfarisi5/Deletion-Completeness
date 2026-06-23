"""Abstract probe interface + shared result type.

Every probe answers one question: can an adversary recover fact F from the
current system state? It returns a recoverability score in [0, 1].
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


def normalize_values(probe_value) -> list[str]:
    """probe_value may be a string or list of acceptable surface forms."""
    if isinstance(probe_value, str):
        return [probe_value]
    return [str(v) for v in (probe_value or [])]


@dataclass
class ProbeResult:
    probe: str
    fact_id: str
    recoverable: bool
    score: float                       # [0, 1]
    layer: str | None = None           # where it was found (memory/retrieval/kg/...)
    evidence: list[dict] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "probe": self.probe, "fact_id": self.fact_id,
            "recoverable": self.recoverable, "score": round(self.score, 4),
            "layer": self.layer, "evidence": self.evidence, "detail": self.detail,
        }


class BaseProbe(ABC):
    name: str = "base"

    @abstractmethod
    def run(self, adapter, user_id: str, fact: dict) -> ProbeResult:
        raise NotImplementedError
