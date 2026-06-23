"""Experiment 1 — naive deletion baseline.

Question: after a user asks to delete fact F and the system removes the single
record it surfaces for F, is F still recoverable from the surviving store?

Design:
  1. Inject targets (+ context corpus) under a fresh user_id.
  2. For each target F:
       a. count how many rows carry F's value (Mem0 may duplicate -> disclosed)
       b. probe BEFORE  (sanity: F recoverable)
       c. NAIVE delete  (delete the single top-retrieved record for F)
       d. probe AFTER   (residual survival? still retrievable?)
  3. Aggregate residual-survival + retrieval rates after naive deletion.

Naive deletion is content/search-based (delete the record the system surfaces),
which is robust to Mem0's async-id / duplication quirks. If the system silently
duplicated F, a single delete leaves copies -> residual survival.

Usage:
  python experiments/exp01_baseline.py --facts data/facts/isolated_facts.json --n 12 -v
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from tqdm import tqdm  # noqa: E402

import config  # noqa: E402
from pipeline.deleter import Deleter  # noqa: E402
from pipeline.injector import Injector, load_facts  # noqa: E402
from probes.base_probe import normalize_values  # noqa: E402
from probes.exact_match import ExactMatchProbe  # noqa: E402
from probes.paraphrase_probe import ParaphraseProbe  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Naive deletion baseline")
    ap.add_argument("--system", default="mem0", choices=["mem0"])
    ap.add_argument("--facts", default=str(config.FACTS_DIR / "isolated_facts.json"))
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--no-corpus", action="store_true")
    ap.add_argument("--no-paraphrase", action="store_true")
    ap.add_argument("--seed", type=int, default=config.GLOBAL_SEED)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    if config.validate():
        print("Config not ready:\n  - " + "\n  - ".join(config.validate()))
        raise SystemExit(1)
    random.seed(args.seed)
    np.random.seed(args.seed)

    targets = load_facts(args.facts)[: args.n]
    corpus = [] if args.no_corpus else load_facts(config.FACTS_DIR / "context_facts.json")
    user_id = f"{config.USER_ID_PREFIX}_{uuid.uuid4().hex[:8]}"
    print(f"System={args.system}  user_id={user_id}")
    print(f"Targets={len(targets)}  corpus={len(corpus)}  judge={config.JUDGE_MODEL}")

    from systems.mem0_adapter import Mem0Adapter
    adapter = Mem0Adapter()
    injector, deleter = Injector(adapter), Deleter(adapter)
    exact = ExactMatchProbe()
    para = None if args.no_paraphrase else ParaphraseProbe()

    adapter.delete_all_memories(user_id)
    print("\nInjecting corpus + targets (with settle) ...")
    injector.inject_many(user_id, corpus + targets, progress=tqdm)
    n_rows = len(adapter.list_memories(user_id))
    print(f"Store now holds {n_rows} memory rows.")

    def probe_all(fact):
        out = {"exact": exact.run(adapter, user_id, fact).as_dict()}
        if para:
            out["paraphrase"] = para.run(adapter, user_id, fact).as_dict()
        return out

    rows = []
    print("\nNaive-deleting each target (top-1 surfaced record) and re-probing ...")
    for fact in tqdm(targets):
        vals = normalize_values(fact.get("probe_value"))
        n_value_rows = len(deleter.rows_with_value(user_id, vals))  # duplication
        before = probe_all(fact)
        rep = deleter.delete_top_match(user_id, fact["text"], vals)
        after = probe_all(fact)
        row = {
            "fact_id": fact["id"], "category": fact.get("category"),
            "value_rows_before": n_value_rows, "deleted_count": len(rep["deleted"]),
            "exact_before": before["exact"]["score"],
            "exact_after": after["exact"]["score"],
            "retr_before": before.get("paraphrase", {}).get("score"),
            "retr_after": after.get("paraphrase", {}).get("score"),
            "residual_layer_after": after["exact"]["layer"],
            "residual_evidence": after["exact"]["evidence"],
        }
        rows.append(row)
        if args.verbose:
            tqdm.write(f"  [{fact['id']}] value_rows={n_value_rows} "
                       f"exact {row['exact_before']:.0f}->{row['exact_after']:.0f} "
                       f"retr {row['retr_before']}->{row['retr_after']}")

    df = pd.DataFrame(rows)
    residual_rate = float(df["exact_after"].mean())
    retr_rate = (float(df["retr_after"].dropna().mean())
                 if para and df["retr_after"].notna().any() else None)
    extraction_fidelity = float(df["exact_before"].mean())
    dup_rate = float((df["value_rows_before"] > 1).mean())

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = config.RESULTS_DIR / f"exp01_baseline_{args.system}_{stamp}"
    df.to_csv(base.with_suffix(".csv"), index=False)
    base.with_suffix(".json").write_text(json.dumps({
        "experiment": "exp01_baseline", "timestamp_utc": stamp, "system": args.system,
        "mem0_mode": config.MEM0_MODE, "llm_provider": config.LLM_PROVIDER,
        "judge_model": config.JUDGE_MODEL, "seed": args.seed, "user_id": user_id,
        "facts_file": args.facts, "n_targets": len(targets), "n_corpus": len(corpus),
        "store_rows_after_inject": n_rows,
        "metrics": {"extraction_fidelity_before": extraction_fidelity,
                    "naive_deletion_residual_rate": residual_rate,
                    "naive_deletion_retrieval_rate": retr_rate,
                    "duplicated_fact_rate": dup_rate},
        "rows": rows}, indent=2, default=str))
    if not args.keep:
        adapter.delete_all_memories(user_id)

    print("\n" + "=" * 60)
    print("  EXP01 — NAIVE DELETION BASELINE")
    print("=" * 60)
    print(f"  Targets tested            : {len(targets)}")
    print(f"  Store rows / facts        : {n_rows} / {len(targets) + len(corpus)}")
    print(f"  Facts Mem0 duplicated     : {dup_rate:.2%}  (>1 row carries the value)")
    print(f"  Extraction fidelity (pre) : {extraction_fidelity:.2%}")
    print(f"  Residual survival (post)  : {residual_rate:.2%}  (value remains after naive delete)")
    if retr_rate is not None:
        print(f"  Retrievable (post)        : {retr_rate:.2%}")
    print(f"\n  Results: {base.with_suffix('.csv')}")


if __name__ == "__main__":
    main()
