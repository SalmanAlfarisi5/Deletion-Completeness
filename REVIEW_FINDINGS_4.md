# REVIEW_FINDINGS_4 — full-codebase fresh pass (closes the NEEDS-VERIFICATION gaps)

**Reviewer:** Claude (read-only audit; no code changed, no paper number changed)
**Date:** 2026-07-02
**Mode:** full read of every source file (including the files passes 1–3 left grep-only: exp05/06/09/10/11 bodies, `paraphrase_probe`, `kg_node_residue`, `artifact_tracer`, `graph_builder`, `generate_facts`/`validate_facts` internals, `evaluation/metrics.py`, tests, Makefile, reproduce.sh, README, the uncommitted paper diff) + offline data checks against `data/facts/` and committed `data/results/`. Offline test suite **46/46 green**. No paid API calls.

**Scope note:** findings from passes 1–3 are not re-reported. Everything below is new.

---

## 0. Lead verdict

Two findings matter for the paper; the rest are code/doc hygiene.

1. **H-04 (exp05):** the duplication-incidence metric counts *cross-fact value collisions* as duplicates, and the enlarged corpus is 7× more collision-prone than the old one (21.5% vs 3.0% of facts). The drafts' "incidence rises with store size, 30–39% → 63–70%" sentence is therefore partly a counting artifact, and the n=149 paraphrase>byte margin is inflated by the same mechanism.
2. **M-09 (uncommitted paper edit):** the new formal ρ definition says the 6-draw / T=0.7 estimator is used "**throughout**", but exp03/exp04/exp11 measure ρ as a **single temperature-0 draw** (`run_parametric`), and their certificates carry that value. One word to scope, or a methodology change to make true.

Counts: **High 1 · Medium 8 · Low 9.**

---

## 1. HIGH

### H-04 — exp05 `dup_incidence` counts cross-fact value collisions as duplicates; the enlarged corpus made this 7× worse, confounding the scale-dependence sentence
- **Location:** `experiments/exp05_duplication.py:46-57`; drafts §res (supervisor line ~690: "the incidence rises with store size, from 30–39% at n=33 to 63–70% at n=149"); `paper/CLAIMS_LEDGER.md` C2-Ctrl.
- **What's wrong.** All 149 facts are injected into **one store per cell**, and a fact counts as duplicated when >1 stored row contains its **primary probe value** (`hits = [t for t in texts if prim in t.lower()]`). Rows are not attributed to facts, and subjects are not matched — so if *another fact's* row legitimately contains the same string, that is scored as a duplicate.
- **Measured (offline, static proxy):** in the current corpus **32/149 facts (21.5%)** have their primary value inside another fact's source text/utterance (`painting` C079↔C087↔C095, `walks` C008↔C081↔C089, `guitar` C015↔C101, `50 per month` C040↔C042, `5 hours` C056↔C074, `12 events` C057↔C070, `5 years` C069↔C009, `5%` C071↔C010, `gardening`, `mystery novels`, …). In the **old 33-fact corpus the same check finds 1/33 (3.0%)**. The enlarged LLM-authored bystanders re-use hobby vocabulary heavily, which is exactly what the metric can't distinguish from Mem0 duplication.
- **Impact on claims.**
  - *Scale-dependence:* measured incidence rose 30–39% → 63–70% (Δ≈30 pts) while the collision floor rose 3% → 21.5% (Δ≈18 pts). A large share of the reported rise is plausibly the corpus, not Mem0. True dedup-failure incidence at n=149 is bounded below by roughly (measured − collision) ≈ 42–48% — still above the old 30–39%, so *some* scale trend likely survives, but the sentence as written over-claims.
  - *paraphrase > byte:* a cross-fact collision always lands in the **paraphrase** bucket (different row texts → `len(norm) > 1`), so the n=149 paraphrase counts (61–79 vs byte 26–41) are inflated specifically on the side the claim leans on. The old-corpus cells (collision-free) still support the qualitative claim.
  - The committed exp05 JSONs store only aggregate cells (no per-fact rows), so this **cannot be re-scored from logs** — quantifying exactly needs a re-run that logs per-fact hit rows.
- **Suggested fixes (methodology — author approval; pick one):**
  (a) count duplicates only among rows attributable to the fact via the injection map (`inj_map[fact_id]["memory_ids"]` + value match), or
  (b) require the fact's **subject AND value** in a row before counting it, or
  (c) keep the metric but report it collision-adjusted (exclude the 32 colliding facts, or subtract the static collision floor), and soften the scale-dependence sentence to "rises at least partly with store size".
  Cheapest paper-only mitigation: keep 63–70% but add one clause acknowledging the counting picks up cross-fact value sharing that grows with corpus size, and lean the scale claim on row counts per fact rather than incidence.

---

## 2. MEDIUM

### M-09 — Uncommitted paper edit: "ρ̂ over n=6 draws at T=0.7 **throughout**" contradicts exp03/exp04/exp11, which use a single temperature-0 draw
- **Location:** uncommitted `paper/supervisor_draft.tex` (new Def. parametric floor: "over $n{=}6$ draws at $T{=}0.7$ throughout, substituting $\hat\rho$ … wherever the floor enters Definitions"); `planner/optimizer.py:44` and `experiments/exp04_parametric.py:92`, `exp11:110` — all `param.run_parametric(fact)` = **one** deterministic (T=0) sample; their certificates' `parametric_risk_rho` carries it (e.g. supervisor line 584 "parametric floor ρ=0%").
- **Impact:** the formalization is only true of exp07. Numerically harmless today (multi-hop ρ≈0 under both procedures), but a careful reviewer comparing Def. ρ̂ to the exp04 table/certificates will catch the mismatch. The AAAI draft does not (yet) contain the new wording.
- **Fix:** scope the sentence ("n=6 at T=0.7 for the ρ-gradient measurements; for multi-hop targets, where ρ≈0, we use a single deterministic draw as a cheap point estimate") — text-only; or actually switch exp03/04/11 to `estimate_rho` (paid re-run, likely no number change).

### M-10 — `validate_recovery_judge(model)` no longer validates the model it is passed
- **Location:** `evaluation/judge.py:51-56` (`ParametricProbe(model=model)` → `probe._judge_recovery(...)`); `probes/parametric_probe.py:84-92` (post-H-01, `_judge_recovery` hardcodes `config.JUDGE_MODEL`).
- **What's wrong:** since the H-01 lock, the `model` argument only changes the **label** written into `judge_validation_*.json` (`"model": model`); the actual judging model is always `config.JUDGE_MODEL`. Calling `validate_recovery_judge(config.SECOND_MODEL)` (e.g. to validate a gpt-4o recovery judge) would silently re-validate gpt-4o-mini and record it as gpt-4o — a false validation artifact that `_resolve_judge_recall()` would then pick up by mtime.
- **Fix:** have `validate_recovery_judge` call the judge prompt directly with `model`, or make `_judge_recovery` accept an explicit override parameter used only by validation; at minimum assert `model == config.JUDGE_MODEL`.

### M-11 — `build_isolated` restarts ids at F100: duplicate-id collision on any future gate re-run
- **Location:** `data/validate_facts.py:315` (`nid = 100` unconditionally); isolated set already holds **F100–F135**.
- **What's wrong:** unlike `build_multihop_and_context` (`f_next = max(existing)+1`) and `build_rho` (same), a second non-dry `validate_facts.py` run that keeps any new isolated candidate writes a **second F100, F101, …**. Downstream code indexes facts by id (`{f["id"]: f}` in exp09/exp10, `iso_ids` sets), so duplicates are silently overwritten/miscounted.
- **Impact:** none on the frozen committed datasets; a real data-integrity trap the next time the gate runs (e.g., another enlargement wave).
- **Fix:** `nid = max([int(f["id"][1:]) for f in existing if f["id"][1:].isdigit()] + [99]) + 1`.

### M-12 — exp11 still has `--n` default 6, and exp05/exp11 are missing from `reproduce.sh`
- **Location:** `experiments/exp11_letta_rederivation.py:65` (`--n type=int default=6`; paper is n=34, commit `169e22b`); `reproduce.sh` (contains exp01–04, 07, 08, comments exp09/10 — **no exp05, no exp11, no exp06**).
- **What's wrong:** the pass-2 fix #3 ("--n default → all facts") covered exp01–04 but not exp11, so a no-flag exp11 run reproduces the **old n=6** numbers (bin1 n=1). And two experiments that back reported numbers (exp05 = the C2 control cells; exp11 = the Letta re-derivation row) are absent from the reproduce script entirely — exp06 is deliberately uncited, but exp05/exp11 are cited.
- **Fix:** `--n default=None` (with the `[:None]` slice already in place at line 76), and add exp05 (no service needed) plus a commented exp11 line next to exp09/10 (`--n 34` until the default changes, service prereq noted).

### M-13 — README contradicts the paper and contains a command that crashes
- **Location:** `README.md:10` ("Recoverability is decomposed into **exactly two causes**" — the paper's core claim is the **three-channel** decomposition, with ρ folded into cause 2 here); `README.md:79` (`python experiments/exp08_mia.py --n 6 --corpus 27 -v` — exp08 has **no `--n`/`--corpus` args**; argparse exits with "unrecognized arguments"); `README.md:105,130-137` (exp08 block reports the **old n=33** numbers — intact 0.72 / naive 0.61 "does **not** reach significance p=.07" / aware 0.51, plus "a planned n≈60 run" — while the committed exp08 and both drafts report n=48+96: intact 0.69 p=.001 / **naive 0.68 p=.001 significant** / aware 0.52; the planned run already happened); `README.md:28` lists an "embedding" probe that doesn't exist (pass-1 L-09, still in README); `--n 12`/`--n 6` example commands reproduce pre-wave numbers.
- **Impact:** the README is the first thing a reviewer opens; right now it mis-states the contribution's arity, shows a broken command, and asserts the *opposite* significance verdict for naive-deletion MIA than the paper does.
- **Fix:** one README refresh pass against the drafts (text-only).

### M-14 — exp08 CI/p-value machinery ignores the matched, clustered design (docstring says "resampling facts"; code resamples scores)
- **Location:** `probes/membership_inference.py:40-62`; design: each member has **2 matched twins** (`exp08 --twins 2`).
- **What's wrong:** `bootstrap_ci` resamples members and twins **independently** (not fact-clusters of 1 member + its 2 twins), and `permutation_p` permutes pooled labels — both treat the 96 twin scores as exchangeable/iid even though twin pairs share a template with each other and with their member. The module/exp08 docstrings say "resampling facts", which the code does not do. Effect: CI slightly too narrow, p slightly mis-calibrated (pseudo-replication).
- **Impact on claims:** the headline (aware CI **includes** 0.5) only gets safer under a wider clustered CI. The "powered" naive/intact p=.001 claims are very likely robust (AUC 0.68–0.69), but their nominal calibration rests on an assumption the design breaks.
- **Fix:** cluster bootstrap by fact (resample fact indices, take the member + its own twins), and permute at the fact level; or fix the docstring and add one caveat line in the drafts. Statistical-methods change → author approval.

### M-15 — exp04/exp11 certificates are primary-reasoner-only, not worst-adversary
- **Location:** `experiments/exp04_parametric.py:112-122`, `exp11:137-148` (cert emitted only for `config.REASONER_MODEL` = gpt-4o-mini, with that reasoner's `red_after`/`rho`); contrast `exp07:131` (cert ρ = max over reasoners, per Def. 4).
- **What's wrong:** a fact whose re-derivation is closed for gpt-4o-mini but open for gpt-4o would receive a COMPLETE certificate. In the committed runs this never bites (`rederiv_after_codelete` = 0 for **both** reasoners in every bin), so no emitted cert is wrong — but the emission *design* doesn't implement the worst-adversary semantics the certificate text claims ("worst adversary" appears in `to_text` and the threat model).
- **Fix:** emit the cert from `max` over the reasoners' `red_after`/`rho` (both are already measured in the same loop — cheap restructuring), or annotate the cert's threat model with the reasoner actually used.

### M-16 — `gate_isolated` keeps candidates whose ρ-gate call errored, and reports nothing
- **Location:** `data/validate_facts.py:203-204` (`except … return {"recoverable": False, "error": …}` — comment says "keep-on-error, never silently drop") vs the multihop gate, which **discards** on error (line 256, "conservative").
- **What's wrong:** for the isolated set, "keep" is the **anti-conservative** direction — an API failure admits a candidate *without* the ρ≈0 check that defines the set — and the error is not counted, printed, or stored (only discards are reported), so a partial outage would silently weaken the gate.
- **Fix:** at minimum count and print errored candidates; better, retry-then-discard (matching the multihop gate's direction).

### M-17 — CLAIMS_LEDGER C2 control row is stale after the exp05 re-run/reframe
- **Location:** `paper/CLAIMS_LEDGER.md` C2-Ctrl: still "row-inflation **24–42%**, duplication incidence **30–39%**" (the old n=33 cells) and still "Corroborated by Mem0 issues (#4896 … #687)" — the drafts now lead with 63–70% at n=149 and commit `918b8cd` removed the issue citations as uncitable.
- **Impact:** the ledger is the anti-mismatch safety net; its C2 row no longer matches either draft. (If H-04 is acted on, this row changes again — update once.)

---

## 3. LOW

- **L-10 — `graph_builder.get_recovery_paths` accepts paths through deleted intermediate nodes** (`pipeline/graph_builder.py:54-62` checks only the *source* node's deleted flag; `nx.has_path` happily routes through deleted nodes). Dead code today (no experiment imports it), but a trap if ever revived.
- **L-11 — Dead code inventory:** `pipeline/graph_builder.py`, `pipeline/artifact_tracer.py` (imported by nothing), `evaluation/metrics.recoverability/mean/rate` (only `cohens_kappa` is used anywhere). README still lists tracer/builder as live pipeline stages. Either wire them in, or move to an `attic/`/delete before artifact review.
- **L-12 — exp09 `--communities` is `store_true` with `default=True`** (`exp09:49`) — the flag can never be turned off; dead CLI option (use `action=argparse.BooleanOptionalAction`).
- **L-13 — `parse_number` treats any `k…`-prefixed unit as ×1000** (`evaluation/recovery.py:39`): "36 km" → 36000, "5 kg" → 5000. Harmless today (verified: no mid-tier delete_value or logged exp07 mid answer carries km/kg), and self-cancelling when both sides scale — but a false negative if a target says "36 km" and an answer says "36". Guard with `startswith("k") and not startswith(("km","kg"))`.
- **L-14 — `value_twins` pads with duplicate twins on under-delivery** (`llm.py:139-140`): a duplicated twin string would enter exp08 twice (pseudo-replication in AUC/CI/permutation). Verified the committed run has 0 duplicates and 0 member-equal twins — latent only. Prefer topping up via extra `value_twin` calls with an exclusion list.
- **L-15 — `letta_adapter.query` exception fallback returns `list_memories()`** (both surfaces, unranked) as if they were search results (`letta_adapter.py:111-112`): any retrieval probe run on Letta would silently see the *entire* store on API error. No current experiment queries Letta, so latent.
- **L-16 — Letta agents leak server-side across processes:** `_agent` always **creates** `dc-{user_id}` (no lookup-by-name), and `delete_all_memories` only deletes agents created in the current process (`letta_adapter.py:36-46,85-92`). Every crashed/`--keep` run strands agents (and their stores) on the local server. Isolation is unaffected (fresh agent each run); it's hygiene + Postgres growth.
- **L-17 — exp01/exp02 sequential naive deletions mutate the shared store while later targets are probed** (one uid for all targets; a consolidated multi-fact row deleted for target A can carry target B's value). Direction is conservative for the residual-survival claims (could only *lower* the 97.9%/68.75%), and with isolated facts the coupling is rare — worth one limitation sentence at most.
- **L-18 — `chat()` ignores `json_mode` on the Anthropic path** (`llm.py:54-63`; no `response_format` equivalent is set), so `chat_json` under `LLM_PROVIDER=anthropic` relies purely on prompt discipline + brace-extraction. Non-default provider; latent.

---

## 4. Verified-correct this pass (new confirmations, beyond passes 1–3)

- **rho-gradient store hygiene:** all 49 utterances contain a `delete_value` surface form → after `delete_value_rows` the exp07 per-fact store is empty, so the certs' asserted `rederivation=0.0` is sound (checked all 49, 0 misses).
- **exp08 twins are well-formed in the committed run:** 96 twins, 0 equal to a member text, 0 duplicate strings; the 3 probe-value hits are template retention (e.g. the drug name with the dosage swapped) — intended matched-control design.
- **exp10 targets all exist** in the enlarged isolated set (incl. F102); `multi_hop` contamination check clean (no `delete_value` inside any operand text, comma/space-stripped); no duplicate ids within or across fact files; ctx roles = 67 entailing / 34 bystander, matching the experiments' assumptions.
- **`.env` is properly gitignored** (never tracked; only `.env.example` is committed) — no secret in the repo or history for that path.
- **`k`-suffix parsing** does not misfire on any committed mid-tier data or logged answer (checked exp07 logs).
- **Offline suite 46/46**; certificate boundary tests still pin `final==τ → PARTIAL` and floor-reaching semantics.
- **Uncommitted bib edits** fill in the real P2E2 (VLDB'25) author list/DOI and the ForgetEval title/author, removing the `[VERIFY]` placeholders — strictly an improvement; nothing inconsistent spotted (arXiv ids not independently verifiable offline).

## 5. Coverage
Every `.py` file in the repo was read in full this pass, plus Makefile, reproduce.sh, README, REPRODUCTION.md, CLAIMS_LEDGER.md, .gitignore, requirements*, the four fact datasets (programmatic checks), committed exp05/exp07/exp08 result JSONs, and the uncommitted `paper/` diff. Not re-verified: live service behavior (Neo4j/Letta), hosted-mode Mem0 paths, and the two .tex drafts line-by-line (passes 1–2 did the claims audit; only the uncommitted diff was reviewed here).
