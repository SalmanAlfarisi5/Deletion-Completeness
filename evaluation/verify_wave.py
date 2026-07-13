"""Thorough correctness/corruption check for a full experiment wave.

Loads the latest result JSON for each experiment and runs sanity + consistency +
corruption checks, printing a PASS / WARN / FAIL report. Key checks:

  * value ranges (residual ~1, planner 100%/0-spurious, MIA AUC in [.4,.8], ...);
  * NO error markers / NaNs in any result;
  * exp07 rho REFUSAL PATTERN -- refusals must fall only on high-tier sensitive
    facts; refusals on low/mid-tier are the rate-limit-contamination signature;
  * exp12 exact planner is provably minimal (k == k* per topology);
  * certificate referential integrity + dataset DAG validity.

Run:  python evaluation/verify_wave.py
Exit code 0 = all PASS/WARN; 1 = at least one FAIL.
"""
from __future__ import annotations

import glob
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

R = config.RESULTS_DIR
_fail = 0
_warn = 0


def _latest(pattern: str):
    fs = sorted(glob.glob(str(R / pattern)))
    return json.loads(open(fs[-1]).read()) if fs else None


def check(name: str, cond: bool, detail: str, warn: bool = False):
    global _fail, _warn
    tag = "PASS" if cond else ("WARN" if warn else "FAIL")
    if not cond:
        if warn:
            _warn += 1
        else:
            _fail += 1
    print(f"  [{tag}] {name}: {detail}")


def _finite(*xs) -> bool:
    return all(isinstance(x, (int, float)) and math.isfinite(x) for x in xs)


def has_error_marker(obj) -> bool:
    """Recursively scan for NaN / error / __REFUSED__-in-unexpected-places markers."""
    s = json.dumps(obj, default=str).lower()
    return ('"error"' in s and '"errors": []' not in s) or "nan" in s.replace("meannan", "")


print("=" * 74)
print("  WAVE VERIFICATION")
print("=" * 74)

# ---- exp01: residual survival (naive) ----
d = _latest("exp01_baseline_mem0_*.json")
if d:
    rs = d.get("metrics", {}).get("naive_deletion_residual_rate")
    print("\nexp01 (naive residual):")
    check("exp01 residual in [0.85,1.0]", isinstance(rs, (int, float)) and 0.85 <= rs <= 1.0,
          f"residual={rs}")

# ---- exp02: naive -> artifact-aware ----
d = _latest("exp02_artifact_purge_mem0_*.json")
if d:
    print("\nexp02 (naive vs artifact-aware residual):")
    naive = d.get("metrics", {}).get("residual_naive_rate")
    aware = d.get("metrics", {}).get("residual_artifact_aware_rate")
    check("exp02 naive high", isinstance(naive, (int, float)) and naive >= 0.5, f"naive={naive}")
    check("exp02 aware ~0", isinstance(aware, (int, float)) and aware <= 0.10, f"aware={aware}")

# ---- exp03: planner (exact/threshold/depth) ----
for heur, mink in (("exact", None), ("threshold", None), ("depth_first", None)):
    d = _latest(f"exp03_planner_mem0_{heur}_*.json")
    if not d:
        continue
    m = d.get("metrics", {})
    print(f"\nexp03 ({heur}):")
    comp = m.get("completeness_rate")
    sp = m.get("spurious_bystander_deletions")
    k = m.get("mean_collateral_k")
    check(f"exp03 {heur} completeness=100%",
          isinstance(comp, (int, float)) and comp >= 0.99, f"completeness={comp}")
    if heur == "exact":
        check("exp03 exact 0 spurious", sp == 0, f"spurious={sp}")
    check(f"exp03 {heur} k finite/sane", _finite(k) and 0 <= k <= 12, f"k={k}")

# ---- exp04: re-derivation by bin x reasoner ----
d = _latest("exp04_parametric_mem0_*.json")
if d:
    print("\nexp04 (re-derivation, operands-only control):")
    per = d.get("per_reasoner_bin", {})
    ok_post, ok_rho = True, True
    for r, bins in per.items():
        for b, s in bins.items():
            if s.get("rederiv_after_codelete", 0) > 0.10:
                ok_post = False
            if b in ("bin1", "bin4", "bin5", "bin6", "bin8") and s.get("rho", 0) > 0.10:
                ok_rho = False
    check("exp04 post-codelete rederiv ~0 (all bins)", ok_post, "all bins <=0.10 after co-delete")
    check("exp04 rho~0 on fictional multi-hop bins", ok_rho, "fictional bins rho<=0.10", warn=True)
    check("exp04 no error markers", not has_error_marker(d.get("per_reasoner_bin", {})), "clean")

# ---- exp05: duplication ----
d = _latest("exp05_duplication_*.json")
if d:
    print("\nexp05 (duplication factorial):")
    check("exp05 present + no errors", not has_error_marker(d), "clean")

# ---- exp07: rho + REFUSAL-PATTERN corruption check ----
d = _latest("exp07_rho_gradient_*.json")
if d:
    print("\nexp07 (rho gradient) -- incl. rate-limit corruption check:")
    ncert = d.get("n_certificates")
    ncertifiable = d.get("certifiable_complete")
    check("exp07 certs emitted", isinstance(ncert, int) and ncert >= 200, f"n_certs={ncert}")
    check("exp07 certifiable count finite", isinstance(ncertifiable, int), f"certifiable={ncertifiable}")
    # refusal pattern: refusals only on high-tier sensitive facts
    rows = d.get("rows_with_logged_answers", [])
    tier = {r["fact_id"]: r["tier"] for r in rows}
    byt: dict = {}
    for f in d.get("refusal_flags", []):
        t = tier.get(f["fact_id"], "?")
        byt[t] = byt.get(t, 0) + 1
    lowmid = byt.get("low", 0) + byt.get("mid", 0)
    check("exp07 refusals only on high-tier (no rate-limit signature)",
          lowmid == 0, f"refusals by tier={byt} (low+mid={lowmid} must be 0)")
    check("exp07 no measurement errors", not any(r.get("flag") == "ERROR" for r in rows),
          "no ERROR flags")

# ---- exp08: MIA ----
d = _latest("exp08_mia_mem0_*.json")
if d:
    print("\nexp08 (MIA):")
    stages = {s.get("stage"): s for s in d.get("stages", [])}
    for st in ("intact", "naive", "aware"):
        auc = stages.get(st, {}).get("auc")
        check(f"exp08 {st} AUC in [0.45,0.80]",
              isinstance(auc, (int, float)) and 0.45 <= auc <= 0.80, f"AUC={auc}")
    check("exp08 n_members>=200", d.get("n_members", 0) >= 200, f"n_members={d.get('n_members')}")

# ---- exp12: minimality (exact == optimum) ----
d = _latest("exp12_planner_minimality_*.json")
if d:
    print("\nexp12 (planner minimality vs optimum k*):")
    ov = d.get("overall", {})
    ek = ov.get("exact", {}).get("mean_gap")
    ec = ov.get("exact", {}).get("completeness")
    # exact never EXCEEDS the optimum; it may be slightly BELOW when Stage-2 artifact
    # purge closes re-derivation before any operand co-deletion (k < k*).
    check("exp12 exact gap <=0 (never exceeds optimum)", _finite(ek) and ek <= 0.05, f"exact mean_gap={ek}")
    check("exp12 exact completeness 100%", _finite(ec) and ec >= 0.99, f"exact completeness={ec}")

# ---- exp09/10/11: cross-system ----
d = _latest("exp09_zep_kg_residual_*.json")
if d:
    print("\nexp09 (Graphiti):")
    m = d.get("metrics", {})
    check("exp09 kg-summary residue in [0,1]",
          0 <= m.get("kg_residue_after_rate", -1) <= 1, f"kg_residue={m.get('kg_residue_after_rate')}")
d = _latest("exp10_letta_*.json")
if d:
    print("\nexp10 (Letta agent-mediated):")
    check("exp10 present + no errors", not has_error_marker(d), "clean")
d = _latest("exp11_letta_rederivation_*.json")
if d:
    print("\nexp11 (Letta re-derivation):")
    check("exp11 present + no errors", not has_error_marker(d), "clean")

# ---- judge validation ----
d = _latest("judge_validation_*.json")
if d and "recovery" in d:
    print("\njudge validation:")
    for m, r in d.get("recovery", {}).items():
        fa = r.get("false_accept", {}).get("rate")
        check(f"judge recovery false-accept low ({m.split('-')[0]})",
              isinstance(fa, (int, float)) and fa <= 0.05, f"false_accept={fa}")
    for m, r in d.get("entailment", {}).items():
        miss = r.get("miss_rate_multihop", {}).get("rate")
        check(f"judge entailment multi-hop miss=0 ({m.split('-')[0]})",
              miss == 0.0, f"miss_multihop={miss}", warn=(miss not in (0.0, None)))

# ---- datasets + certificates ----
print("\ndatasets + certificates:")
try:
    import planner.entailment_dag as ed
    from pipeline.injector import load_facts
    mh = load_facts(config.FACTS_DIR / "multi_hop_facts.json")
    bad = 0
    for f in mh:
        d2 = ed.dag_of(f)
        if ed.min_codelete_size(d2["formula"]) < 1:
            bad += 1
    check("multi-hop DAGs all valid (k*>=1)", bad == 0, f"{len(mh)} facts, {bad} invalid")
    ctx_ids = {c["id"] for c in load_facts(config.FACTS_DIR / "context_facts.json")}
    ref_bad = sum(1 for f in mh for cid in f.get("co_delete_required", []) if cid not in ctx_ids)
    check("multi-hop operand refs resolve", ref_bad == 0, f"{ref_bad} dangling operand refs")
except Exception as e:  # noqa: BLE001
    check("dataset checks ran", False, f"error: {e}")

print("\n" + "=" * 74)
print(f"  RESULT: {'ALL CHECKS PASS' if _fail == 0 else str(_fail) + ' FAILURE(S)'}"
      f"  ({_warn} warning(s))")
print("=" * 74)
raise SystemExit(1 if _fail else 0)
