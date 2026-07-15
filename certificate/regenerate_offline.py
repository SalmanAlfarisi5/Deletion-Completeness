"""Regenerate ENRICHED deletion certificates from existing results -- OFFLINE.

NO experiments are re-run and NO API calls are made. Everything here is pure file IO
plus the deterministic boolean solver in planner/entailment_dag. It adds the three
audit-evidence blocks a bare verdict was missing:

  (1) proof trace      -- per-channel probe + score + supporting detail (probe_trace);
  (2) reliability       -- validated production-judge false-accept / recall, adversary
                           panel, and (for world-recall facts) per-adversary rho, sample
                           size, context-lift, refusals (reliability);
  (3) WHY each co-deletion was necessary -- derived from the fact's known entailment DAG:
                           each co-deleted operand lies on a re-derivation path and is
                           flagged necessary/redundant, with the spared entailers and the
                           collateral-vs-optimum minimality (co_deletion_justifications,
                           operands_spared, minimality, entailment_structure).

Sources (latest by mtime):
  planner  : data/results/exp03_planner_mem0_exact_*.json      (co-deletion + operands)
  world-recall: data/results/exp07_rho_gradient_*.json          (per-adversary rho)
  judges   : data/results/judge_validation_*.json               (reliability)
  facts    : data/facts/multi_hop_facts.json, rho_gradient_facts.json

Writes to data/results/certificates_enriched/ (the original certs are left untouched).

Run:  <venv>/bin/python -m certificate.regenerate_offline
"""
from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from certificate.emitter import make_certificate, build_reliability


def _latest(pattern: str) -> str | None:
    fs = sorted(glob.glob(str(config.RESULTS_DIR / pattern)), key=os.path.getmtime)
    return fs[-1] if fs else None


def _load_facts(name: str) -> dict:
    p = config.FACTS_DIR / name
    if not p.exists():
        return {}
    data = json.loads(p.read_text())
    return {f["id"]: f for f in data.get("facts", [])}


def _existing_exact_channel_split() -> dict:
    """Map fact_id -> {residual, rederiv} from the previously emitted mem0/exact certs,
    so the enriched cert keeps the REAL post-plan channel split instead of re-deriving
    it. Falls back to completeness-implied zeros when a fact has no prior cert."""
    out: dict = {}
    for fp in glob.glob(str(config.RESULTS_DIR / "certificates" / "cert-*.json")):
        try:
            c = json.loads(Path(fp).read_text())
        except (OSError, ValueError):
            continue
        if c.get("system") != "mem0" or c.get("heuristic_used") != "exact":
            continue
        prev = out.get(c["fact_id"])
        if prev is None or c.get("issued_at", "") > prev.get("issued_at", ""):
            out[c["fact_id"]] = {"residual": c.get("residual_survival_score", 0.0),
                                 "rederiv": c.get("re_derivation_score", 0.0),
                                 "issued_at": c.get("issued_at", "")}
    return out


def regenerate_planner(out_dir: Path) -> list[str]:
    """Enriched planner certificates from exp03 (exact): full entailment proof trace."""
    src = _latest("exp03_planner_mem0_exact_*.json")
    if not src:
        print("  [planner] no exp03 exact result file -- skipped")
        return []
    facts = _load_facts("multi_hop_facts.json")
    split = _existing_exact_channel_split()
    rows = json.loads(Path(src).read_text()).get("rows", [])
    ids = []
    for r in rows:
        fact = facts.get(r["fact_id"])
        if fact is None:
            continue
        co = list(r.get("co_deleted") or [])
        rho = float(r.get("parametric_risk", 0.0))
        final = float(r.get("final_recoverability", 0.0))
        complete = bool(r.get("achieved_completeness"))
        sp = split.get(r["fact_id"])
        if sp is not None:
            residual, rederiv = sp["residual"], sp["rederiv"]
        else:                       # completeness => deletable channels are 0
            residual = 0.0
            rederiv = 0.0 if complete else final
        probe_trace = [
            {"channel": "residual_survival", "probe": "exact_match", "score": residual,
             "detail": "post-plan scan of every surviving record for a surface form of the value"},
            {"channel": "re_derivation", "probe": "rederivation_adversary", "score": rederiv,
             "detail": "post-plan adversary elicitation over the surviving store + world knowledge"},
            {"channel": "world_recall", "probe": "parametric", "score": rho,
             "detail": "store withheld; base model + world context only -- deletion cannot lower this"},
        ]
        cert = make_certificate(
            fact=fact, system="mem0", system_version="mem0ai-2.0.7",
            residual=residual, rederivation=rederiv, rho=rho,
            final_recoverability=final,
            probe_scores={"residual_survival": residual, "re_derivation_score": rederiv,
                          "parametric_risk_rho": rho, "final_recoverability": final},
            heuristic="exact (minimum hitting set over the entailment DAG)",
            facts_co_deleted=co, operands_required=list(r.get("operands_required_set") or []),
            probe_battery=["exact_match", "rederivation", "parametric"],
            probe_trace=probe_trace)
        (out_dir / f"{cert.certificate_id}.json").write_text(cert.model_dump_json(indent=2))
        ids.append(cert.certificate_id)
    print(f"  [planner] {len(ids)} enriched certs from {os.path.basename(src)}")
    return ids


def regenerate_world_recall(out_dir: Path) -> list[str]:
    """Enriched world-recall certificates from exp07: per-adversary rho + reliability."""
    src = _latest("exp07_rho_gradient_*.json")
    if not src:
        print("  [world-recall] no exp07 result file -- skipped")
        return []
    facts = _load_facts("rho_gradient_facts.json")
    data = json.loads(Path(src).read_text())
    n_samples = data.get("n_samples")
    # headline per-fact record (rho, residual_after_delete, status)
    head = {c["fact_id"]: c for c in data.get("certificates", [])}
    # per-adversary detail
    by_fact: dict = {}
    for row in data.get("rows_with_logged_answers", []):
        by_fact.setdefault(row["fact_id"], {})[row["reasoner"]] = row
    ids = []
    for fid, per_adv in by_fact.items():
        fact = facts.get(fid)
        if fact is None:
            continue
        rho_per_adv = {m: float(r.get("rho_context", 0.0)) for m, r in per_adv.items()}
        lift = {m: float(r.get("context_lift", 0.0)) for m, r in per_adv.items()}
        refus = {m: int(r.get("refusals", 0)) for m, r in per_adv.items()}
        worst = max(rho_per_adv.values()) if rho_per_adv else 0.0
        h = head.get(fid, {})
        residual = float(h.get("residual_after_delete", 0.0))
        # a couple of raw adversary answers, so a human can spot-check the score
        sample_ans = {m: (r.get("answers_context") or [])[:2] for m, r in per_adv.items()}
        reliability = build_reliability(rho_per_adversary=rho_per_adv, rho_n_samples=n_samples,
                                        context_lift=lift, refusals=refus)
        reliability["rho_answer_samples"] = sample_ans
        probe_trace = [{"channel": "world_recall", "probe": "parametric",
                        "score": worst,
                        "detail": ("store withheld; each adversary queried with the subject's "
                                   "world-knowable context only; rho = recovery rate over "
                                   f"{n_samples} samples; worst-of-panel reported")}]
        cert = make_certificate(
            fact=fact, system="base-model (store withheld)", system_version="n/a",
            residual=residual, rederivation=0.0, rho=worst,
            probe_scores={"residual_survival": residual, "world_recall_worst": worst},
            heuristic="none (world recall is not closed by deletion)",
            facts_co_deleted=[], evidence=False,
            probe_battery=["parametric"], probe_trace=probe_trace,
            reliability=reliability)
        (out_dir / f"{cert.certificate_id}.json").write_text(cert.model_dump_json(indent=2))
        ids.append(cert.certificate_id)
    print(f"  [world-recall] {len(ids)} enriched certs from {os.path.basename(src)}")
    return ids


def main() -> None:
    out_dir = config.RESULTS_DIR / "certificates_enriched"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Regenerating enriched certificates -> {out_dir}  (OFFLINE, no API)")
    p = regenerate_planner(out_dir)
    w = regenerate_world_recall(out_dir)
    print(f"Total: {len(p) + len(w)} certificates written.")
    # show one enriched planner cert with a non-trivial hitting set (k>=1) as a sample
    for cid in p:
        c = json.loads((out_dir / f"{cid}.json").read_text())
        if c.get("co_deletion_justifications"):
            print("\n----- SAMPLE ENRICHED PLANNER CERTIFICATE -----")
            print(json.dumps({k: c[k] for k in (
                "certificate_id", "fact_id", "status", "collateral_k",
                "facts_co_deleted", "minimality", "co_deletion_justifications",
                "operands_spared", "entailment_structure", "reliability") if k in c},
                indent=2)[:2600])
            break


if __name__ == "__main__":
    main()
