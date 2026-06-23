"""LLM-as-judge entailment detection.

Does a surviving fact (or combination of surviving facts) let an adversary
recover a deleted target fact? Used to draw ENTAILS edges in the dependency
graph and to choose co-deletion targets in the planner.
"""
from __future__ import annotations

import llm

ENTAILMENT_PROMPT = """You are evaluating whether surviving memory fact(s) entail a deleted fact.

Surviving fact(s):
{surviving}

Deleted fact: "{target}"

Question: If someone knows ONLY the surviving fact(s) plus general world knowledge,
can they infer or recover the deleted fact?

- YES     -> inferable with >80% confidence
- PARTIAL -> right category/range but not the exact value
- NO      -> gives no meaningful information about the deleted fact

Respond ONLY as JSON: {{"answer":"YES|PARTIAL|NO","confidence":0.0-1.0,"reasoning":"..."}}"""


class EntailmentDetector:
    def __init__(self, model: str | None = None):
        self.model = model
        self.cache: dict[tuple, dict] = {}

    def check_detailed(self, surviving_text: str | list[str], target_text: str) -> dict:
        if isinstance(surviving_text, (list, tuple)):
            surviving = "\n".join(f"- {s}" for s in surviving_text)
        else:
            surviving = f"- {surviving_text}"
        key = (surviving, target_text)
        if key in self.cache:
            return self.cache[key]
        msgs = [{"role": "user", "content": ENTAILMENT_PROMPT.format(
            surviving=surviving, target=target_text)}]
        out = llm.chat_json(msgs, model=self.model, temperature=0.0, max_tokens=300)
        ans = str(out.get("answer", "NO")).upper()
        try:
            conf = float(out.get("confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        # PARTIAL shouldn't read as a full recovery
        if ans == "NO":
            conf = min(conf, 0.2)
        res = {"answer": ans, "confidence": conf, "reasoning": out.get("reasoning", "")}
        self.cache[key] = res
        return res

    def check(self, surviving_text: str | list[str], target_text: str) -> float:
        """Return entailment confidence in [0, 1]."""
        return self.check_detailed(surviving_text, target_text)["confidence"]
