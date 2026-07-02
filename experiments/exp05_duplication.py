"""Experiment 5 — Mem0 duplication factorial (embedder x cadence).

Reported as a finding (cf. Mem0 issues #4896 hash-only dedup, #4573 ~37.6%
near-dups in production, #687 async race). We confirm it is NOT an artifact of
our local embedder or injection cadence, and we type the duplicates:
  - byte-identical  -> async write race
  - paraphrase      -> semantic-dedup design limitation

Metrics per cell (corpus = context + isolated, injected infer=True):
  row_inflation   = (rows - facts) / facts          (overall extra-row rate)
  dup_incidence   = fraction of corpus-unique facts with >1 row carrying their value
                    (RF4: denominator excludes facts whose value collides with
                    another fact's text, so overlap can't masquerade as duplication)
  byte/paraphrase = breakdown of duplicated facts

Usage:  python experiments/exp05_duplication.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from pipeline.injector import Injector, load_facts  # noqa: E402


def main() -> None:
    facts = (load_facts(config.FACTS_DIR / "context_facts.json")
             + load_facts(config.FACTS_DIR / "isolated_facts.json"))
    n_facts = len(facts)

    # RF4 exp05 fix: dup-incidence must reflect Mem0 duplication, not corpus
    # vocabulary overlap. A fact's value appearing in >1 row is only unambiguous
    # duplication when that value is globally UNIQUE in the corpus; otherwise the
    # extra row may be another fact's text. Restrict the denominator to facts with
    # a corpus-unique primary value.
    def _prim(f):
        v = f["probe_value"]
        return (v[0] if isinstance(v, list) else v).lower()

    _hay = {g["id"]: (g.get("text", "") + " " + g.get("utterance", "")).lower()
            for g in facts}
    measurable = [f for f in facts
                  if not any(g["id"] != f["id"] and _prim(f) in _hay[g["id"]]
                             for g in facts)]
    n_measurable = len(measurable)
    print(f"corpus={n_facts} facts; {n_measurable} have a corpus-unique value "
          f"(dup-incidence denominator); {n_facts - n_measurable} excluded as ambiguous")
    cells = []
    for embedder in ("huggingface", "openai"):
        from systems.mem0_adapter import Mem0Adapter
        adapter = Mem0Adapter(embedder=embedder, collection=f"dup_{embedder}")
        injector = Injector(adapter)
        for cadence in (0.0, 1.5):
            uid = f"dup_{embedder}_{str(cadence).replace('.', '')}"
            adapter.delete_all_memories(uid)
            injector.inject_many(uid, facts, settle_seconds=cadence, infer=True)
            mems = adapter.list_memories(uid)
            n_rows = len(mems)
            texts = [adapter.memory_text(m) for m in mems]

            dup_facts, byte_ident, paraphrase = 0, 0, 0
            for f in measurable:
                prim = _prim(f)
                hits = [t for t in texts if prim in t.lower()]
                if len(hits) > 1:
                    dup_facts += 1
                    norm = {h.strip().lower() for h in hits}
                    if len(norm) == 1:
                        byte_ident += 1
                    else:
                        paraphrase += 1
            cell = {
                "embedder": embedder, "cadence_s": cadence,
                "facts": n_facts, "measurable": n_measurable, "rows": n_rows,
                "row_inflation": round((n_rows - n_facts) / n_facts, 3),
                "dup_incidence": round(dup_facts / n_measurable, 3),
                "dup_facts": dup_facts, "byte_identical": byte_ident,
                "paraphrase": paraphrase,
            }
            cells.append(cell)
            print(f"  embedder={embedder:11s} cadence={cadence}s -> rows={n_rows}/{n_facts} "
                  f"inflation={cell['row_inflation']:+.0%} dup_incidence={cell['dup_incidence']:.0%} "
                  f"(byte={byte_ident}, paraphrase={paraphrase})")
            adapter.delete_all_memories(uid)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = config.RESULTS_DIR / f"exp05_duplication_{stamp}.json"
    out.write_text(json.dumps({"experiment": "exp05_duplication",
                               "timestamp_utc": stamp, "infer": True,
                               "cells": cells}, indent=2))
    print(f"\n  Saved: {out}")


if __name__ == "__main__":
    main()
