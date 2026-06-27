"""Experiment 4 — re-derivation & the parametric floor (operands-only control).

Clean control for the RE-DERIVATION channel, contamination-free:
  - inject ONLY the source/operand facts (never the target's own value), verbatim
    (infer=False); VERIFY the target value is absent from every stored row, so
    residual survival = 0 by construction (this is the post-deletion state).
  - re-derivation probe (adversary reads the surviving operands + world knowledge,
    is given today's date) -> the leak.
  - co-delete the operands -> re-derivation should fall to the parametric floor.
  - parametric rho probe (model alone, no notes) -> the floor.

Facts are BINNED by recovery mechanism and NEVER aggregated across bins:
  bin 1 = re-derivable from stored facts alone   (co-deletion suffices)
  bin 2 = stored facts + correct world knowledge  (reasoner-dependent)
  bin 3 = world knowledge alone (= rho)           (needs the rho-gradient set)

Re-derivation is reasoner-model-dependent, so we run >= 2 reasoner models.

Usage:  python experiments/exp04_parametric.py --n 6 -v
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
from evaluation.stats import wilson_ci  # noqa: E402
from certificate.emitter import make_certificate, save_certificate  # noqa: E402
from pipeline.deleter import Deleter  # noqa: E402
from pipeline.injector import Injector, load_facts  # noqa: E402
from probes.base_probe import normalize_values  # noqa: E402
from probes.exact_match import ExactMatchProbe  # noqa: E402
from probes.parametric_probe import ParametricProbe  # noqa: E402


def bin_of(fact: dict) -> int:
    return {"stored": 1, "stored+world": 2, "world": 3}.get(
        fact.get("rederivation_basis", "stored+world"), 2)


def main() -> None:
    ap = argparse.ArgumentParser(description="Re-derivation & parametric floor")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--bystanders", type=int, default=3)
    ap.add_argument("--single", action="store_true", help="primary reasoner only (cheaper)")
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
    reasoners = [config.REASONER_MODEL] if args.single else [config.REASONER_MODEL, config.SECOND_MODEL]

    from systems.mem0_adapter import Mem0Adapter
    adapter = Mem0Adapter()
    injector, deleter, exact = Injector(adapter), Deleter(adapter), ExactMatchProbe()

    rows, certs = [], []
    for reasoner in reasoners:
        param = ParametricProbe(model=reasoner)
        for fact in tqdm(targets, desc=reasoner):
            entailing = [ctx_by_id[c] for c in fact.get("co_delete_required", []) if c in ctx_by_id]
            del_vals = normalize_values(fact.get("delete_value", fact["probe_value"]))
            target_exact = {**fact, "probe_value": del_vals}
            uid = f"{config.USER_ID_PREFIX}_mh_{fact['id']}_{abs(hash(reasoner)) % 9999}"
            adapter.delete_all_memories(uid)

            # CONTROL: inject operands only (never the target value), verbatim.
            injector.inject_many(uid, entailing + bystanders, infer=False, settle_seconds=0.0)
            contaminated = exact.run(adapter, user_id=uid, fact=target_exact).recoverable
            residual = 1.0 if contaminated else 0.0  # should be 0 (target never stored)

            red_operands = param.run_rederivation(adapter, uid, fact).score   # the leak
            rho = param.run_parametric(fact).score                            # the floor

            for c in entailing:                                               # co-delete operands
                deleter.delete_value_rows(uid, normalize_values(c.get("probe_value")))
            co_deleted = [c["id"] for c in entailing
                          if not deleter.rows_with_value(uid, normalize_values(c.get("probe_value")))]
            red_after = param.run_rederivation(adapter, uid, fact).score

            final = max(residual, red_after, rho)
            row = {"reasoner": reasoner, "fact_id": fact["id"], "bin": bin_of(fact),
                   "basis": fact.get("rederivation_basis"), "contaminated": contaminated,
                   "residual_survival": residual, "rederiv_with_operands": red_operands,
                   "rho": rho, "rederiv_after_codelete": red_after,
                   "final_recoverability": final, "collateral_k": len(co_deleted)}
            rows.append(row)
            if args.verbose:
                tqdm.write(f"  [{fact['id']} bin{row['bin']}] {reasoner.split('-')[0]}: "
                           f"residual={residual:.0f} leak(operands)={red_operands:.0f} "
                           f"rho={rho:.0f} after_codelete={red_after:.0f}")

            if reasoner == config.REASONER_MODEL:    # emit one cert per fact (primary reasoner)
                cert = make_certificate(
                    fact=fact, system="mem0", residual=residual, rederivation=red_after, rho=rho,
                    probe_scores={"residual_survival": residual,
                                  "rederiv_with_operands": red_operands, "rho": rho,
                                  "rederiv_after_codelete": red_after},
                    heuristic="operands-only control + co-delete operands",
                    facts_co_deleted=co_deleted, final_recoverability=final,
                    probe_battery=["exact_match", "rederivation", "parametric"])
                save_certificate(cert)
                certs.append(cert.certificate_id)
            if not args.keep:
                adapter.delete_all_memories(uid)

    df = pd.DataFrame(rows)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = config.RESULTS_DIR / f"exp04_parametric_mem0_{stamp}"
    df.to_csv(base.with_suffix(".csv"), index=False)

    # per-(reasoner, bin) summary — never aggregated across bins.
    # Per-fact re-derivation scores are binary (recovered or not), so each per-bin
    # rate is a proportion -> Wilson CI on k = #recovered, n = #facts in the bin.
    summary = defaultdict(dict)
    for (r, b), g in df.groupby(["reasoner", "bin"]):
        n_g = len(g)
        leak_ci = wilson_ci(int((g["rederiv_with_operands"] >= 0.5).sum()), n_g)
        after_ci = wilson_ci(int((g["rederiv_after_codelete"] >= 0.5).sum()), n_g)
        summary[r][f"bin{b}"] = {
            "n": n_g,
            "rederiv_with_operands": round(g["rederiv_with_operands"].mean(), 3),
            "rederiv_with_operands_ci95": [round(leak_ci[0], 4), round(leak_ci[1], 4)],
            "rederiv_after_codelete": round(g["rederiv_after_codelete"].mean(), 3),
            "rederiv_after_codelete_ci95": [round(after_ci[0], 4), round(after_ci[1], 4)],
            "rho": round(g["rho"].mean(), 3),
            "residual_survival": round(g["residual_survival"].mean(), 3),
        }
    base.with_suffix(".json").write_text(json.dumps(
        {"experiment": "exp04_parametric", "timestamp_utc": stamp, "design": "operands-only control",
         "reasoners": reasoners, "judge_model": config.JUDGE_MODEL,
         "per_reasoner_bin": summary, "rows": rows, "certificates": certs}, indent=2, default=str))

    print("\n" + "=" * 70)
    print("  EXP04 — RE-DERIVATION (operands-only control), by reasoner x bin")
    print("=" * 70)
    print("  bin1=stored-alone  bin2=stored+world  bin3=world-only(rho)")
    for r in reasoners:
        print(f"\n  reasoner = {r}")
        for b in sorted(summary[r]):
            s = summary[r][b]
            lo_l, hi_l = s["rederiv_with_operands_ci95"]
            lo_a, hi_a = s["rederiv_after_codelete_ci95"]
            print(f"    {b} (n={s['n']}): leak(operands)={s['rederiv_with_operands']:.0%} "
                  f"[{lo_l:.0%},{hi_l:.0%}]  after co-delete={s['rederiv_after_codelete']:.0%} "
                  f"[{lo_a:.0%},{hi_a:.0%}]  rho={s['rho']:.0%}  residual={s['residual_survival']:.0%}")
    print(f"\n  Certificates: {config.RESULTS_DIR / 'certificates'}   Results: {base.with_suffix('.csv')}")


if __name__ == "__main__":
    main()
