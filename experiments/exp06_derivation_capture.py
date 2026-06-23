"""Experiment 6 — infer=True derivation-capture (a Mem0 finding).

When facts are added with infer=True, Mem0's extraction LLM may COMPUTE a derived
value from the operands and store it verbatim — e.g. adding "born in 1991" can
produce a stored row "...making him ~35 years old". If so, the *derived* target
value becomes residual in the store even though it was never injected, and even
though only the operands were ever provided.

Test: inject ONLY the operand facts (never the target value) with infer=True;
check whether the target's own value (delete_value) appears in any stored row.
Contrast: infer=False stores operands verbatim, so capture is 0 by construction.

Usage:  python experiments/exp06_derivation_capture.py -v
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from pipeline.injector import Injector, load_facts  # noqa: E402
from probes.base_probe import normalize_values  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="infer=True derivation-capture")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    targets = load_facts(config.FACTS_DIR / "multi_hop_facts.json")
    ctx_by_id = {c["id"]: c for c in load_facts(config.FACTS_DIR / "context_facts.json")}

    from systems.mem0_adapter import Mem0Adapter
    adapter = Mem0Adapter()
    injector = Injector(adapter)

    rows = []
    for fact in targets:
        entailing = [ctx_by_id[c] for c in fact.get("co_delete_required", []) if c in ctx_by_id]
        del_vals = normalize_values(fact.get("delete_value", fact["probe_value"]))
        for mode in (False, True):                      # infer=False control, infer=True test
            uid = f"capture_{fact['id']}_{int(mode)}"
            adapter.delete_all_memories(uid)
            injector.inject_many(uid, entailing, infer=mode,
                                 settle_seconds=1.5 if mode else 0.0)
            stored = [adapter.memory_text(m) for m in adapter.list_memories(uid)]
            hits = [t for t in stored if any(v.lower() in t.lower() for v in del_vals)]
            rows.append({"fact_id": fact["id"], "infer": mode,
                         "captured": bool(hits), "stored_rows": stored, "evidence": hits})
            if args.verbose and mode:
                tag = "CAPTURED" if hits else "clean"
                tqdm_print = print
                tqdm_print(f"  [{fact['id']}] infer=True -> {tag}"
                           + (f"  -> {hits}" if hits else ""))
            if not args.keep:
                adapter.delete_all_memories(uid)

    capture_rate = sum(r["captured"] for r in rows if r["infer"]) / max(
        1, sum(1 for r in rows if r["infer"]))
    false_under_false = sum(r["captured"] for r in rows if not r["infer"])

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = config.RESULTS_DIR / f"exp06_derivation_capture_{stamp}.json"
    out.write_text(json.dumps({"experiment": "exp06_derivation_capture",
                               "timestamp_utc": stamp,
                               "capture_rate_infer_true": capture_rate,
                               "captured_under_infer_false": false_under_false,
                               "rows": rows}, indent=2, default=str))
    print("\n" + "=" * 60)
    print("  EXP06 — infer=True DERIVATION-CAPTURE")
    print("=" * 60)
    print(f"  Targets whose derived value Mem0 baked in (infer=True): "
          f"{capture_rate:.0%}")
    print(f"  Same under infer=False (control, expect 0): {false_under_false}")
    print(f"\n  Saved: {out}")


if __name__ == "__main__":
    main()
