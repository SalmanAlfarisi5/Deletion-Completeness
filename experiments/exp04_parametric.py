"""Experiment 4 — re-derivation & the parametric floor (the core result).

Per multi-hop target F (run in its own small, clean store so duplication is not
a confound):
  0. inject F + its entailing context facts + a few bystanders
  1. ARTIFACT-COMPLETE delete of F (remove every row carrying F's value)
       - residual survival            -> ~0 by construction
       - re-derivation (retrieve+model) from surviving entailing facts -> HIGH (leak!)
       - parametric rho (model alone)  -> ~0
  2. CO-DELETE the entailing context facts
       - re-derivation                 -> LOW
       - whatever remains ~ rho (the floor)
  3. emit a certificate per fact.

Shows the two-cause decomposition: even PERFECT residual deletion leaves a
re-derivation channel that only co-deletion of entailing facts closes — down to
the parametric floor rho.

Usage:  python experiments/exp04_parametric.py --n 6 -v
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
from certificate.emitter import make_certificate, save_certificate  # noqa: E402
from pipeline.deleter import Deleter  # noqa: E402
from pipeline.injector import Injector, load_facts  # noqa: E402
from probes.base_probe import normalize_values  # noqa: E402
from probes.exact_match import ExactMatchProbe  # noqa: E402
from probes.parametric_probe import ParametricProbe  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Re-derivation & parametric floor")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--bystanders", type=int, default=3)
    ap.add_argument("--seed", type=int, default=config.GLOBAL_SEED)
    ap.add_argument("--keep", action="store_true")
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
    exact, param = ExactMatchProbe(), ParametricProbe()

    rows, certs = [], []
    for fact in tqdm(targets, desc="targets"):
        fid = fact["id"]
        entailing = [ctx_by_id[c] for c in fact.get("co_delete_required", []) if c in ctx_by_id]
        user_id = f"{config.USER_ID_PREFIX}_mh_{fid}_{uuid.uuid4().hex[:6]}"
        adapter.delete_all_memories(user_id)
        # store verbatim (infer=False) to keep injection controlled and avoid
        # Mem0 baking derived values into operand rows.
        injector.inject_many(user_id, [fact] + entailing + bystanders,
                             infer=False, settle_seconds=0.0)

        # residual survival is checked on the target's OWN value; re-derivation
        # is scored on the broader recovery criterion (the full fact).
        del_vals = normalize_values(fact.get("delete_value", fact["probe_value"]))
        target_exact = {**fact, "probe_value": del_vals}

        # baseline (store intact)
        res_before = exact.run(adapter, user_id, target_exact).score
        red_before = param.run_rederivation(adapter, user_id, fact).score

        # 1) artifact-complete deletion of the target's own value
        deleter.delete_value_rows(user_id, del_vals)
        res_naive = exact.run(adapter, user_id, target_exact).score
        red_naive = param.run_rederivation(adapter, user_id, fact).score
        rho = param.run_parametric(fact).score

        # 2) co-delete the entailing context facts
        for c in entailing:
            deleter.delete_value_rows(user_id, normalize_values(c.get("probe_value")))
        # collateral = un-requested entailing facts whose value is now gone (counts
        # side-effect removals when facts share surface forms)
        co_deleted = [c["id"] for c in entailing
                      if not deleter.rows_with_value(user_id, normalize_values(c.get("probe_value")))]
        res_codel = exact.run(adapter, user_id, target_exact).score
        red_codel = param.run_rederivation(adapter, user_id, fact).score

        final = max(res_codel, red_codel, rho)
        probe_scores = {"exact_before": res_before, "rederiv_before": red_before,
                        "exact_after_purge": res_naive, "rederiv_after_purge": red_naive,
                        "parametric_rho": rho, "exact_after_codelete": res_codel,
                        "rederiv_after_codelete": red_codel}
        cert = make_certificate(
            fact=fact, system="mem0", residual=res_codel, rederivation=red_codel, rho=rho,
            probe_scores=probe_scores,
            heuristic="artifact-complete purge + co-delete entailing facts",
            facts_co_deleted=co_deleted, final_recoverability=final,
            probe_battery=["exact_match", "rederivation", "parametric"])
        save_certificate(cert)
        certs.append(cert.certificate_id)

        row = {"fact_id": fid, "basis": fact.get("rederivation_basis"),
               "category": fact.get("category"), **probe_scores,
               "final_recoverability": final, "status": cert.status,
               "collateral_k": cert.collateral_k}
        rows.append(row)
        if args.verbose:
            tqdm.write(f"  [{fid}] {fact.get('rederivation_basis'):12s} "
                       f"rederiv before={red_before:.0f} purge={red_naive:.0f} "
                       f"codelete={red_codel:.0f} | rho={rho:.0f} -> {cert.status}")
        if not args.keep:
            adapter.delete_all_memories(user_id)

    df = pd.DataFrame(rows)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = config.RESULTS_DIR / f"exp04_parametric_mem0_{stamp}"
    df.to_csv(base.with_suffix(".csv"), index=False)
    metrics = {
        "rederiv_after_purge_rate": float(df["rederiv_after_purge"].mean()),
        "rederiv_after_codelete_rate": float(df["rederiv_after_codelete"].mean()),
        "parametric_rho_mean": float(df["parametric_rho"].mean()),
        "residual_after_purge_rate": float(df["exact_after_purge"].mean()),
        "certified_complete": int((df["status"] == "COMPLETE").sum()),
    }
    base.with_suffix(".json").write_text(json.dumps(
        {"experiment": "exp04_parametric", "timestamp_utc": stamp,
         "judge_model": config.JUDGE_MODEL, "seed": args.seed,
         "metrics": metrics, "rows": rows, "certificates": certs}, indent=2, default=str))

    print("\n" + "=" * 64)
    print("  EXP04 — RE-DERIVATION & PARAMETRIC FLOOR")
    print("=" * 64)
    print(f"  Residual survival after purge      : {metrics['residual_after_purge_rate']:.2%}")
    print(f"  Re-derivable after purge (the leak): {metrics['rederiv_after_purge_rate']:.2%}")
    print(f"  Re-derivable after CO-DELETION     : {metrics['rederiv_after_codelete_rate']:.2%}")
    print(f"  Parametric floor rho (mean)        : {metrics['parametric_rho_mean']:.2%}")
    print(f"  Certified COMPLETE                 : {metrics['certified_complete']}/{len(df)}")
    print(f"\n  Certificates: {config.RESULTS_DIR / 'certificates'}")
    print(f"  Results: {base.with_suffix('.csv')}")


if __name__ == "__main__":
    main()
