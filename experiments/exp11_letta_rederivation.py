"""Experiment 11 — re-derivation & co-deletion on Letta/MemGPT (THIRD-system row).

Consistency pass for the re-derivation channel already shown on Mem0 (exp04):
a target whose own value is gone can still be RE-DERIVED from surviving operand
facts, and co-deleting those operands collapses recovery to the parametric floor.
Running the SAME operands-only control on Letta fills the third row of the
re-derivation table so the result is system-general.

Mirrors exp04 exactly so the rows are directly comparable:
  - inject ONLY the operands (never the target's own value), so residual survival
    = 0 by construction (this IS the post-deletion state). Residual is checked
    with the NARROW `delete_value` (not the broad recovery `probe_value`), so an
    operand that merely shares a surface form with the target is not miscounted.
  - re-derivation probe (adversary reads the surviving store + world knowledge) ->
    the leak. Re-derivation is reasoner-dependent, so we run >= 2 reasoners and
    BIN by mechanism (stored / stored+world), never aggregating across bins.
  - co-delete the operands -> re-derivation should fall to the parametric floor.
  - parametric rho probe (model alone) -> the floor.

LETTA-SPECIFIC, and the CRITICAL CONTROL (so this does not contaminate exp10):
  * operands live in ARCHIVAL passages (Letta's vector store); we capture each
    passage id at seed time and co-delete BY ID through the DIRECT op
    (`passages.delete`), NOT a conversational `agent_forget`. exp10 showed the
    agent-mediated path is surface-incomplete under vague phrasing; here every
    delete is deterministic, and we VERIFY each operand passage is actually gone
    (`faithful_codelete`). So "re-derivation closed" cannot be confounded with
    "the delete silently didn't execute".
  * the agent's human core block is seeded with the user's identity ("The user's
    name is <owner>"). The default block, "(no information about the user yet)",
    otherwise lands in the adversary's notes and suppresses recovery of facts
    phrased about "the user" (F040/F043) for reasons unrelated to re-derivability.

Usage:  python experiments/exp11_letta_rederivation.py --n 6 -v
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402
from tqdm import tqdm  # noqa: E402

import config  # noqa: E402
from certificate.emitter import make_certificate, save_certificate  # noqa: E402
from pipeline.deleter import Deleter  # noqa: E402
from pipeline.injector import load_facts  # noqa: E402
from probes.base_probe import normalize_values  # noqa: E402
from probes.exact_match import ExactMatchProbe  # noqa: E402
from probes.parametric_probe import ParametricProbe  # noqa: E402


def bin_of(fact: dict) -> int:
    return {"stored": 1, "stored+world": 2, "world": 3}.get(
        fact.get("rederivation_basis", "stored+world"), 2)


def main() -> None:
    ap = argparse.ArgumentParser(description="Letta re-derivation & parametric floor")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--bystanders", type=int, default=3)
    ap.add_argument("--single", action="store_true", help="primary reasoner only (cheaper)")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()
    if config.validate():
        raise SystemExit("Config not ready:\n  - " + "\n  - ".join(config.validate()))

    mh = json.loads((config.FACTS_DIR / "multi_hop_facts.json").read_text())
    owner = mh.get("_meta", {}).get("account_owner", "the user")
    targets = mh["facts"][: args.n]
    context = load_facts(config.FACTS_DIR / "context_facts.json")
    ctx_by_id = {c["id"]: c for c in context}
    bystanders = [c for c in context if c.get("role") == "bystander"][: args.bystanders]
    reasoners = [config.REASONER_MODEL] if args.single else [config.REASONER_MODEL, config.SECOND_MODEL]

    from systems.letta_adapter import LettaAdapter
    adapter = LettaAdapter()
    deleter, exact = Deleter(adapter), ExactMatchProbe()
    print(f"system = letta-0.16.8 | reasoners = {reasoners} | user identity = {owner!r}")

    rows, certs = [], []
    for reasoner in reasoners:
        param = ParametricProbe(model=reasoner)
        for fact in tqdm(targets, desc=reasoner):
            entailing = [ctx_by_id[c] for c in fact.get("co_delete_required", []) if c in ctx_by_id]
            del_vals = normalize_values(fact.get("delete_value", fact["probe_value"]))
            target_exact = {**fact, "probe_value": del_vals}
            uid = f"{config.USER_ID_PREFIX}_lettamh_{fact['id']}_{abs(hash(reasoner)) % 9999}"
            adapter.delete_all_memories(uid)

            # The agent knows who its user is (identity, NOT the deleted value).
            adapter.set_core_block(uid, "human", f"The user's name is {owner}.")

            # CONTROL: seed operands only (never the target value), in archival;
            # capture passage ids so co-deletion is by-id and faithful.
            op_pids: dict[str, list[str]] = {}
            for c in entailing + bystanders:
                op_pids[c["id"]] = adapter.archival_insert(uid, c["text"])

            contaminated = exact.run(adapter, user_id=uid, fact=target_exact).recoverable
            residual = 1.0 if contaminated else 0.0  # should be 0 (target never stored)

            red_operands = param.run_rederivation(adapter, uid, fact).score   # the leak
            rho = param.run_parametric(fact).score                            # the floor

            # Co-delete operands by captured passage id -> DIRECT passages.delete.
            codel_ids = [pid for c in entailing for pid in op_pids.get(c["id"], [])]
            deleter.delete_records(uid, codel_ids)
            gone = deleter.verify_deleted(uid, codel_ids)
            faithful_codelete = all(gone.values()) if gone else True
            bys_ids = [pid for c in bystanders for pid in op_pids.get(c["id"], [])]
            bystanders_intact = not any(deleter.verify_deleted(uid, bys_ids).values()) if bys_ids else True
            co_deleted = [c["id"] for c in entailing
                          if all(gone.get(pid, False) for pid in op_pids.get(c["id"], []))]

            red_after = param.run_rederivation(adapter, uid, fact).score
            final = max(residual, red_after, rho)
            row = {"reasoner": reasoner, "fact_id": fact["id"], "bin": bin_of(fact),
                   "basis": fact.get("rederivation_basis"), "contaminated": contaminated,
                   "residual_survival": residual, "rederiv_with_operands": red_operands,
                   "rho": rho, "rederiv_after_codelete": red_after,
                   "final_recoverability": final, "collateral_k": len(co_deleted),
                   "faithful_codelete": faithful_codelete, "bystanders_intact": bystanders_intact}
            rows.append(row)
            if args.verbose:
                tqdm.write(f"  [{fact['id']} bin{row['bin']}] {reasoner.split('-')[0]}: "
                           f"residual={residual:.0f} leak(operands)={red_operands:.0f} "
                           f"rho={rho:.0f} after_codelete={red_after:.0f} "
                           f"faithful={faithful_codelete} bys_intact={bystanders_intact}")

            if reasoner == config.REASONER_MODEL:    # one cert per fact (primary reasoner)
                cert = make_certificate(
                    fact=fact, system="letta", residual=residual, rederivation=red_after, rho=rho,
                    probe_scores={"residual_survival": residual,
                                  "rederiv_with_operands": red_operands, "rho": rho,
                                  "rederiv_after_codelete": red_after},
                    heuristic="operands-only control + faithful (direct) co-delete of operands",
                    facts_co_deleted=co_deleted, final_recoverability=final,
                    probe_battery=["exact_match", "rederivation", "parametric"],
                    system_version="letta-0.16.8")
                save_certificate(cert)
                certs.append(cert.certificate_id)
            if not args.keep:
                adapter.delete_all_memories(uid)

    df = pd.DataFrame(rows)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = config.RESULTS_DIR / f"exp11_letta_rederivation_{stamp}"
    df.to_csv(base.with_suffix(".csv"), index=False)

    summary = defaultdict(dict)
    for (r, b), g in df.groupby(["reasoner", "bin"]):
        summary[r][f"bin{b}"] = {
            "n": len(g),
            "rederiv_with_operands": round(g["rederiv_with_operands"].mean(), 3),
            "rederiv_after_codelete": round(g["rederiv_after_codelete"].mean(), 3),
            "rho": round(g["rho"].mean(), 3),
            "residual_survival": round(g["residual_survival"].mean(), 3),
        }
    metrics = {"faithful_codelete_rate": round(float(df["faithful_codelete"].mean()), 3),
               "bystanders_intact_rate": round(float(df["bystanders_intact"].mean()), 3)}
    base.with_suffix(".json").write_text(json.dumps(
        {"experiment": "exp11_letta_rederivation", "timestamp_utc": stamp, "system": "letta-0.16.8",
         "design": "operands-only control + faithful direct co-delete", "reasoners": reasoners,
         "judge_model": config.JUDGE_MODEL, "user_identity": owner, "metrics": metrics,
         "per_reasoner_bin": summary, "rows": rows, "certificates": certs}, indent=2, default=str))

    print("\n" + "=" * 70)
    print("  EXP11 — LETTA/MemGPT RE-DERIVATION (operands-only control), reasoner x bin")
    print("=" * 70)
    print("  bin1=stored-alone  bin2=stored+world   (residual=0 by construction)")
    for r in reasoners:
        print(f"\n  reasoner = {r}")
        for b in sorted(summary[r]):
            s = summary[r][b]
            print(f"    {b} (n={s['n']}): leak(operands)={s['rederiv_with_operands']:.0%}  "
                  f"after co-delete={s['rederiv_after_codelete']:.0%}  rho={s['rho']:.0%}  "
                  f"residual={s['residual_survival']:.0%}")
    print(f"\n  Faithful (direct) co-delete : {metrics['faithful_codelete_rate']:.0%}  (want 100% — the control)")
    print(f"  Bystanders left intact      : {metrics['bystanders_intact_rate']:.0%}  (want 100%)")
    print(f"\n  Certificates: {config.RESULTS_DIR / 'certificates'}   Results: {base.with_suffix('.csv')}")


if __name__ == "__main__":
    main()
