"""Experiment 1 — naive deletion baseline.

Question: after a user asks to delete fact F and the system removes the
record(s) it created for F, is F still recoverable from the surviving store?

Design:
  1. Inject the target facts (+ context corpus for realism / consolidation)
     under a fresh user_id, recording which memory IDs each fact produced.
  2. For each target F:
       a. probe BEFORE  (sanity: F should be recoverable)
       b. NAIVE delete  (remove only the records F produced)
       c. verify the raw deletion took effect
       d. probe AFTER   (residual survival? still retrievable?)
  3. Aggregate: residual-survival rate and retrieval rate after naive deletion.

Usage:
  python experiments/exp01_baseline.py --system mem0 \
      --facts data/facts/isolated_facts.json --n 5 --verbose
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import uuid
from datetime import datetime, timezone

# make project root importable when run as `python experiments/exp01_baseline.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from tqdm import tqdm  # noqa: E402

import config  # noqa: E402
from pipeline.deleter import Deleter  # noqa: E402
from pipeline.injector import Injector, load_facts  # noqa: E402
from probes.exact_match import ExactMatchProbe  # noqa: E402
from probes.paraphrase_probe import ParaphraseProbe  # noqa: E402

ADAPTERS = {"mem0": "systems.mem0_adapter.Mem0Adapter"}


def get_adapter(system: str):
    if system != "mem0":
        raise SystemExit(f"Only 'mem0' is wired up so far (got {system!r}).")
    from systems.mem0_adapter import Mem0Adapter

    return Mem0Adapter()


def main() -> None:
    ap = argparse.ArgumentParser(description="Naive deletion baseline")
    ap.add_argument("--system", default="mem0", choices=list(ADAPTERS))
    ap.add_argument("--facts", default=str(config.FACTS_DIR / "isolated_facts.json"))
    ap.add_argument("--n", type=int, default=5, help="number of target facts to test")
    ap.add_argument("--no-corpus", action="store_true",
                    help="skip injecting context facts (faster, cheaper, less realistic)")
    ap.add_argument("--no-paraphrase", action="store_true",
                    help="skip the paraphrase retrieval probe (cheaper)")
    ap.add_argument("--seed", type=int, default=config.GLOBAL_SEED)
    ap.add_argument("--keep", action="store_true",
                    help="do NOT wipe memories at the end (for manual inspection)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    problems = config.validate()
    if problems:
        print("Config not ready:\n  - " + "\n  - ".join(problems))
        print("\nFill the key in .env, then re-run. (OSS Mem0 needs OPENAI_API_KEY "
              "for fact extraction.)")
        raise SystemExit(1)

    random.seed(args.seed)
    np.random.seed(args.seed)

    targets = load_facts(args.facts)[: args.n]
    corpus = [] if args.no_corpus else load_facts(config.FACTS_DIR / "context_facts.json")
    user_id = f"{config.USER_ID_PREFIX}_{uuid.uuid4().hex[:8]}"

    print(f"System={args.system}  user_id={user_id}")
    print(f"Targets={len(targets)}  corpus={len(corpus)}  judge={config.JUDGE_MODEL}")

    adapter = get_adapter(args.system)
    injector = Injector(adapter)
    deleter = Deleter(adapter)
    exact = ExactMatchProbe()
    para = None if args.no_paraphrase else ParaphraseProbe()

    adapter.delete_all_memories(user_id)  # clean slate

    # ---- inject -----------------------------------------------------------
    print("\nInjecting corpus + targets ...")
    to_inject = corpus + targets
    inj = injector.inject_many(user_id, to_inject, progress=tqdm)
    n_rows = len(adapter.list_memories(user_id))
    print(f"Store now holds {n_rows} memory rows.")

    # ---- per-target naive deletion ---------------------------------------
    def probe_all(fact):
        out = {"exact": exact.run(adapter, user_id, fact).as_dict()}
        if para:
            out["paraphrase"] = para.run(adapter, user_id, fact).as_dict()
        return out

    rows = []
    print("\nNaive-deleting each target and re-probing ...")
    for fact in tqdm(targets):
        rec = inj[fact["id"]]
        before = probe_all(fact)
        del_report = deleter.delete_records(user_id, rec["memory_ids"])
        verify = deleter.verify_deleted(user_id, rec["memory_ids"])
        after = probe_all(fact)

        row = {
            "fact_id": fact["id"],
            "category": fact.get("category"),
            "type": fact.get("type"),
            "n_owned_records": len(rec["memory_ids"]),
            "raw_deleted_ok": all(verify.values()) if verify else False,
            "exact_before": before["exact"]["score"],
            "exact_after": after["exact"]["score"],
            "retr_before": before.get("paraphrase", {}).get("score"),
            "retr_after": after.get("paraphrase", {}).get("score"),
            "residual_layer_after": after["exact"]["layer"],
            "residual_evidence": after["exact"]["evidence"],
        }
        rows.append(row)
        if args.verbose:
            tqdm.write(
                f"  [{fact['id']}] exact {row['exact_before']:.0f}->{row['exact_after']:.0f}"
                f"  retr {row['retr_before']}->{row['retr_after']}"
                f"  raw_deleted={row['raw_deleted_ok']}"
            )

    # ---- aggregate + persist ---------------------------------------------
    df = pd.DataFrame(rows)
    residual_rate = float(df["exact_after"].mean()) if len(df) else float("nan")
    retr_rate = (float(df["retr_after"].dropna().mean())
                 if para and df["retr_after"].notna().any() else None)
    extraction_fidelity = float(df["exact_before"].mean()) if len(df) else float("nan")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = config.RESULTS_DIR / f"exp01_baseline_{args.system}_{stamp}"
    df.to_csv(base.with_suffix(".csv"), index=False)
    summary = {
        "experiment": "exp01_baseline",
        "timestamp_utc": stamp,
        "system": args.system,
        "mem0_mode": config.MEM0_MODE,
        "llm_provider": config.LLM_PROVIDER,
        "judge_model": config.JUDGE_MODEL,
        "embed_model": config.EMBED_MODEL,
        "seed": args.seed,
        "user_id": user_id,
        "facts_file": args.facts,
        "n_targets": len(targets),
        "n_corpus": len(corpus),
        "store_rows_after_inject": n_rows,
        "metrics": {
            "extraction_fidelity_before": extraction_fidelity,
            "naive_deletion_residual_rate": residual_rate,
            "naive_deletion_retrieval_rate": retr_rate,
        },
        "rows": rows,
        "injection_records": inj,
    }
    base.with_suffix(".json").write_text(json.dumps(summary, indent=2, default=str))

    if not args.keep:
        adapter.delete_all_memories(user_id)

    # ---- report -----------------------------------------------------------
    print("\n" + "=" * 60)
    print("  EXP01 — NAIVE DELETION BASELINE")
    print("=" * 60)
    print(f"  Targets tested            : {len(targets)}")
    print(f"  Extraction fidelity (pre) : {extraction_fidelity:.2%}  "
          f"(value present before deletion)")
    print(f"  Residual survival (post)  : {residual_rate:.2%}  "
          f"(value still in store after naive delete)")
    if retr_rate is not None:
        print(f"  Retrievable (post)        : {retr_rate:.2%}  "
              f"(paraphrase query surfaces value)")
    print(f"\n  Results: {base.with_suffix('.csv')}")
    print(f"           {base.with_suffix('.json')}")


if __name__ == "__main__":
    main()
