"""Experiment 8 — membership inference via retrieval scores (never-stored prior).

Control = a CONTROL store with the same corpus but the fact NEVER inserted.
Member = corpus + fact, then the fact deleted. We query the fact (+ paraphrases)
against both and test whether member scores exceed control scores
(Mann-Whitney one-sided, AUC effect size). We measure this after NAIVE deletion
(single record) and after ARTIFACT-AWARE deletion (all value-bearing rows):

  - naive  -> if Mem0 left a duplicate, member > control, AUC -> 1 (leak)
  - aware  -> member ~ control, AUC ~ 0.5 (indistinguishable from never-stored)

Usage:  python experiments/exp08_mia.py --n 6 -v
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from tqdm import tqdm  # noqa: E402

import config  # noqa: E402
import llm  # noqa: E402
from pipeline.deleter import Deleter  # noqa: E402
from pipeline.injector import Injector, load_facts  # noqa: E402
from probes.base_probe import normalize_values  # noqa: E402
from probes.membership_inference import membership_test  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="MIA via retrieval scores")
    ap.add_argument("--n", type=int, default=6, help="number of target facts")
    ap.add_argument("--corpus", type=int, default=27,
                    help="background size; >~25 reaches Mem0's duplication regime")
    ap.add_argument("--paraphrases", type=int, default=4)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=config.GLOBAL_SEED)
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()
    if config.validate():
        raise SystemExit("Config not ready:\n  - " + "\n  - ".join(config.validate()))
    np.random.seed(args.seed)

    corpus = (load_facts(config.FACTS_DIR / "context_facts.json")
              + load_facts(config.FACTS_DIR / "multi_hop_facts.json"))[: args.corpus]
    targets = load_facts(config.FACTS_DIR / "isolated_facts.json")[: args.n]

    from systems.mem0_adapter import Mem0Adapter
    adapter = Mem0Adapter()
    injector, deleter = Injector(adapter), Deleter(adapter)

    # control store: corpus only, target NEVER inserted (shared)
    uid_ctrl = f"{config.USER_ID_PREFIX}_mia_ctrl"
    adapter.delete_all_memories(uid_ctrl)
    injector.inject_many(uid_ctrl, corpus, infer=True)

    rows = []
    for fact in tqdm(targets, desc="targets"):
        del_vals = normalize_values(fact.get("probe_value"))
        queries = [fact["text"]] + llm.paraphrase(fact["text"], args.paraphrases)
        uid_m = f"{config.USER_ID_PREFIX}_mia_m_{fact['id']}"
        adapter.delete_all_memories(uid_m)
        injector.inject_many(uid_m, corpus + [fact], infer=True)
        n_dup = len(deleter.rows_with_value(uid_m, del_vals))            # >1 => Mem0 duplicated F

        deleter.delete_top_match(uid_m, fact["text"], del_vals)          # naive deletion
        mia_naive = membership_test(adapter, uid_m, uid_ctrl, queries)
        deleter.delete_value_rows(uid_m, del_vals)                       # artifact-aware purge
        mia_aware = membership_test(adapter, uid_m, uid_ctrl, queries)

        rows.append({"fact_id": fact["id"], "category": fact.get("category"),
                     "value_rows_in_member": n_dup,
                     "auc_naive": round(mia_naive["auc"], 3), "p_naive": mia_naive["p_value"],
                     "auc_aware": round(mia_aware["auc"], 3), "p_aware": mia_aware["p_value"],
                     "mean_member_naive": round(mia_naive["mean_member"], 3),
                     "mean_control": round(mia_naive["mean_control"], 3)})
        if args.verbose:
            tqdm.write(f"  [{fact['id']} dup={n_dup}] AUC naive={mia_naive['auc']:.2f} "
                       f"(p={mia_naive['p_value']:.3f}) -> aware={mia_aware['auc']:.2f} "
                       f"(p={mia_aware['p_value']:.3f})")
        adapter.delete_all_memories(uid_m)
    adapter.delete_all_memories(uid_ctrl)

    df = pd.DataFrame(rows)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = config.RESULTS_DIR / f"exp08_mia_mem0_{stamp}"
    df.to_csv(base.with_suffix(".csv"), index=False)
    metrics = {
        "mean_auc_naive": round(float(df["auc_naive"].mean()), 3),
        "mean_auc_aware": round(float(df["auc_aware"].mean()), 3),
        "sig_member_naive": int((df["p_naive"] < args.alpha).sum()),
        "sig_member_aware": int((df["p_aware"] < args.alpha).sum()),
        "n": len(df), "alpha": args.alpha,
        "n_duplicated": int((df["value_rows_in_member"] > 1).sum()),
        "mean_auc_naive_duplicated": (round(float(df[df["value_rows_in_member"] > 1]["auc_naive"].mean()), 3)
                                      if (df["value_rows_in_member"] > 1).any() else None),
    }
    base.with_suffix(".json").write_text(json.dumps(
        {"experiment": "exp08_mia", "timestamp_utc": stamp, "metrics": metrics,
         "rows": rows}, indent=2, default=str))

    print("\n" + "=" * 60)
    print("  EXP08 — MEMBERSHIP INFERENCE (retrieval-score)")
    print("=" * 60)
    print(f"  Mean AUC, naive deletion          : {metrics['mean_auc_naive']:.2f}  (0.5=no signal, 1=leak)")
    print(f"  Mean AUC, artifact-aware deletion : {metrics['mean_auc_aware']:.2f}")
    print(f"  Significant membership (p<{args.alpha}): "
          f"naive {metrics['sig_member_naive']}/{metrics['n']}, "
          f"aware {metrics['sig_member_aware']}/{metrics['n']}")
    print(f"  Facts Mem0 duplicated in member    : {metrics['n_duplicated']}/{metrics['n']}"
          + (f"  (mean AUC among them, naive = {metrics['mean_auc_naive_duplicated']})"
             if metrics["n_duplicated"] else ""))
    print(f"\n  Results: {base.with_suffix('.csv')}")


if __name__ == "__main__":
    main()
