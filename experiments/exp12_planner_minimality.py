"""Experiment 12 — planner minimality across entailment topologies.

Compares the three co-deletion planners on a LIVE Mem0 store, per topology, against
the GROUND-TRUTH optimum k* (the minimum hitting set of the known entailment DAG,
planner/entailment_dag):

  * exact       — deletes a minimum hitting set of the entailment formula (the method);
                  provably minimal and never misses a multi-hop entailer.
  * threshold   — LLM-confidence greedy comparator (may over-delete on disjunctions,
                  or under-delete when no single operand entails the target).
  * depth_first — aggressive one-shot comparator (deletes every above-tau candidate).

For each target we record, per heuristic: collateral k, completeness, spurious
bystander deletions, and the optimality gap (k - k*). Grouped by topology, this turns
the "k is minimal" claim and the NP-hard min-hitting-set framing into a measured,
defensible result — and shows exactly where structure-awareness (the exact planner)
beats an LLM-judge greedy.

Usage:  python experiments/exp12_planner_minimality.py -v          # all multi-hop
        python experiments/exp12_planner_minimality.py --n 40 -v
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from tqdm import tqdm  # noqa: E402

import config  # noqa: E402
import planner.entailment_dag as ed  # noqa: E402
from pipeline.deleter import Deleter  # noqa: E402
from pipeline.injector import Injector, load_facts  # noqa: E402
from planner.entailment_detector import EntailmentDetector  # noqa: E402
from planner.optimizer import GreedyPlanner  # noqa: E402
from probes.exact_match import ExactMatchProbe  # noqa: E402
from probes.parametric_probe import ParametricProbe  # noqa: E402

HEURISTICS = ["exact", "threshold", "depth_first"]


def main() -> None:
    ap = argparse.ArgumentParser(description="Planner minimality across topologies")
    ap.add_argument("--n", type=int, default=None, help="targets (default: all multi-hop)")
    ap.add_argument("--bystanders", type=int, default=4)
    ap.add_argument("--entailment-model", default=config.ENTAILMENT_JUDGE_MODEL,
                    help="entailment judge for the greedy comparators (config.ENTAILMENT_JUDGE_MODEL; frontier wave = claude-sonnet-5)")
    ap.add_argument("--seed", type=int, default=config.GLOBAL_SEED)
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()
    if config.validate():
        raise SystemExit("Config not ready:\n  - " + "\n  - ".join(config.validate()))
    random.seed(args.seed)
    np.random.seed(args.seed)

    targets = load_facts(config.FACTS_DIR / "multi_hop_facts.json")[: args.n]
    context = load_facts(config.FACTS_DIR / "context_facts.json")
    ctx_by_id = {c["id"]: c for c in context}
    bystanders = [c for c in context if c.get("role") == "bystander"][: args.bystanders]

    from systems.mem0_adapter import Mem0Adapter
    adapter = Mem0Adapter()
    injector, deleter = Injector(adapter), Deleter(adapter)
    planner = GreedyPlanner(adapter, deleter, ExactMatchProbe(),
                            ParametricProbe(model=config.REASONER_MODEL),
                            EntailmentDetector(model=args.entailment_model),
                            threshold_tau=config.TAU)
    print(f"entailment judge (greedy comparators) = {args.entailment_model}")

    rows = []
    for fact in tqdm(targets, desc="targets"):
        basis = fact.get("rederivation_basis", "stored+world")
        entailing = [ctx_by_id[c] for c in fact.get("co_delete_required", []) if c in ctx_by_id]
        entail_ids = {c["id"] for c in entailing}
        candidates = entailing + bystanders
        k_star = ed.min_codelete_size(ed.dag_of(fact)["formula"])  # ground-truth optimum
        for heur in HEURISTICS:
            user_id = f"{config.USER_ID_PREFIX}_min_{fact['id']}_{heur}"
            adapter.delete_all_memories(user_id)
            inj_map = injector.inject_many(user_id, [fact] + candidates,
                                           infer=False, settle_seconds=0.0)
            plan = getattr(planner, f"heuristic_{heur}")(user_id, fact, candidates, inj_map)
            deleted = set(plan.facts_co_deleted)
            spurious = sorted(deleted - entail_ids)
            rows.append({
                "fact_id": fact["id"], "basis": basis, "topology": basis.replace("stored_", ""),
                "heuristic": heur, "k_star": k_star, "collateral_k": plan.collateral_k,
                "optimality_gap": plan.collateral_k - k_star,
                "spurious_bystanders": len(spurious),
                "achieved_completeness": plan.achieved_completeness,
                "final_recoverability": round(plan.residual_recoverability, 3)})
            adapter.delete_all_memories(user_id)
        if args.verbose:
            r = {x["heuristic"]: x for x in rows[-3:]}
            tqdm.write(f"  [{fact['id']} {basis}] k*={k_star} "
                       + "  ".join(f"{h}:k={r[h]['collateral_k']}"
                                   f"(gap{r[h]['optimality_gap']:+d},"
                                   f"{'C' if r[h]['achieved_completeness'] else 'X'})"
                                   for h in HEURISTICS))

    df = pd.DataFrame(rows)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = config.RESULTS_DIR / f"exp12_planner_minimality_{stamp}"
    df.to_csv(base.with_suffix(".csv"), index=False)

    # Summary: per (topology, heuristic) mean k, mean gap, completeness, spurious.
    summary: dict = defaultdict(dict)
    for (topo, heur), g in df.groupby(["topology", "heuristic"]):
        summary[topo][heur] = {
            "n": int(len(g)), "k_star": float(g["k_star"].mean()),
            "mean_k": round(float(g["collateral_k"].mean()), 3),
            "mean_gap": round(float(g["optimality_gap"].mean()), 3),
            "completeness": round(float(g["achieved_completeness"].mean()), 3),
            "spurious_total": int(g["spurious_bystanders"].sum())}
    overall = {heur: {
        "mean_k": round(float(df[df.heuristic == heur]["collateral_k"].mean()), 3),
        "mean_gap": round(float(df[df.heuristic == heur]["optimality_gap"].mean()), 3),
        "completeness": round(float(df[df.heuristic == heur]["achieved_completeness"].mean()), 3),
        "spurious_total": int(df[df.heuristic == heur]["spurious_bystanders"].sum())}
        for heur in HEURISTICS}
    base.with_suffix(".json").write_text(json.dumps(
        {"experiment": "exp12_planner_minimality", "timestamp_utc": stamp, "tau": config.TAU,
         "entailment_model": args.entailment_model, "n_targets": len(targets),
         "per_topology": summary, "overall": overall, "rows": rows}, indent=2, default=str))

    print("\n" + "=" * 72)
    print("  EXP12 — PLANNER MINIMALITY (k vs ground-truth optimum k*), by topology")
    print("=" * 72)
    for topo in sorted(summary):
        print(f"\n  {topo}  (k*={summary[topo][HEURISTICS[0]]['k_star']:.1f}, "
              f"n={summary[topo][HEURISTICS[0]]['n']})")
        for heur in HEURISTICS:
            s = summary[topo][heur]
            print(f"    {heur:11s}: k={s['mean_k']:.2f}  gap={s['mean_gap']:+.2f}  "
                  f"complete={s['completeness']:.0%}  spurious={s['spurious_total']}")
    print("\n  OVERALL")
    for heur in HEURISTICS:
        s = overall[heur]
        print(f"    {heur:11s}: mean_k={s['mean_k']:.2f}  mean_gap={s['mean_gap']:+.2f}  "
              f"complete={s['completeness']:.0%}  spurious={s['spurious_total']}")
    print(f"\n  Results: {base.with_suffix('.csv')}")


if __name__ == "__main__":
    main()
