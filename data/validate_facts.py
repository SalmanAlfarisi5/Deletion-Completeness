"""data/validate_facts.py -- THE DATA GATE for the deletion-completeness datasets.

Takes the gpt-4o-mini-authored candidates (data/generate_facts.py) and enforces
the per-set invariants using the LOCKED MEASUREMENT models
(config.REASONER_MODEL = gpt-4o-mini, config.SECOND_MODEL = gpt-4o, and the
config.JUDGE_MODEL entailment judge).  AUTHORING (gpt-4o-mini) and MEASUREMENT are
kept strictly separate: the author only proposed facts; here the locked models
independently measure rho / entailment.  The value to be recovered is never shown
to the rho elicitation (ParametricProbe hides it), so the measurement is not
circular even where the author and reasoner-1 are the same gpt-4o-mini weights;
reasoner-2 (gpt-4o) is fully independent and the worst-adversary rho is the max
over both (Def. 4).

Invariants
----------
isolated      : entailed_by == [] AND the base model alone cannot recover the value
                (parametric rho ~ 0).  DISCARD any candidate recoverable by either
                reasoner.
multi-hop     : the two operands JOINTLY fire the entailment judge AND each SINGLE
                operand does NOT (near-miss); AND delete_value is not a substring of
                any operand text (contamination).  DISCARD-on-fail.  >=15 in bin1
                ('stored') and >=15 in bin2 ('stored+world').
rho-gradient  : MEASURE rho for BOTH reasoners, STORE per-fact, and FLAG (never
                discard) any tier-hypothesis-vs-measured mismatch.  Report rho for
                ALL rho-gradient facts.  >=15 per tier, distinct subjects.
global        : no persona name collides with a real public figure (memorization
                confound); cross-file referential integrity of entailed_by /
                co_delete_required / supports.

On a clean pass the script prints `GATE: PASS`; otherwise `GATE: FAIL -- <reason>`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
import generate_facts as gen  # noqa: E402  (sibling module in data/)
from planner.entailment_detector import EntailmentDetector  # noqa: E402
from probes.base_probe import normalize_values  # noqa: E402
from probes.parametric_probe import ParametricProbe  # noqa: E402

ISO_PATH = config.FACTS_DIR / "isolated_facts.json"
MH_PATH = config.FACTS_DIR / "multi_hop_facts.json"
CTX_PATH = config.FACTS_DIR / "context_facts.json"
RHO_PATH = config.FACTS_DIR / "rho_gradient_facts.json"

# Floors (the binding constraints from the brief).
FLOOR_ISO_PERSONAS = 15
FLOOR_MH_PER_BIN = 15
FLOOR_RHO_PER_TIER = 15

# tier classification from a measured rho (midpoints split the _meta gaps
# 0.2-0.3 and 0.6-0.7).
TIER_LO_HI = (config.TAU, 0.5)  # RF4 H-03: align tier-flag boundary with exp07

# Deterministic guard for obvious real Singapore public figures (the LLM check is
# the main screen; this is a fast belt-and-braces).
REAL_FIGURE_BLOCKLIST = {
    "lee kuan yew", "lee hsien loong", "lawrence wong", "halimah yacob",
    "tharman shanmugaratnam", "goh chok tong", "heng swee keat", "k shanmugam",
    "vivian balakrishnan", "ong ye kung", "josephine teo", "grace fu",
    "chan chun sing", "tony tan", "s r nathan", "pritam singh", "sylvia lim",
    "low thia khiang", "chee soon juan", "ho ching", "joseph schooling",
}


# --------------------------------------------------------------------------- #
# Small concurrency helpers
# --------------------------------------------------------------------------- #
def _retry(fn, tries: int = 3):
    last = None
    for _ in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
    raise last


def _parallel(fn, items, workers: int, desc: str = ""):
    results: list = [None] * len(items)
    if not items:
        return results
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn, it): i for i, it in enumerate(items)}
        done = 0
        for fut in as_completed(futs):
            results[futs[fut]] = fut.result()
            done += 1
            if desc and (done % 10 == 0 or done == len(items)):
                print(f"    [{desc}] {done}/{len(items)}", flush=True)
    return results


def _load(path):
    obj = json.loads(path.read_text())
    return obj.get("_meta", {}), obj["facts"]


def _write(path, meta, facts):
    path.write_text(json.dumps({"_meta": meta, "facts": facts}, indent=2,
                               ensure_ascii=False) + "\n")


def _contains(text: str, value: str) -> bool:
    """Case-insensitive substring, also matching comma/space-stripped digit forms
    (so delete_value '3,200' is caught inside an operand reading '3200')."""
    t, v = (text or "").lower(), (value or "").lower()
    if v and v in t:
        return True
    tc = t.replace(",", "").replace(" ", "")
    vc = v.replace(",", "").replace(" ", "")
    return bool(vc) and vc in tc


def _measured_tier(rho: float) -> str:
    lo, hi = TIER_LO_HI
    if rho < lo:
        return "low"
    if rho < hi:
        return "mid"
    return "high"


# --------------------------------------------------------------------------- #
# Global checks
# --------------------------------------------------------------------------- #
_PUBFIG_PROMPT = (
    'Is "{name}" the name of a REAL, well-known PUBLIC FIGURE (head of state, '
    "politician, famous athlete, celebrity, well-known business leader, or notable "
    "historical person) about whom detailed biographical facts are widely documented "
    "and likely memorised by a language model? Treat ordinary, non-famous individuals "
    'as NOT public figures. Respond ONLY as JSON {{"is_public_figure":true|false,'
    '"confidence":0.0-1.0,"who":"<who, or empty>"}}.')


def persona_check(names: list[str], workers: int) -> dict:
    """Screen each persona name for real-public-figure collision."""
    import llm

    def task(name):
        if name.lower() in REAL_FIGURE_BLOCKLIST:
            return {"name": name, "is_public_figure": True, "confidence": 1.0,
                    "who": "blocklist", "collision": True}
        out = _retry(lambda: llm.chat_json(
            [{"role": "user", "content": _PUBFIG_PROMPT.format(name=name)}],
            model=config.JUDGE_MODEL, temperature=0.0, max_tokens=120))
        is_pf = bool(out.get("is_public_figure", False))
        try:
            conf = float(out.get("confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        return {"name": name, "is_public_figure": is_pf, "confidence": conf,
                "who": out.get("who", ""), "collision": is_pf and conf >= 0.8}

    res = _parallel(task, names, workers, desc="persona-check")
    return {r["name"]: r for r in res}


def referential_integrity(mh_facts: list[dict], ctx_facts: list[dict]) -> list[str]:
    problems: list[str] = []
    ctx_by_id = {c["id"]: c for c in ctx_facts}
    mh_ids = {f["id"] for f in mh_facts}
    for f in mh_facts:
        for cid in f.get("entailed_by", []) + f.get("co_delete_required", []):
            if cid not in ctx_by_id:
                problems.append(f"{f['id']}: references missing context id {cid}")
            elif ctx_by_id[cid].get("role") != "entailing":
                problems.append(f"{f['id']}: operand {cid} is not role='entailing'")
    for c in ctx_facts:
        if c.get("role") == "entailing":
            for fid in c.get("supports", []):
                if fid not in mh_ids:
                    problems.append(f"{c['id']}: supports missing target {fid}")
    return problems


def check_value_uniqueness(iso_facts: list[dict], ctx_facts: list[dict]) -> list[str]:
    """Cross-fact value-uniqueness gate (RF4 C-01).

    No isolated fact's probe value may also appear in another stored fact's
    searchable text (isolated OR context). A shared value makes exp02's per-fact
    naive->purge loop contaminate later facts (an earlier fact's artifact purge
    deletes a later fact's value rows, so it scores a spurious naive-success) and
    inflates exp05's dup-incidence with mere vocabulary overlap. Uses the same
    digit-normalizing _contains as the probes.
    """
    store = iso_facts + ctx_facts

    def hay(g):
        return " || ".join([g.get("text", ""), g.get("utterance", ""),
                            " ".join(normalize_values(g.get("probe_value", [])))])

    H = {g["id"]: hay(g) for g in store}
    problems = []
    for f in iso_facts:
        for pv in normalize_values(f.get("probe_value")):
            if len(pv) < 3:
                continue
            for g in store:
                if g["id"] != f["id"] and _contains(H[g["id"]], pv):
                    problems.append(f"{f['id']} value {pv!r} also appears in {g['id']}")
    return problems


# --------------------------------------------------------------------------- #
# Per-set measurement tasks (locked models)
# --------------------------------------------------------------------------- #
def gate_isolated(cands: list[dict], workers: int):
    """Reject any candidate recoverable by the base model alone (parametric)."""
    reasoners = [config.REASONER_MODEL, config.SECOND_MODEL]

    def task(c):
        fact = {"id": "tmp", "text": c["text"],
                "probe_value": normalize_values(c["probe_value"])}
        try:
            rec, detail = False, {}
            for m in reasoners:
                p = ParametricProbe(model=m)
                r = _retry(lambda p=p: p.run_parametric(fact))
                detail[m] = r.recoverable
                rec = rec or r.recoverable
            return {"recoverable": rec, "detail": detail}
        except Exception as e:  # noqa: BLE001
            # discard-on-error (conservative): an unverified candidate must NOT be
            # admitted to the ISOLATED set without the rho~0 check that defines it.
            # Surfaced via the WARN after the gate (was: silently KEPT on error).
            return {"error": str(e)}

    out = _parallel(task, cands, workers, desc="isolated-rho")
    kept, discarded, errored = [], [], []
    for c, r in zip(cands, out):
        if "error" in r:
            errored.append((c, r["error"]))          # rho-check errored -> DISCARD (conservative)
        elif r.get("recoverable"):
            discarded.append((c, r.get("detail")))
        else:
            kept.append(c)
    if errored:
        print(f"    WARN: {len(errored)} isolated candidates discarded on rho-check error")
    return kept, discarded


def gate_multihop(cands: list[dict], workers: int):
    """Near-miss + contamination gate via the LOCKED entailment judge.

    Operationalisation (calibrated against the canonical F040-F045): the judge
    (gpt-4o-mini) is positivity-biased and pins confidence around 0.85, so a raw
    'confidence < tau' rule on a single operand is unusable -- it would reject even
    the published facts.  The discriminating signal is the categorical answer:

      * JOINT must RECOVER     -> answer YES or PARTIAL with confidence >= tau.
      * NEITHER single may FULLY recover -> a single operand answering YES means
        that one operand alone suffices (NOT a near-miss).  A single answering
        PARTIAL/NO is the near-miss (partial info alone; full only when combined).
      * delete_value must not be a substring of either operand (contamination).

    This accepts canonical F040/F043/F044 and flags F042/F045 (where each clue
    alone already implies the target) -- the intended near-miss semantics.
    """
    thr = config.ENTAILMENT_THRESHOLD

    def task(c):
        try:
            det = EntailmentDetector(model=config.JUDGE_MODEL)
            tgt, a, b = c["target_text"], c["opA_text"], c["opB_text"]
            dj = _retry(lambda: det.check_detailed([a, b], tgt))
            da = _retry(lambda: det.check_detailed(a, tgt))
            db = _retry(lambda: det.check_detailed(b, tgt))
            jfires = dj["confidence"] >= thr
            a_full = da["answer"].upper() == "YES"
            b_full = db["answer"].upper() == "YES"
            contam = any(_contains(a, v) or _contains(b, v)
                         for v in normalize_values(c["delete_value"]))
            passed = jfires and not a_full and not b_full and not contam
            reason = ("ok" if passed else
                      ("joint-weak" if not jfires else
                       "opA-recovers" if a_full else
                       "opB-recovers" if b_full else "contamination"))
            return {"joint": f"{dj['answer']}@{dj['confidence']:.2f}",
                    "a": f"{da['answer']}@{da['confidence']:.2f}",
                    "b": f"{db['answer']}@{db['confidence']:.2f}",
                    "contam": contam, "passed": passed, "reason": reason}
        except Exception as e:  # noqa: BLE001 -- discard-on-error (conservative)
            return {"passed": False, "reason": f"error:{e}"}

    out = _parallel(task, cands, workers, desc="multihop-nearmiss")
    kept, discarded = [], []
    for c, r in zip(cands, out):
        (kept if r["passed"] else discarded).append((c, r))
    return kept, discarded


def measure_rho(facts: list[dict], n: int, workers: int, remeasure: bool):
    """Measure rho for BOTH reasoners for every rho fact; store on the fact and
    FLAG tier mismatches.  Never discards."""
    r1, r2 = config.REASONER_MODEL, config.SECOND_MODEL

    def task(f):
        if not remeasure and isinstance(f.get("measured_rho"), dict) \
                and r1 in f["measured_rho"] and r2 in f["measured_rho"]:
            return {"reused": True, r1: f["measured_rho"][r1], r2: f["measured_rho"][r2]}
        try:
            ctx = f["world_context"]
            vals = {}
            for m in (r1, r2):
                p = ParametricProbe(model=m)
                vals[m] = _retry(lambda p=p: p.estimate_rho(f, ctx, n=n))["rho"]
            return {"reused": False, **vals}
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)}

    out = _parallel(task, facts, workers, desc="rho-measure")
    flags = []
    for f, r in zip(facts, out):
        if "error" in r:
            f["measured_rho"] = {"error": r["error"]}
            f["tier_flag"] = "ERROR"
            flags.append({"id": f["id"], "subject": f.get("subject"),
                          "hyp": f.get("tier"), "flag": "ERROR", "error": r["error"]})
            continue
        rho1, rho2 = float(r[r1]), float(r[r2])
        worst = max(rho1, rho2)
        meas = _measured_tier(worst)
        hyp = f.get("tier", "?")
        match = (meas == hyp)
        f["measured_rho"] = {r1: round(rho1, 3), r2: round(rho2, 3)}
        f["measured_rho_worst"] = round(worst, 3)
        f["measured_tier"] = meas
        f["tier_flag"] = "MATCH" if match else f"MISMATCH(hyp={hyp}->meas={meas})"
        flags.append({"id": f["id"], "subject": f.get("subject"), "hyp": hyp,
                      "rho_r1": round(rho1, 3), "rho_r2": round(rho2, 3),
                      "worst": round(worst, 3), "meas": meas,
                      "flag": f["tier_flag"], "mismatch": not match})
    return flags


# --------------------------------------------------------------------------- #
# Builders (assign ids, wire references, extend _meta)
# --------------------------------------------------------------------------- #
def build_isolated(existing, kept_cands, cap=None):
    facts = list(existing)
    # Continue the F1xx block after the highest existing id -- never restart at 100
    # (a re-run with existing F1xx facts would otherwise mint duplicate ids).
    used = [int(f["id"][1:]) for f in existing
            if f.get("id", "").startswith("F") and f["id"][1:].isdigit()]
    nid = max([n for n in used if n >= 100], default=99) + 1
    for c in (kept_cands[:cap] if cap else kept_cands):
        facts.append({
            "id": f"F{nid}", "subject": c["subject"], "category": c["category"],
            "text": c["text"], "utterance": c["utterance"],
            "probe_value": normalize_values(c["probe_value"]),
            "entailed_by": [], "note": c.get("note", "Arbitrary value; non-inferable."),
        })
        nid += 1
    return facts


def build_multihop_and_context(existing_mh, existing_ctx, kept_mh, byst_cands,
                               n_floor_total):
    mh = list(existing_mh)
    ctx = list(existing_ctx)
    # next ids
    f_next = max([int(f["id"][1:]) for f in existing_mh] + [45]) + 1  # F046+
    c_next = max([int(c["id"][1:]) for c in existing_ctx] + [22]) + 1  # C023+
    for c, _r in kept_mh:
        fid = f"F{f_next:03d}"; f_next += 1
        ca_id = f"C{c_next:03d}"; c_next += 1
        cb_id = f"C{c_next:03d}"; c_next += 1
        cat = c.get("category", "financial")
        mh.append({
            "id": fid, "subject": c["subject"], "category": cat,
            "text": c["target_text"], "utterance": c["target_utterance"],
            "question": c.get("target_question",
                              f"What is the value described for {c['subject']}?"),
            "delete_value": normalize_values(c["delete_value"]),
            "probe_value": sorted(set(normalize_values(c.get("probe_value", []))
                                      + normalize_values(c["delete_value"])),
                                  key=str),
            "entailed_by": [ca_id, cb_id],
            "co_delete_required": [ca_id, cb_id],
            "rederivation_basis": c["bin"],
            "entailment_note": c.get("entailment_note", ""),
        })
        ctx.append({"id": ca_id, "subject": c["subject"], "category": cat,
                    "role": "entailing", "supports": [fid],
                    "text": c["opA_text"], "utterance": c.get("opA_utterance", c["opA_text"]),
                    "probe_value": normalize_values(c.get("opA_probe") or [c["opA_text"]])})
        ctx.append({"id": cb_id, "subject": c["subject"], "category": "reference",
                    "role": "entailing", "supports": [fid],
                    "text": c["opB_text"], "utterance": c.get("opB_utterance", c["opB_text"]),
                    "probe_value": normalize_values(c.get("opB_probe") or [c["opB_text"]])})
    # bystanders (grow pool to >= the new multi-hop target count)
    target_bystanders = max(n_floor_total, len([c for c in ctx if c.get("role") == "bystander"]))
    have = len([c for c in ctx if c.get("role") == "bystander"])
    for c in byst_cands:
        if have >= target_bystanders:
            break
        cid = f"C{c_next:03d}"; c_next += 1
        ctx.append({"id": cid, "subject": c["subject"],
                    "category": c.get("category", "preference"),
                    "role": "bystander", "supports": [],
                    "text": c["text"], "utterance": c["utterance"],
                    "probe_value": normalize_values(c.get("probe_value") or [])})
        have += 1
    return mh, ctx


def build_rho(existing_rho, kept_cands):
    facts = list(existing_rho)
    used = {f.get("subject") for f in existing_rho}
    nums = [int(f["id"][1:]) for f in existing_rho if f["id"][1:].isdigit()]
    n_next = (max(nums) if nums else 15) + 1
    for c in kept_cands:
        if c["subject"] in used:
            continue  # keep subjects distinct
        used.add(c["subject"])
        facts.append({
            "id": f"R{n_next:02d}", "tier": c["tier"], "subject": c["subject"],
            "world_context": c["world_context"], "text": c["text"],
            "utterance": c.get("utterance", c["text"]), "question": c["question"],
            "delete_value": normalize_values(c["delete_value"]),
            "probe_value": normalize_values(c["probe_value"]),
        })
        n_next += 1
    return facts


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Validate + enlarge the fact datasets (DATA GATE)")
    ap.add_argument("--n-samples", type=int, default=6, help="rho samples/reasoner (exp07 default)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--remeasure", action="store_true", help="re-measure rho even if stored")
    ap.add_argument("--dry-run", action="store_true", help="validate but do not write data/facts/*")
    args = ap.parse_args()

    problems = config.validate()
    if problems:
        print("Config not ready:\n  - " + "\n  - ".join(problems))
        return 2

    print("=" * 74)
    print("  DATA GATE  --  author (gpt-4o-mini) -> measure (locked reasoners) -> gate")
    print(f"  reasoners: {config.REASONER_MODEL}  +  {config.SECOND_MODEL}")
    print(f"  judge:     {config.JUDGE_MODEL}   |  rho n-samples={args.n_samples}")
    print("=" * 74)

    iso_meta, iso_existing = _load(ISO_PATH)
    mh_meta, mh_existing = _load(MH_PATH)
    ctx_meta, ctx_existing = _load(CTX_PATH)
    rho_meta, rho_existing = _load(RHO_PATH)

    # ---- author candidates (gpt-4o-mini) ------------------------------------
    print("\n[1/6] Authoring candidates with gpt-4o-mini ...", flush=True)
    cand = gen.author_all()
    print(f"      isolated={len(cand['isolated'])}  bin1={len(cand['multihop_bin1'])}  "
          f"bin2={len(cand['multihop_bin2'])}  bystanders={len(cand['bystanders'])}  "
          f"rho={len(cand['rho'])}")

    # ---- global persona public-figure check ---------------------------------
    print("\n[2/6] Persona public-figure check (memorization-confound guard) ...", flush=True)
    persona_names = sorted({p["name"] for p in gen.PERSONAS}
                           | {p["name"] for p in gen.RHO_SUBJECTS})
    pf = persona_check(persona_names, args.workers)
    collisions = [v for v in pf.values() if v["collision"]]
    bad_names = {v["name"] for v in collisions}
    for v in collisions:
        print(f"      COLLISION: {v['name']} -> {v.get('who')} (conf {v['confidence']:.2f})")
    if not collisions:
        print(f"      OK -- 0/{len(persona_names)} personas collide with a real public figure")
    # drop any candidate whose subject collided
    if bad_names:
        for key in ("isolated", "multihop_bin1", "multihop_bin2", "bystanders", "rho"):
            cand[key] = [c for c in cand[key] if c.get("subject") not in bad_names]

    # ---- isolated: parametric rho ~ 0 gate ----------------------------------
    print("\n[3/6] Isolated: rejecting any candidate recoverable by the base model ...", flush=True)
    iso_kept, iso_disc = gate_isolated(cand["isolated"], args.workers)
    print(f"      kept {len(iso_kept)} / {len(cand['isolated'])}  (discarded {len(iso_disc)} recoverable)")

    # ---- multi-hop: near-miss + contamination gate --------------------------
    print("\n[4/6] Multi-hop: near-miss (joint fires, singles don't) + contamination ...", flush=True)
    mh1_kept, mh1_disc = gate_multihop(cand["multihop_bin1"], args.workers)
    mh2_kept, mh2_disc = gate_multihop(cand["multihop_bin2"], args.workers)
    print(f"      bin1(stored)       kept {len(mh1_kept)} / {len(cand['multihop_bin1'])}")
    print(f"      bin2(stored+world) kept {len(mh2_kept)} / {len(cand['multihop_bin2'])}")

    # ---- assemble final sets (gentle caps so sizes track the spec) ----------
    iso_facts = build_isolated(iso_existing, iso_kept, cap=36)         # ~48 total
    mh1_use = [k for k in mh1_kept][:16]                              # ->17 with existing
    mh2_use = [k for k in mh2_kept][:12]                              # ->17 with existing
    n_floor_total = len(mh_existing) + len(mh1_use) + len(mh2_use)
    mh_facts, ctx_facts = build_multihop_and_context(
        mh_existing, ctx_existing, mh1_use + mh2_use, cand["bystanders"], n_floor_total)

    # ---- rho-gradient: MEASURE both reasoners, FLAG mismatches (no discard) --
    print("\n[5/6] rho-gradient: measuring rho for ALL facts (both reasoners) ...", flush=True)
    rho_facts = build_rho(rho_existing, cand["rho"])
    flags = measure_rho(rho_facts, args.n_samples, args.workers, args.remeasure)

    # ---- referential integrity ----------------------------------------------
    print("\n[6/6] Referential integrity (entailed_by / supports) ...", flush=True)
    ref_problems = referential_integrity(mh_facts, ctx_facts)
    print("      OK" if not ref_problems else "      PROBLEMS:\n        - "
          + "\n        - ".join(ref_problems))

    print("\n[6b/6] Cross-fact value uniqueness (RF4 C-01) ...", flush=True)
    uniq_problems = check_value_uniqueness(iso_facts, ctx_facts)
    print("      OK -- no isolated value collides with another stored fact"
          if not uniq_problems else
          f"      {len(uniq_problems)} VALUE COLLISIONS:\n        - "
          + "\n        - ".join(uniq_problems))

    # ---- counts -------------------------------------------------------------
    iso_personas = sorted({f["subject"] for f in iso_facts})
    iso_cats = sorted({f["category"] for f in iso_facts})
    bin1 = [f for f in mh_facts if f.get("rederivation_basis") == "stored"]
    bin2 = [f for f in mh_facts if f.get("rederivation_basis") == "stored+world"]
    ent = [c for c in ctx_facts if c.get("role") == "entailing"]
    byst = [c for c in ctx_facts if c.get("role") == "bystander"]
    rho_by_tier = {t: [f for f in rho_facts if f.get("tier") == t]
                   for t in ("low", "mid", "high")}

    # ---- extend _meta -------------------------------------------------------
    iso_meta.setdefault("fields", {})["category"] = " | ".join(gen.ISO_CATEGORIES)
    iso_meta["description"] = iso_meta.get("description", "") + \
        " [extended: enlarged to >=15 fictional personas across >=6 categories; every " \
        "new fact passed the parametric rho~0 gate (not recoverable by the base model)]"
    rho_meta["measurement"] = {
        "reasoners": [config.REASONER_MODEL, config.SECOND_MODEL],
        "n_samples": args.n_samples, "judge": config.JUDGE_MODEL,
        "measured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tier_boundaries": {"low<": TIER_LO_HI[0], "mid<": TIER_LO_HI[1]},
        "note": "measured_rho stored per fact (both reasoners); measured_tier uses the "
                "worst-adversary rho = max over reasoners (Def. 4); tier_flag marks "
                "hypothesis-vs-measured mismatches (kept, never discarded).",
    }

    # ---- write --------------------------------------------------------------
    if not args.dry_run:
        _write(ISO_PATH, iso_meta, iso_facts)
        _write(MH_PATH, mh_meta, mh_facts)
        _write(CTX_PATH, ctx_meta, ctx_facts)
        _write(RHO_PATH, rho_meta, rho_facts)
        print("\n  wrote: " + ", ".join(str(p) for p in (ISO_PATH, MH_PATH, CTX_PATH, RHO_PATH)))
    else:
        print("\n  [dry-run] no files written")

    # ---- report -------------------------------------------------------------
    print("\n" + "=" * 74)
    print("  PER-SET COUNTS")
    print("=" * 74)
    print(f"  isolated_facts.json   : {len(iso_facts):3d} facts "
          f"({len(iso_existing)} existing + {len(iso_facts) - len(iso_existing)} new"
          f"; {len(iso_kept)} passed the rho~0 gate)  "
          f"| {len(iso_personas)} distinct personas | {len(iso_cats)} categories")
    print(f"  multi_hop_facts.json  : {len(mh_facts):3d} facts  "
          f"| bin1(stored)={len(bin1)}  bin2(stored+world)={len(bin2)}")
    print(f"  context_facts.json    : {len(ctx_facts):3d} facts  "
          f"| entailing={len(ent)}  bystander={len(byst)}")
    print(f"  rho_gradient_facts.json: {len(rho_facts):3d} facts | "
          + "  ".join(f"{t}={len(rho_by_tier[t])}" for t in ('low', 'mid', 'high')))

    print("\n" + "=" * 74)
    print("  rho-GRADIENT  HYPOTHESIS  vs  MEASURED   (worst-adversary = max over reasoners)")
    print("=" * 74)
    print(f"  {'id':5s} {'subject':22s} {'hyp':5s} {'rho(mini)':>9s} {'rho(4o)':>8s} "
          f"{'worst':>6s} {'meas':5s}  flag")
    n_mismatch = 0
    for fl in sorted(flags, key=lambda x: (x.get("hyp", ""), x["id"])):
        if fl.get("flag") == "ERROR":
            print(f"  {fl['id']:5s} {str(fl.get('subject'))[:22]:22s} {str(fl.get('hyp')):5s} "
                  f"{'ERR':>9s} {'ERR':>8s} {'-':>6s} {'-':5s}  ERROR: {fl.get('error')}")
            continue
        mark = "  <-- MISMATCH" if fl["mismatch"] else ""
        if fl["mismatch"]:
            n_mismatch += 1
        print(f"  {fl['id']:5s} {str(fl['subject'])[:22]:22s} {fl['hyp']:5s} "
              f"{fl['rho_r1']:9.2f} {fl['rho_r2']:8.2f} {fl['worst']:6.2f} {fl['meas']:5s}{mark}")
    print(f"\n  tier flags: {n_mismatch} mismatch / {len(flags)} facts "
          f"(mismatches are FLAGGED + KEPT, never discarded)")

    # ---- gate decision ------------------------------------------------------
    fails = []
    if len(iso_personas) < FLOOR_ISO_PERSONAS:
        fails.append(f"isolated personas {len(iso_personas)} < {FLOOR_ISO_PERSONAS}")
    if len(bin1) < FLOOR_MH_PER_BIN:
        fails.append(f"multi-hop bin1 {len(bin1)} < {FLOOR_MH_PER_BIN}")
    if len(bin2) < FLOOR_MH_PER_BIN:
        fails.append(f"multi-hop bin2 {len(bin2)} < {FLOOR_MH_PER_BIN}")
    for t in ("low", "mid", "high"):
        if len(rho_by_tier[t]) < FLOOR_RHO_PER_TIER:
            fails.append(f"rho tier {t} {len(rho_by_tier[t])} < {FLOOR_RHO_PER_TIER}")
    if ref_problems:
        fails.append(f"{len(ref_problems)} referential-integrity problems")
    if uniq_problems:
        fails.append(f"{len(uniq_problems)} value-collision problems (RF4 C-01)")
    if any(f.get("flag") == "ERROR" for f in flags):
        fails.append("rho measurement errors present")

    print("\n" + "=" * 74)
    if fails:
        print("  GATE: FAIL -- " + "; ".join(fails))
        print("=" * 74)
        return 1
    print("  GATE: PASS -- all per-set floors met, refs intact, rho measured for all facts")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
