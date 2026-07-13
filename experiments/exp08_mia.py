"""Experiment 8 — membership inference via retrieval scores (powered).

Members = the enlarged ISOLATED set (clean single-value templates -> well-matched
twins), injected into a store alongside a permanent bystander background, then
deleted. Each member has ``--twins`` matched never-stored near-twins (same
template, different value). A 2nd matched control per fact lifts the powered test
toward n~60 and sharpens the naive-stage permutation p.

Per fact we take the top-1 retrieval similarity (continuous) of its exact-text
query against the store. AUC = P(member > twin) from these continuous scores,
with a bootstrap 95% CI (resampling facts) and a label-permutation p-value.

Stages:
  intact -> members present (sanity: AUC high)
  naive  -> each member deleted by its single surfaced record
  aware  -> every value-bearing row purged

If the artifact-aware CI includes 0.50, the honest finding is that artifact-aware
deletion RESTORES membership-indistinguishability. Until the CI is in, an AUC
near 0.5 is "not shown != 0.5".

Usage:  python experiments/exp08_mia.py -v
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
import llm  # noqa: E402
from pipeline.deleter import Deleter  # noqa: E402
from pipeline.injector import Injector, load_facts  # noqa: E402
from probes.base_probe import normalize_values  # noqa: E402
from probes.membership_inference import membership_auc, top1_scores  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Powered MIA via retrieval scores")
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--n-perm", type=int, default=1000)
    ap.add_argument("--twins", type=int, default=2,
                    help="matched never-stored near-twins per member (2 = the powered 2nd control)")
    ap.add_argument("--seed", type=int, default=config.GLOBAL_SEED)
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()
    if config.validate():
        raise SystemExit("Config not ready:\n  - " + "\n  - ".join(config.validate()))

    # Member pool = the full enlarged ISOLATED set (~250): single clear value per fact,
    # so value-twins are well matched. multi-hop / rho facts have no single swappable
    # value. Members auto-scale with the isolated set; run --twins 3 for more controls.
    members = load_facts(config.FACTS_DIR / "isolated_facts.json")
    background = [c for c in load_facts(config.FACTS_DIR / "context_facts.json")
                 if c.get("role") == "bystander"]
    member_queries = [m["text"] for m in members]
    print(f"Members={len(members)}  background(bystander)={len(background)}  twins/fact={args.twins}")
    print("Generating matched near-twins ...")
    twin_queries = [t for m in tqdm(members) for t in llm.value_twins(m["text"], n=args.twins)]

    from systems.mem0_adapter import Mem0Adapter
    adapter = Mem0Adapter()
    injector, deleter = Injector(adapter), Deleter(adapter)
    uid = f"{config.USER_ID_PREFIX}_mia"
    adapter.delete_all_memories(uid)

    print("Injecting background + members (infer=True) ...")
    injector.inject_many(uid, background + members, progress=tqdm, infer=True)

    def stage(label: str) -> dict:
        ms = top1_scores(adapter, uid, member_queries)
        ts = top1_scores(adapter, uid, twin_queries)
        res = membership_auc(ms, ts, n_boot=args.n_boot, n_perm=args.n_perm, seed=args.seed)
        res["stage"] = label
        if args.verbose:
            print(f"  {label:7s}: AUC={res['auc']:.3f} CI95={res['ci95']} "
                  f"p_perm={res['p_perm']} (mean member={res['mean_member']} twin={res['mean_twin']})"
                  + ("  [CI includes 0.5]" if res["ci_includes_half"] else ""))
        return res

    results = [stage("intact")]
    for m in members:                                  # naive: delete the surfaced record
        deleter.delete_top_match(uid, m["text"], normalize_values(m.get("delete_value", m.get("probe_value"))))
    results.append(stage("naive"))
    for m in members:                                  # artifact-aware: purge all value rows
        deleter.delete_value_rows(uid, normalize_values(m.get("delete_value", m.get("probe_value"))))
    results.append(stage("aware"))
    adapter.delete_all_memories(uid)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = config.RESULTS_DIR / f"exp08_mia_mem0_{stamp}"
    pd.DataFrame(results).to_csv(base.with_suffix(".csv"), index=False)
    base.with_suffix(".json").write_text(json.dumps(
        {"experiment": "exp08_mia", "timestamp_utc": stamp, "n_members": len(members),
         "n_background": len(background), "twins_per_fact": args.twins,
         "n_twins": len(twin_queries), "n_boot": args.n_boot, "n_perm": args.n_perm,
         "stages": results, "twins": twin_queries}, indent=2, default=str))

    print("\n" + "=" * 64)
    print("  EXP08 — MEMBERSHIP INFERENCE (powered: bootstrap CI + permutation)")
    print("=" * 64)
    for r in results:
        verdict = ("indistinguishable (CI incl. 0.5)" if r["ci_includes_half"]
                   else f"distinguishable (p={r['p_perm']})")
        print(f"  {r['stage']:7s}: AUC={r['auc']:.3f}  CI95={r['ci95']}  -> {verdict}")
    aware = results[-1]
    print("\n  Headline test — after ARTIFACT-AWARE deletion:")
    print(f"    {'membership signal SURVIVES' if not aware['ci_includes_half'] else 'indistinguishability RESTORED'}"
          f"  (AUC={aware['auc']:.3f}, CI95={aware['ci95']})")
    print(f"\n  Results: {base.with_suffix('.csv')}")


if __name__ == "__main__":
    main()
