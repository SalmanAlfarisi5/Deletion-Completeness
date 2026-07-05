"""Experiment 7 — the parametric floor rho, measured on a gradient.

rho = recovery RATE of a deleted target from ONLY the subject's world-knowable
context (no memory store), over N stochastic samples, scored by the SAME
criterion as exp04 re-derivation (ParametricProbe._recovered = probe_value
substring union LLM judge) so rho and re-derivation are on one scale.

This version also:
  - LOGS every sampled answer (so re-scoring is free);
  - measures a BASE-RATE condition (generic context) to separate base rate from
    context-lift (lift = rho_context - rho_baserate);
  - reports a MID-TIER tolerance sweep (exact / 5 / 10 / 20%) by re-scoring the
    logged numeric answers — "the floor exists at all tolerances, its magnitude
    is tolerance-dependent";
  - audits HIGH-tier answers for refusal/hedging (rho is then an adversarial
    LOWER bound for sensitive-attribute hops).

Pipeline: delete the target (residual -> 0), recoverability bottoms out at rho;
the certificate carries the measured rho and flips completeness to FALSE when
rho > tau (the limit result).

Usage:  python experiments/exp07_rho_gradient.py --n-samples 6 -v
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
from certificate.emitter import make_certificate, save_certificate  # noqa: E402
from evaluation.recovery import looks_like_refusal, numeric_recovered  # noqa: E402
from evaluation.stats import wilson_ci  # noqa: E402
from pipeline.deleter import Deleter  # noqa: E402
from pipeline.injector import Injector, load_facts  # noqa: E402
from probes.base_probe import normalize_values  # noqa: E402
from probes.exact_match import ExactMatchProbe  # noqa: E402
from probes.parametric_probe import ParametricProbe  # noqa: E402

TIER_ORDER = ["low", "mid", "high"]
SWEEP_TOLS = [0.0, 0.05, 0.10, 0.20]


def main() -> None:
    ap = argparse.ArgumentParser(description="rho-gradient measurement + pipeline")
    ap.add_argument("--n-samples", type=int, default=8)
    ap.add_argument("--single", action="store_true")
    ap.add_argument("--seed", type=int, default=config.GLOBAL_SEED)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()
    if config.validate():
        raise SystemExit("Config not ready:\n  - " + "\n  - ".join(config.validate()))
    random.seed(args.seed)
    np.random.seed(args.seed)

    facts = load_facts(config.FACTS_DIR / "rho_gradient_facts.json")
    reasoners = [config.REASONER_MODEL] if args.single else config.reasoner_models()

    ckpt_p = config.RESULTS_DIR / "exp07_ckpt.json"
    rows, rho_by_fact, done = [], defaultdict(dict), set()
    if ckpt_p.exists():   # resume a crashed run WITHOUT re-spending on finished reasoners
        try:
            ck = json.loads(ckpt_p.read_text())
            if (ck.get("n") == args.n_samples and ck.get("reasoners") == reasoners
                    and ck.get("n_facts") == len(facts)):
                rows = ck["rows"]
                for _fid, _d in ck["rho_by_fact"].items():
                    rho_by_fact[_fid] = _d
                done = set(ck["done_reasoners"])
                print(f"  [resume] {len(done)} reasoner(s) from checkpoint: {sorted(done)}")
        except Exception:  # noqa: BLE001 -- a bad checkpoint just means start fresh
            rows, rho_by_fact, done = [], defaultdict(dict), set()
    for reasoner in reasoners:
        if reasoner in done:
            continue
        param = ParametricProbe(model=reasoner)
        for f in tqdm(facts, desc=f"rho/{reasoner.split('-')[0]}"):
            base_ctx = f"{f['subject']} is a person in Singapore."   # strips the informative attribute
            ctx = param.estimate_rho(f, f["world_context"], n=args.n_samples)
            base = param.estimate_rho(f, base_ctx, n=args.n_samples)
            rho_by_fact[f["id"]][reasoner] = ctx["rho"]
            refusals = sum(looks_like_refusal(a) for a in ctx["answers"])
            rows.append({"reasoner": reasoner, "fact_id": f["id"], "tier": f["tier"],
                         "subject": f["subject"], "rho_context": ctx["rho"],
                         "rho_baserate": base["rho"], "context_lift": ctx["rho"] - base["rho"],
                         "refusals": refusals, "n": args.n_samples,
                         "answers_context": ctx["answers"], "answers_baserate": base["answers"]})
            if args.verbose:
                tqdm.write(f"  [{f['id']} {f['tier']:4s}] {reasoner.split('-')[0]:11s} "
                           f"rho={ctx['rho']:.2f} base={base['rho']:.2f} "
                           f"lift={ctx['rho']-base['rho']:+.2f} refusals={refusals}/{args.n_samples}")
        done.add(reasoner)   # checkpoint after each reasoner (protects the multi-hour run)
        ckpt_p.write_text(json.dumps(
            {"n": args.n_samples, "reasoners": reasoners, "n_facts": len(facts),
             "done_reasoners": sorted(done), "rows": rows,
             "rho_by_fact": dict(rho_by_fact)}, default=str))

    df = pd.DataFrame(rows)
    # Per-tier rho is a pooled recovery RATE over all samples in the tier
    # (rho_context = recovered/n per fact, n constant), so the Wilson CI uses
    # k = total recovered samples, N = total samples across the tier's facts.
    by_tier = {}
    for r in reasoners:
        by_tier[r] = {}
        for t in TIER_ORDER:
            sub = df[(df.reasoner == r) & (df.tier == t)]
            k = int((sub["rho_context"] * sub["n"]).round().sum())   # recovered samples
            n_samp = int(sub["n"].sum())                             # total samples in tier
            rho_ci = wilson_ci(k, n_samp)
            by_tier[r][t] = {
                "rho": round(float(sub["rho_context"].mean()), 3),
                "rho_ci95": [round(rho_ci[0], 4), round(rho_ci[1], 4)],
                "base": round(float(sub["rho_baserate"].mean()), 3),
                "lift": round(float(sub["context_lift"].mean()), 3),
            }

    # mid-tier tolerance sweep: re-score logged numeric answers (free)
    fact_by_id = {f["id"]: f for f in facts}
    sweep = {r: {} for r in reasoners}
    for r in reasoners:
        mid = [row for row in rows if row["reasoner"] == r and row["tier"] == "mid"]
        for tol in SWEEP_TOLS:
            hits = tot = 0
            for row in mid:
                dvals = normalize_values(fact_by_id[row["fact_id"]].get("delete_value"))
                for ans in row["answers_context"]:
                    hits += int(numeric_recovered(dvals, ans, tol)); tot += 1
            sweep[r][f"tol_{int(tol*100)}pct"] = round(hits / tot, 3) if tot else 0.0

    # high-tier refusal audit
    refusal_flags = [{"fact_id": row["fact_id"], "reasoner": row["reasoner"],
                      "refusals": row["refusals"], "n": row["n"]}
                     for row in rows if row["tier"] == "high" and row["refusals"] > 0]

    # pipeline + certificate (worst modeled adversary: max rho over reasoners, Def. 4)
    adapter = __import__("systems.mem0_adapter", fromlist=["Mem0Adapter"]).Mem0Adapter()
    injector, deleter, exact = Injector(adapter), Deleter(adapter), ExactMatchProbe()
    cert_rows = []
    for f in facts:
        rho = max(rho_by_fact[f["id"]].values())  # worst (highest) modeled adversary, Def. 4
        del_vals = normalize_values(f.get("delete_value", f["probe_value"]))
        uid = f"{config.USER_ID_PREFIX}_rho_{f['id']}"
        adapter.delete_all_memories(uid)
        injector.inject_many(uid, [f], infer=False, settle_seconds=0.0)
        deleter.delete_value_rows(uid, del_vals)
        residual = 1.0 if exact.run(adapter, uid, {**f, "probe_value": del_vals}).recoverable else 0.0
        final = max(residual, rho)
        cert = make_certificate(
            fact=f, system="mem0", residual=residual, rederivation=0.0, rho=rho,
            probe_scores={"residual_after_delete": residual, "parametric_rho": rho},
            heuristic="delete target; rho is the irreducible floor (co-deletion cannot lower it)",
            facts_co_deleted=[], final_recoverability=final,
            probe_battery=["exact_match", "parametric_rho"])
        save_certificate(cert)
        cert_rows.append({"fact_id": f["id"], "tier": f["tier"], "rho": round(rho, 3),
                          "residual_after_delete": residual, "status": cert.status,
                          "certified_complete": cert.completeness_certified})
        if not args.keep:
            adapter.delete_all_memories(uid)

    # ---- report by MEASURED rho (worst adversary), not the authored hypothesis tier.
    # Surfaces (a) hypothesis-vs-measured tier mismatch and (b) the bimodality: the
    # contested "mid" band is nearly empty -> rho is effectively {~0, >=0.5}. The
    # authored-tier view (rho_by_tier) is kept above; this is the measured view.
    def _measured_tier(rho_val: float) -> str:
        if rho_val <= config.TAU:
            return "low"            # rho <= tau -> certifiable floor (~0)
        if rho_val >= 0.5:
            return "high"           # rho >= 0.5 -> hard floor
        return "mid"                # tau < rho < 0.5 -> the contested middle band
    measured_bins = {t: {"n": 0, "certifiable": 0, "fact_ids": []} for t in TIER_ORDER}
    hyp_vs_measured = {"mismatch": 0, "n": len(cert_rows), "mismatched_fact_ids": []}
    for c in cert_rows:
        mt = _measured_tier(c["rho"])
        measured_bins[mt]["n"] += 1
        measured_bins[mt]["certifiable"] += int(c["certified_complete"])
        measured_bins[mt]["fact_ids"].append(c["fact_id"])
        if mt != c["tier"]:
            hyp_vs_measured["mismatch"] += 1
            hyp_vs_measured["mismatched_fact_ids"].append(c["fact_id"])
    n_mid = measured_bins["mid"]["n"]
    bimodality = {"rho_le_tau": measured_bins["low"]["n"], "rho_ge_0.5": measured_bins["high"]["n"],
                  "rho_in_mid_band": n_mid, "n": len(cert_rows),
                  "is_bimodal": n_mid <= max(1, round(0.1 * len(cert_rows)))}

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base_p = config.RESULTS_DIR / f"exp07_rho_gradient_{stamp}"
    df.drop(columns=["answers_context", "answers_baserate"]).to_csv(base_p.with_suffix(".csv"), index=False)
    n_false = sum(not c["certified_complete"] for c in cert_rows)
    # Headline certifiable rate (X/N facts certified complete) -> Wilson CI.
    n_certifiable = sum(c["certified_complete"] for c in cert_rows)
    n_total = len(cert_rows)
    cert_ci = wilson_ci(n_certifiable, n_total)
    base_p.with_suffix(".json").write_text(json.dumps(
        {"experiment": "exp07_rho_gradient", "timestamp_utc": stamp, "tau": config.TAU,
         "n_samples": args.n_samples, "reasoners": reasoners, "scoring": "_recovered (probe_value union judge); mid sweep = numeric tolerance",
         "certifiable_complete": n_certifiable, "n_certificates": n_total,
         "certifiable_rate": round(n_certifiable / n_total, 3) if n_total else 0.0,
         "certifiable_rate_ci95": [round(cert_ci[0], 4), round(cert_ci[1], 4)],
         "rho_by_tier": by_tier, "rho_by_measured_bin": measured_bins,
         "hypothesis_vs_measured": hyp_vs_measured, "bimodality": bimodality,
         "mid_tolerance_sweep": sweep, "refusal_flags": refusal_flags,
         "certificates": cert_rows, "rows_with_logged_answers": rows}, indent=2, default=str))

    print("\n" + "=" * 70)
    print("  EXP07 — PARAMETRIC FLOOR rho (context vs base-rate, by tier)")
    print("=" * 70)
    for r in reasoners:
        print(f"  {r}:")
        for t in TIER_ORDER:
            s = by_tier[r][t]
            lo, hi = s["rho_ci95"]
            print(f"    {t:4s}: rho={s['rho']:.2f} [{lo:.2f},{hi:.2f}]  "
                  f"base-rate={s['base']:.2f}  context-lift={s['lift']:+.2f}")
        print(f"    mid tolerance sweep: " + "  ".join(
            f"{k.replace('tol_','').replace('pct','%')}={v:.2f}" for k, v in sweep[r].items()))
    if refusal_flags:
        print("\n  HIGH-tier refusals (rho = adversarial lower bound there):")
        for fl in refusal_flags:
            print(f"    {fl['fact_id']} [{fl['reasoner'].split('-')[0]}]: {fl['refusals']}/{fl['n']} refused")
    print(f"\n  tau={config.TAU}  ->  NOT certified-complete (rho>tau, limit result): {n_false}/{len(cert_rows)}")
    print(f"  certifiable-complete (rho<=tau)        : {n_certifiable}/{n_total} "
          f"[{cert_ci[0]:.0%}, {cert_ci[1]:.0%}]")
    print(f"\n  MEASURED-rho binning (worst adversary, n={len(cert_rows)} facts):")
    for mt in TIER_ORDER:
        b = measured_bins[mt]
        print(f"    {mt:4s}: n={b['n']:2d}  certifiable={b['certifiable']:2d}  fact_ids={b['fact_ids']}")
    print(f"  hypothesis tier != measured tier   : {hyp_vs_measured['mismatch']}/{hyp_vs_measured['n']} facts")
    print(f"  bimodality (mid band ~empty)       : rho<=tau:{bimodality['rho_le_tau']}  "
          f"mid:{bimodality['rho_in_mid_band']}  rho>=0.5:{bimodality['rho_ge_0.5']}  "
          f"is_bimodal={bimodality['is_bimodal']}")
    print(f"  Results: {base_p.with_suffix('.csv')}  (answers logged in .json for free re-scoring)")
    if ckpt_p.exists():
        ckpt_p.unlink()   # completed successfully -> drop the resume checkpoint


if __name__ == "__main__":
    main()
