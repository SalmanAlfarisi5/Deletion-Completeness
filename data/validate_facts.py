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
import planner.entailment_dag as ed  # noqa: E402
from planner.entailment_detector import EntailmentDetector  # noqa: E402
from probes.base_probe import normalize_values  # noqa: E402
from probes.parametric_probe import ParametricProbe  # noqa: E402

ISO_PATH = config.FACTS_DIR / "isolated_facts.json"
MH_PATH = config.FACTS_DIR / "multi_hop_facts.json"
CTX_PATH = config.FACTS_DIR / "context_facts.json"
RHO_PATH = config.FACTS_DIR / "rho_gradient_facts.json"
SEED_DIR = config.FACTS_DIR / "_seed"   # frozen canonical base for a reproducible rebuild

# The five structured topologies (uniform leaves+formula shape) and their bases.
STRUCT_KEYS = {"multilevel_join": "join", "multilevel_chain": "chain",
               "structured_or_and": "or_and", "structured_diamond": "diamond",
               "structured_threshold": "threshold"}
STRUCT_BASES = ("stored_join", "stored_chain", "stored_or_and",
                "stored_diamond", "stored_threshold")

# Floors (binding constraints for the ~3x expansion: ~250 per dataset).
FLOOR_ISO_TOTAL = 230
FLOOR_ISO_PERSONAS = 15
FLOOR_MH_PER_BIN = 40             # flat bin1 (stored) and bin2 (stored+world)
FLOOR_RHO_TOTAL = 230
FLOOR_RHO_PER_TIER = 15           # keep authored-tier diversity (measured tier may differ)
FLOOR_STRUCT_PER_TOPOLOGY = 25    # each of join/chain/or_and/diamond/threshold

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


def _load_base(path):
    """Load the frozen seed (data/facts/_seed/) if present so the rebuild is
    reproducible and idempotent; otherwise fall back to the live file."""
    seed = SEED_DIR / path.name
    return _load(seed if seed.exists() else path)


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


def _max_fid(*factlists) -> int:
    """Highest F-id number across the given fact lists (F-ids share a namespace across
    isolated + multi-hop, so new ids must be minted above the global max)."""
    nums = [int(f["id"][1:]) for lst in factlists for f in lst
            if f.get("id", "").startswith("F") and f["id"][1:].isdigit()]
    return max(nums, default=99)


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


def cross_file_id_uniqueness(iso_facts: list[dict], mh_facts: list[dict],
                             ctx_facts: list[dict], rho_facts: list[dict]) -> list[str]:
    """Every fact id must be globally unique across the four datasets. A collision
    (the same id naming two *different* facts in two files) is a latent corruption:
    any code that later merges two sets into one id-keyed dict silently drops the
    duplicate, and a certificate keyed by id resolves to the wrong fact. Historically
    the isolated and multi-hop sets both minted F1xx ids (see the build note at the
    id-minting site), colliding on F100--F131; this gate prevents recurrence."""
    from collections import defaultdict
    seen: dict[str, list[str]] = defaultdict(list)
    for name, facts in (("isolated", iso_facts), ("multi_hop", mh_facts),
                        ("context", ctx_facts), ("rho_gradient", rho_facts)):
        for f in facts:
            seen[f["id"]].append(name)
    return [f"{fid} appears in {len(files)} sets: {', '.join(files)}"
            for fid, files in sorted(seen.items()) if len(files) > 1]


def check_value_uniqueness(iso_facts: list[dict], ctx_facts: list[dict]) -> list[str]:
    """Cross-fact value-uniqueness gate (RF4 C-01).

    No isolated fact's probe value may also appear in another stored fact's
    searchable text (isolated OR context). A shared value makes exp02's per-fact
    naive->purge loop contaminate later facts (an earlier fact's artifact purge
    deletes a later fact's value rows, so it scores a spurious naive-success) and
    inflates exp05's dup-incidence with mere vocabulary overlap. Uses the same
    digit-normalizing _contains as the probes.
    """
    # SCOPE: only facts CO-INJECTED with the isolated set matter. exp01/02/05 inject
    # isolated alone; exp08 adds the bystander background. Entailing OPERANDS
    # (role='entailing') are only injected with their multi-hop targets, never with
    # isolated facts, so their dense numeric surface ('12 crates', 'SGD 35') produces
    # false-positive substring collisions -- excluded here.
    store = iso_facts + [c for c in ctx_facts if c.get("role") != "entailing"]

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
def dedup_isolated(iso_facts: list[dict], ctx_facts: list[dict]) -> list[dict]:
    """Drop the NEWER fact of each isolated value-collision until the set has
    globally-unique high-entropy values (RF4 C-01). gpt-4o-mini occasionally
    authors duplicate/low-entropy values (e.g. two facts sharing an IMEI, or a
    generic 'dark chocolate'); a shared value corrupts exp02's per-fact naive->purge
    loop, so we enforce uniqueness here rather than trust the author."""
    import re as _re
    iso = list(iso_facts)
    while True:
        probs = check_value_uniqueness(iso, ctx_facts)
        if not probs:
            break
        drop = set()
        for p in probs:
            # message format: "<iso F-id> value ... also appears in <other id>"
            ids = _re.findall(r"F\d+", p)
            if len(ids) >= 2:
                drop.add(max(ids, key=lambda x: int(x[1:])))  # iso-vs-iso: drop the newer
            elif ids:
                drop.add(ids[0])  # iso-vs-context (bystander): drop the isolated fact
        if not drop:
            break
        iso = [f for f in iso if f["id"] not in drop]
    return iso


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
def build_isolated(existing, kept_cands, cap=None, start=100):
    """Append isolated facts starting at F{start}. `start` is a GLOBAL F-id ceiling
    (max over isolated AND multi-hop) so new isolated ids never collide with new
    multi-hop ids -- the two sets mint from disjoint blocks (see main())."""
    facts = list(existing)
    nid = start
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
                               n_floor_total, f_start=None):
    mh = list(existing_mh)
    ctx = list(existing_ctx)
    # next ids: multi-hop F-ids start at f_start (a high, disjoint block from isolated
    # ids -- see main()); context C-ids continue their own namespace.
    f_next = f_start if f_start is not None else (
        max([int(f["id"][1:]) for f in existing_mh] + [45]) + 1)
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


def gate_structured(cands: list[dict], workers: int):
    """Gate for the TEMPLATED structured topologies (join / chain / or_and / diamond
    / threshold), all in the uniform ``leaves`` + ``formula`` shape.

    The facts are correct by construction (exact arithmetic, fictional rules), so this
    gate is a SAFETY NET that DISCARDS a candidate only on a real structural defect:
      (a) contamination: delete_value is a substring of any stored leaf text;
      (b) formula/leaf mismatch: the formula's leaf labels != the candidate's leaves;
      (c) single-sufficient leaf: some ONE leaf alone re-derives the target per the
          GROUND-TRUTH boolean formula (would break the near-miss property).
    The LLM JOINT-entailment answer (strong model) is REPORTED but never used to
    discard -- the gpt-4o-mini judge under-fires on multi-step derivations, so gating
    on it would wrongly drop valid facts (mirrors the rho flag-don't-discard policy).
    The near-miss ground truth here is the formula, not the fallible LLM judge."""
    def task(c):
        try:
            leaves = c["leaves"]
            texts = [lf["text"] for lf in leaves]
            formula = c["formula"]
            labels_match = ed.leaf_labels(formula) == {lf["label"] for lf in leaves}
            single_ok = ed.single_sufficient_leaves(formula) == []
            contam = any(_contains(t, v) for t in texts
                         for v in normalize_values(c["delete_value"]))
            passed = labels_match and single_ok and not contam
            # LLM joint report only (strong model can do the arithmetic).
            det_strong = EntailmentDetector(model=config.SECOND_MODEL)
            joint = _retry(lambda: det_strong.check_detailed(texts, c["target_text"]))
            return {"passed": passed, "variant": c.get("variant"),
                    "k_star": ed.min_codelete_size(formula),
                    "joint": f"{joint['answer']}@{joint['confidence']:.2f}",
                    "reason": ("ok" if passed else
                               "label-mismatch" if not labels_match else
                               "single-recovers" if not single_ok else "contamination")}
        except Exception as e:  # noqa: BLE001 -- discard-on-error (conservative)
            return {"passed": False, "reason": f"error:{e}"}

    out = _parallel(task, cands, workers, desc="structured-gate")
    kept, disc = [], []
    for c, r in zip(cands, out):
        (kept if r["passed"] else disc).append((c, r))
    return kept, disc


def build_structured(mh: list[dict], ctx: list[dict], kept: list, f_min: int = 0):
    """Append structured targets (into mh, with basis tag + packaged entailment_dag)
    and their stored leaf operands (into ctx, role='entailing'). Consumes the uniform
    candidate shape, so ONE builder handles every topology. Ids continue the F/C
    blocks after whatever build_multihop_and_context already appended; f_min anchors
    the F-ids into the multi-hop high block so they can never fall back into the
    isolated block (robust even if no flat facts were added first)."""
    f_next = max(max([int(f["id"][1:]) for f in mh if f["id"][1:].isdigit()] + [45]) + 1, f_min)
    c_next = max([int(c["id"][1:]) for c in ctx if c["id"][1:].isdigit()] + [22]) + 1
    for c, _r in kept:
        fid = f"F{f_next:03d}"; f_next += 1
        leaf_ids: dict[str, str] = {}
        support_ids: list[str] = []
        for lf in c["leaves"]:
            cid = f"C{c_next:03d}"; c_next += 1
            support_ids.append(cid)
            leaf_ids[lf["label"]] = cid
            ctx.append({"id": cid, "subject": c["subject"], "category": "reference",
                        "role": "entailing", "supports": [fid],
                        "text": lf["text"], "utterance": lf.get("utterance", lf["text"]),
                        "probe_value": normalize_values(lf.get("probe") or [lf["text"]])})
        mh.append({
            "id": fid, "subject": c["subject"], "category": c.get("category", "financial"),
            "text": c["target_text"], "utterance": c["target_utterance"],
            "question": c.get("target_question", f"What is the value for {c['subject']}?"),
            "delete_value": normalize_values(c["delete_value"]),
            "probe_value": sorted(set(normalize_values(c.get("probe_value", []))
                                      + normalize_values(c["delete_value"])), key=str),
            "entailed_by": list(support_ids),
            "co_delete_required": list(support_ids),
            "rederivation_basis": c["basis"],
            "entailment_note": c.get("entailment_note", ""),
            "entailment_dag": ed.build_dag(leaf_ids, c["formula"], c["variant"]),
        })
    return mh, ctx


# Old-format structured facts (entailment_dag = {nodes,edges,derived}) are re-authored
# fresh in the uniform leaves+formula shape, so they are stripped from the seed before
# the rebuild (their orphaned entailing operands go too).
OLD_STRUCTURED_BASES = {"stored_multilevel", "stored_chain"}


def strip_old_structured(mh: list[dict], ctx: list[dict]):
    """Drop seed multi-hop facts in the OLD structured format + their now-orphaned
    entailing operands; keep flat facts, all their operands, and every bystander."""
    keep_mh = [f for f in mh if f.get("rederivation_basis") not in OLD_STRUCTURED_BASES]
    referenced: set[str] = set()
    for f in keep_mh:
        referenced |= set(f.get("entailed_by", [])) | set(f.get("co_delete_required", []))
    keep_ctx = [c for c in ctx
                if c.get("role") != "entailing" or c["id"] in referenced]
    return keep_mh, keep_ctx


def build_rho(existing_rho, kept_cands, cap_total: int = 250):
    """Append rho candidates up to cap_total, keeping DISTINCT target values. A subject
    may carry several facts across different domains/tiers (a locker code AND an income
    band AND a licence->age), which is realistic and diverse; ~100 distinct subjects
    still back the set, well above the old effective-n concern. Keying on value (not
    (subject, tier)) is what lets the set scale, since the authoring reuses the subject
    pool."""
    facts = list(existing_rho)
    # rho facts are measured independently (one elicitation each), so there is NO
    # exp02-style purge contamination -> the SAME value may recur across DIFFERENT
    # subjects. Only skip an exact-duplicate fact (same subject + same value).
    seen = {(f.get("subject"), v) for f in existing_rho
            for v in normalize_values(f.get("delete_value", []))}
    nums = [int(f["id"][1:]) for f in existing_rho if f["id"][1:].isdigit()]
    n_next = (max(nums) if nums else 15) + 1
    for c in kept_cands:
        if len(facts) >= cap_total:
            break
        vals = normalize_values(c["delete_value"])
        keys = {(c["subject"], v) for v in vals}
        if not vals or keys & seen:
            continue  # skip only an exact-duplicate (subject, value) fact
        seen |= keys
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
    ap.add_argument("--n-samples", type=int, default=8, help="rho samples/reasoner (exp07 default)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--remeasure", action="store_true", help="re-measure rho even if stored")
    ap.add_argument("--dry-run", action="store_true", help="validate but do not write data/facts/*")
    ap.add_argument("--smoke", action="store_true",
                    help="tiny author counts + few rho samples + dry-run: exercises the whole "
                         "pipeline cheaply to catch runtime bugs (floors are not enforced)")
    args = ap.parse_args()
    if args.smoke:
        args.dry_run = True
        args.n_samples = min(args.n_samples, 3)

    problems = config.validate()
    if problems:
        print("Config not ready:\n  - " + "\n  - ".join(problems))
        return 2

    print("=" * 74)
    print("  DATA GATE  --  author (gpt-4o-mini) -> measure (locked reasoners) -> gate")
    print(f"  reasoners: {config.REASONER_MODEL}  +  {config.SECOND_MODEL}")
    print(f"  judge:     {config.JUDGE_MODEL}   |  rho n-samples={args.n_samples}")
    print("=" * 74)

    iso_meta, iso_existing = _load_base(ISO_PATH)
    mh_meta, mh_existing = _load_base(MH_PATH)
    ctx_meta, ctx_existing = _load_base(CTX_PATH)
    rho_meta, rho_existing = _load_base(RHO_PATH)
    # Re-author the structured facts fresh in the uniform format: drop the seed's
    # old-format structured facts (and their orphaned operands) before rebuilding.
    mh_existing, ctx_existing = strip_old_structured(mh_existing, ctx_existing)
    src = "seed" if (SEED_DIR / ISO_PATH.name).exists() else "live files"
    print(f"      base = {src}: iso={len(iso_existing)}  mh(flat)={len(mh_existing)}  "
          f"ctx={len(ctx_existing)}  rho={len(rho_existing)}  (old structured stripped)")

    # ---- author candidates (gpt-4o-mini) ------------------------------------
    print("\n[1/6] Authoring candidates with gpt-4o-mini ...", flush=True)
    _smoke_counts = dict(n_isolated_per_persona=1, n_mh_bin1=6, n_mh_bin2=6, n_rho_per_tier=6,
                         n_bystanders=8, n_ml_join=4, n_ml_chain=4, n_or_and=4,
                         n_diamond=4, n_threshold=4)
    cand = gen.author_all(**(_smoke_counts if args.smoke else {}))
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

    # ---- structured topologies (join/chain/or_and/diamond/threshold) --------
    print("\n[4b/6] Structured topologies: formula near-miss + contamination (templated) ...",
          flush=True)
    struct_kept: dict[str, list] = {}
    for key, name in STRUCT_KEYS.items():
        kept_s, _disc = gate_structured(cand.get(key, []), args.workers)
        struct_kept[name] = kept_s
        print(f"      {name:10s} kept {len(kept_s)} / {len(cand.get(key, []))}")

    # ---- assemble final sets (caps so sizes track the ~250 spec) ------------
    # Isolated and multi-hop share the F-id namespace, so mint from DISJOINT blocks
    # above the global F-max: isolated at [fmax+1 ..], multi-hop at [fmax+1000 ..].
    fmax = _max_fid(iso_existing, mh_existing)
    iso_facts = build_isolated(iso_existing, iso_kept, cap=None, start=fmax + 1)  # all survivors
    mh1_use = [k for k in mh1_kept][:40]                              # +40 flat bin1
    mh2_use = [k for k in mh2_kept][:40]                              # +40 flat bin2
    n_struct = sum(min(len(v), 30) for v in struct_kept.values())
    n_floor_total = len(mh_existing) + len(mh1_use) + len(mh2_use) + n_struct
    mh_facts, ctx_facts = build_multihop_and_context(
        mh_existing, ctx_existing, mh1_use + mh2_use, cand["bystanders"], n_floor_total,
        f_start=fmax + 1000)
    # structured targets + their stored leaf operands (appended after the flat set)
    for name in ("join", "chain", "or_and", "diamond", "threshold"):
        mh_facts, ctx_facts = build_structured(mh_facts, ctx_facts, struct_kept[name][:30],
                                               f_min=fmax + 1000)
    # RF4 C-01: drop isolated value collisions FIRST (against the full enlarged context),
    # THEN cap to ~250, so dedup can't push the surviving count below the floor.
    iso_facts = dedup_isolated(iso_facts, ctx_facts)
    iso_facts = iso_facts[: len(iso_existing) + 170]

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

    print("\n[6c/6] Cross-file id uniqueness (no id shared across datasets) ...", flush=True)
    id_problems = cross_file_id_uniqueness(iso_facts, mh_facts, ctx_facts, rho_facts)
    print("      OK -- every fact id is globally unique across datasets"
          if not id_problems else
          f"      {len(id_problems)} ID COLLISIONS:\n        - "
          + "\n        - ".join(id_problems))

    # ---- counts -------------------------------------------------------------
    iso_personas = sorted({f["subject"] for f in iso_facts})
    iso_cats = sorted({f["category"] for f in iso_facts})
    bin1 = [f for f in mh_facts if f.get("rederivation_basis") == "stored"]
    bin2 = [f for f in mh_facts if f.get("rederivation_basis") == "stored+world"]
    struct = {b: [f for f in mh_facts if f.get("rederivation_basis") == b]
              for b in STRUCT_BASES}
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
          f"| bin1(stored)={len(bin1)}  bin2(stored+world)={len(bin2)}  | "
          + "  ".join(f"{b.replace('stored_', '')}={len(struct[b])}" for b in STRUCT_BASES))
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
    if len(iso_facts) < FLOOR_ISO_TOTAL:
        fails.append(f"isolated total {len(iso_facts)} < {FLOOR_ISO_TOTAL}")
    if len(iso_personas) < FLOOR_ISO_PERSONAS:
        fails.append(f"isolated personas {len(iso_personas)} < {FLOOR_ISO_PERSONAS}")
    if len(bin1) < FLOOR_MH_PER_BIN:
        fails.append(f"multi-hop bin1 {len(bin1)} < {FLOOR_MH_PER_BIN}")
    if len(bin2) < FLOOR_MH_PER_BIN:
        fails.append(f"multi-hop bin2 {len(bin2)} < {FLOOR_MH_PER_BIN}")
    for b in STRUCT_BASES:
        if len(struct[b]) < FLOOR_STRUCT_PER_TOPOLOGY:
            fails.append(f"structured {b} {len(struct[b])} < {FLOOR_STRUCT_PER_TOPOLOGY}")
    if len(rho_facts) < FLOOR_RHO_TOTAL:
        fails.append(f"rho total {len(rho_facts)} < {FLOOR_RHO_TOTAL}")
    for t in ("low", "mid", "high"):
        if len(rho_by_tier[t]) < FLOOR_RHO_PER_TIER:
            fails.append(f"rho tier {t} {len(rho_by_tier[t])} < {FLOOR_RHO_PER_TIER}")
    if ref_problems:
        fails.append(f"{len(ref_problems)} referential-integrity problems")
    if uniq_problems:
        fails.append(f"{len(uniq_problems)} value-collision problems (RF4 C-01)")
    if id_problems:
        fails.append(f"{len(id_problems)} cross-file id collisions")
    if any(f.get("flag") == "ERROR" for f in flags):
        fails.append("rho measurement errors present")

    print("\n" + "=" * 74)
    if fails and args.smoke:
        print("  SMOKE: pipeline ran; floors not enforced (tiny counts). Issues: "
              + "; ".join(fails))
        print("=" * 74)
        return 0
    if fails:
        print("  GATE: FAIL -- " + "; ".join(fails))
        print("=" * 74)
        return 1
    print("  GATE: PASS -- all per-set floors met, refs intact, rho measured for all facts")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
