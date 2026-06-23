"""Experiment 3 — the planner end-to-end (threshold heuristic).

For each multi-hop target, run GreedyPlanner.heuristic_threshold on a live store:
  probe -> purge the target's own artifacts -> co-delete entailing facts in
  entailment-confidence order, re-probing until recoverability < tau.

Success = achieves completeness with MINIMAL collateral: it should co-delete the
entailing operands and SPARE the bystanders (which it must not touch). We inject
verbatim (infer=False) so the fact->row map is reliable.

Usage:  python experiments/exp03_planner.py --n 6 -v
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402
from tqdm import tqdm  # noqa: E402

import config  # noqa: E402
from certificate.emitter import make_certificate, save_certificate  # noqa: E402
from pipeline.deleter import Deleter  # noqa: E402
from pipeline.injector import Injector, load_facts  # noqa: E402
from planner.entailment_detector import EntailmentDetector  # noqa: E402
from planner.optimizer import GreedyPlanner  # noqa: E402
from probes.exact_match import ExactMatchProbe  # noqa: E402
from probes.parametric_probe import ParametricProbe  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Planner end-to-end (threshold)")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--bystanders", type=int, default=4)
    ap.add_argument("--entailment-model", default=config.JUDGE_MODEL,
                    help="entailment judge (use gpt-4o: 0%% partial-operand false-fire)")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()
    if config.validate():
        raise SystemExit("Config not ready:\n  - " + "\n  - ".join(config.validate()))

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
    print(f"entailment judge = {args.entailment_model}")

    rows, certs = [], []
    for fact in tqdm(targets, desc="targets"):
        entailing = [ctx_by_id[c] for c in fact.get("co_delete_required", []) if c in ctx_by_id]
        entail_ids = {c["id"] for c in entailing}
        candidates = entailing + bystanders            # planner must pick operands, spare bystanders
        store = [fact] + candidates
        user_id = f"{config.USER_ID_PREFIX}_plan_{fact['id']}"
        adapter.delete_all_memories(user_id)
        inj_map = injector.inject_many(user_id, store, infer=False, settle_seconds=0.0)

        plan = planner.heuristic_threshold(user_id, fact, candidates, inj_map)

        deleted_set = set(plan.facts_co_deleted)
        spurious = sorted(deleted_set - entail_ids)     # bystanders wrongly co-deleted (BAD)
        not_needed = sorted(entail_ids - deleted_set)   # operands not needed (minimality, OK)
        row = {"fact_id": fact["id"], "basis": fact.get("rederivation_basis"),
               "co_deleted": plan.facts_co_deleted, "collateral_k": plan.collateral_k,
               "operands_required_set": sorted(entail_ids),
               "spurious_bystanders": spurious, "operands_not_needed": not_needed,
               "final_recoverability": round(plan.residual_recoverability, 3),
               "parametric_risk": round(plan.parametric_risk, 3),
               "achieved_completeness": plan.achieved_completeness}
        rows.append(row)
        if args.verbose:
            tqdm.write(f"  [{fact['id']}] co_deleted={plan.facts_co_deleted} k={plan.collateral_k} "
                       f"spurious={spurious} final_rec={row['final_recoverability']} "
                       f"complete={plan.achieved_completeness}")

        cert = make_certificate(
            fact=fact, system="mem0", residual=0.0,
            rederivation=plan.residual_recoverability, rho=plan.parametric_risk,
            probe_scores={"final_recoverability": plan.residual_recoverability,
                          "parametric_risk": plan.parametric_risk},
            heuristic=plan.heuristic, facts_co_deleted=plan.facts_co_deleted,
            final_recoverability=plan.residual_recoverability,
            probe_battery=["exact_match", "rederivation", "parametric"])
        save_certificate(cert)
        certs.append(cert.certificate_id)
        if not args.keep:
            adapter.delete_all_memories(user_id)

    df = pd.DataFrame(rows)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = config.RESULTS_DIR / f"exp03_planner_mem0_{stamp}"
    df.to_csv(base.with_suffix(".csv"), index=False)
    metrics = {
        "completeness_rate": round(float(df["achieved_completeness"].mean()), 3),
        "mean_collateral_k": round(float(df["collateral_k"].mean()), 3),
        "spurious_bystander_deletions": int(df["spurious_bystanders"].map(len).sum()),
        "operands_spared_by_minimality": int(df["operands_not_needed"].map(len).sum()),
    }
    base.with_suffix(".json").write_text(json.dumps(
        {"experiment": "exp03_planner", "timestamp_utc": stamp, "tau": config.TAU,
         "metrics": metrics, "rows": rows, "certificates": certs}, indent=2, default=str))

    print("\n" + "=" * 60)
    print("  EXP03 — PLANNER (threshold heuristic)")
    print("=" * 60)
    print(f"  Achieved completeness        : {metrics['completeness_rate']:.0%} of targets")
    print(f"  Mean collateral k            : {metrics['mean_collateral_k']}")
    print(f"  Spurious bystander deletions : {metrics['spurious_bystander_deletions']}  (want 0)")
    print(f"  Operands spared (minimality) : {metrics['operands_spared_by_minimality']}  "
          f"(co-deleted a sufficient subset)")
    print(f"\n  Results: {base.with_suffix('.csv')}")


if __name__ == "__main__":
    main()
