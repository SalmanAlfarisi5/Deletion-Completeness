"""Experiment 2 — artifact-aware deletion vs naive deletion.

Naive deletion removes only the record(s) the system created for the fact.
Artifact-aware deletion ALSO purges every surviving artifact that physically
carries the value. This experiment measures the residual-survival gap between
the two (it is the residual-survival fix; it does NOT address re-derivation,
which is exp04's job).

Usage:
  python experiments/exp02_artifact_purge.py --facts data/facts/isolated_facts.json --n 12
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


def main() -> None:
    ap = argparse.ArgumentParser(description="Artifact-aware vs naive deletion")
    ap.add_argument("--facts", default=str(config.FACTS_DIR / "isolated_facts.json"))
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--no-corpus", action="store_true")
    ap.add_argument("--seed", type=int, default=config.GLOBAL_SEED)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if config.validate():
        raise SystemExit("Config not ready:\n  - " + "\n  - ".join(config.validate()))
    random.seed(args.seed)
    np.random.seed(args.seed)

    targets = load_facts(args.facts)[: args.n]
    corpus = [] if args.no_corpus else load_facts(config.FACTS_DIR / "context_facts.json")
    user_id = f"{config.USER_ID_PREFIX}_aw_{uuid.uuid4().hex[:8]}"

    from systems.mem0_adapter import Mem0Adapter
    adapter = Mem0Adapter()
    injector, deleter, exact = Injector(adapter), Deleter(adapter), ExactMatchProbe()

    print(f"user_id={user_id}  targets={len(targets)}  corpus={len(corpus)}")
    adapter.delete_all_memories(user_id)
    injector.inject_many(user_id, corpus + targets, progress=tqdm)

    rows = []
    for fact in tqdm(targets, desc="targets"):
        vals = normalize_values(fact.get("probe_value"))
        n_value_rows = len(deleter.rows_with_value(user_id, vals))
        before = exact.run(adapter, user_id, fact).score
        # naive: delete the single record the system surfaces for the fact
        deleter.delete_top_match(user_id, fact["text"], vals)
        naive = exact.run(adapter, user_id, fact).score
        # artifact-aware: purge every remaining row carrying the value
        extra = deleter.delete_value_rows(user_id, vals)
        aware = exact.run(adapter, user_id, fact).score
        rows.append({"fact_id": fact["id"], "category": fact.get("category"),
                     "value_rows_before": n_value_rows, "residual_before": before,
                     "residual_naive": naive, "residual_artifact_aware": aware,
                     "extra_artifacts_purged": len(extra["deleted"])})
        if args.verbose:
            tqdm.write(f"  [{fact['id']}] value_rows={n_value_rows} "
                       f"residual before={before:.0f} naive={naive:.0f} "
                       f"aware={aware:.0f} extra_purged={len(extra['deleted'])}")

    df = pd.DataFrame(rows)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = config.RESULTS_DIR / f"exp02_artifact_purge_mem0_{stamp}"
    df.to_csv(base.with_suffix(".csv"), index=False)
    metrics = {
        "residual_naive_rate": float(df["residual_naive"].mean()),
        "residual_artifact_aware_rate": float(df["residual_artifact_aware"].mean()),
        "mean_extra_artifacts_purged": float(df["extra_artifacts_purged"].mean()),
    }
    base.with_suffix(".json").write_text(json.dumps(
        {"experiment": "exp02_artifact_purge", "timestamp_utc": stamp,
         "user_id": user_id, "metrics": metrics, "rows": rows}, indent=2, default=str))

    if not args.keep:
        adapter.delete_all_memories(user_id)

    print("\n" + "=" * 60)
    print("  EXP02 — ARTIFACT-AWARE vs NAIVE DELETION")
    print("=" * 60)
    print(f"  Residual survival, naive          : {metrics['residual_naive_rate']:.2%}")
    print(f"  Residual survival, artifact-aware : {metrics['residual_artifact_aware_rate']:.2%}")
    print(f"  Mean extra artifacts purged       : {metrics['mean_extra_artifacts_purged']:.2f}")
    print(f"\n  Results: {base.with_suffix('.csv')}")


if __name__ == "__main__":
    main()
