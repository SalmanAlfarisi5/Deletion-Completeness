"""Unified recovery scoring — shared by exp04 (re-derivation) and exp07 (rho),
so both sit on ONE scale.

Two scoring paths, chosen by the target type:
- NUMERIC target  -> parse the number from the answer and accept within a
  tolerance band (relative for magnitudes, exact for small codes). The band is a
  knob (exact / 5% / 10% / 20%) for the mid-tier rho tolerance sweep.
- NON-NUMERIC target (categorical / threshold) -> defer to the LLM recovery judge.

Logging the raw answers + this re-scorer makes tolerance sweeps free (no new
LLM calls).
"""
from __future__ import annotations

import re

_NUM = re.compile(r"-?\d[\d,]*\.?\d*")


def value_segment(answer: str) -> str:
    """Text after the last 'Value:' marker (matches parametric_probe)."""
    low = answer or ""
    idx = low.lower().rfind("value:")
    return low[idx + 6:] if idx >= 0 else low


def parse_number(s: str) -> float | None:
    """First number in `s`, handling commas and a trailing 'k' (150k -> 150000)."""
    if not s:
        return None
    s2 = s.replace("SGD", "").replace("$", "")
    m = _NUM.search(s2)
    if not m:
        return None
    try:
        num = float(m.group(0).replace(",", ""))
    except ValueError:
        return None
    after = s2[m.end():].lstrip().lower()
    if after[:1] == "k" and not after[1:2].isalpha():   # 150k -> 150000, but not km/kg
        num *= 1000
    return num


def is_numeric_target(values: list[str]) -> bool:
    return any(parse_number(v) is not None for v in values)


def numeric_recovered(target_values: list[str], answer: str, tolerance: float) -> bool:
    """True if the answer's number is within `tolerance` (relative) of any target
    number. tolerance == 0 means exact (for codes/PINs)."""
    tnums = [n for n in (parse_number(v) for v in target_values) if n is not None]
    anum = parse_number(value_segment(answer))
    if anum is None or not tnums:
        return False
    for t in tnums:
        if tolerance == 0:
            if abs(anum - t) < 0.5:
                return True
        elif t != 0 and abs(anum - t) / abs(t) <= tolerance:
            return True
    return False


REFUSAL_MARKERS = (
    "cannot", "can't", "cannot determine", "unable", "i don't", "i do not",
    "not possible", "no information", "insufficient", "as an ai", "i'm sorry",
    "cannot provide", "without more", "unknown",
)


def looks_like_refusal(answer: str) -> bool:
    """Heuristic: the answer hedges/refuses rather than committing to a value."""
    low = (answer or "").lower()
    return any(m in low for m in REFUSAL_MARKERS)
