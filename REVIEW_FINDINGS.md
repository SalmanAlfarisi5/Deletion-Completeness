# REVIEW_FINDINGS — Deletion-Completeness codebase

**Reviewer:** Claude (senior research-software audit, read-only pass)
**Date:** 2026-06-27
**Mode:** static reading + grep + control-flow tracing + offline test suite. **No paid API/network calls, no experiment runs, no edits.**

## Coverage (be honest about depth)
- **Deep read:** `config.py`, `llm.py`, `evaluation/stats.py`, `evaluation/recovery.py`, `evaluation/judge.py`, `probes/parametric_probe.py`, `probes/membership_inference.py`, `probes/exact_match.py`, `probes/base_probe.py`, `planner/optimizer.py`, `planner/entailment_detector.py`, `certificate/emitter.py`, `certificate/schema.py`, `systems/base.py`, `systems/mem0_adapter.py`, `pipeline/injector.py`, `pipeline/deleter.py`, `experiments/exp03/04/07`, the multi-hop gate in `data/validate_facts.py`, all 4 datasets' schemas, the offline tests.
- **Light read / grep-only (NEEDS deeper pass):** `systems/zep_adapter.py`, `systems/letta_adapter.py`, `probes/paraphrase_probe.py`, `probes/kg_node_residue.py`, `pipeline/artifact_tracer.py`, `pipeline/graph_builder.py`, `experiments/exp01/02/05/06/08/09/10/11`, `data/generate_facts.py` internals. Findings there are marked **NEEDS-VERIFICATION**.

---

## 1. Executive summary

**Headline: I did not find a silent number-corrupting bug in the *as-run* pipeline.** The recoverability equation, the three-channel independence, the parametric probe's memory-off isolation, the statistics, the certificate logic, and the dataset schemas are all implemented correctly, and the 46 offline tests pass. The risks that exist are **(a) a judge-validation coverage gap, (b) reproducibility footguns where defaults don't match the paper, and (c) threshold/labeling inconsistencies** — none of which corrupt the numbers that were actually produced (those runs used the correct non-default flags), but several of which a skeptical reviewer will probe and one of which weakens a stated claim.

**Counts:** Critical 0 · High 1 · Medium 8 · Low 9.

**Look at these first:**
1. **H-01** — the recovery judge that scores recoveries is `self.model` (the reasoner), so gpt-4o's recoveries (which drive the worst-adversary ρ → 22/49) are judged by a model the validation never covered. The "validated, 0-false-accept judge" claim only covers gpt-4o-mini.
2. **M-02 / M-05 / M-07** — the experiment *defaults* don't reproduce the paper: planner's default entailment model is the 41.7%-false-fire gpt-4o-mini; `--n` defaults to 6 (paper is 34); `LLM_PROVIDER` defaults to `anthropic`. A naive re-run produces different numbers.
3. **M-04** — `config.ENTAILMENT_THRESHOLD = 0.50` is never used by the planner, which co-deletes at `τ = 0.10`; the named threshold doesn't govern the thing it appears to govern.
4. **M-03** — the multi-hop near-miss dataset gate uses gpt-4o-mini (the false-firing model), creating a selection effect on which multi-hop facts exist.

---

## 2. Findings

### HIGH

#### H-01 — The recovery judge that scores results is the reasoner itself, and was validated only for gpt-4o-mini
- **Location:** `probes/parametric_probe.py:83-87` (`_judge_recovery` uses `model=self.model`); `evaluation/judge.py:134` (`validate_recovery_judge(config.JUDGE_MODEL)`); `data/validate_facts.py:279` and `experiments/exp07_rho_gradient.py:72` (`ParametricProbe(model=reasoner)` for **both** reasoners).
- **Category:** B (methodological).
- **What's wrong / trigger:** Recovery is decided by a substring check and, when that fails, by `_judge_recovery`, which calls the LLM with `model=self.model`. Since the probe is instantiated per-reasoner, **when the reasoner is gpt-4o, gpt-4o judges its own recoveries.** But `evaluation/judge.py` only ever validates the recovery judge on `config.JUDGE_MODEL` (gpt-4o-mini → the reported "0/8 false-accept, κ=0.767"). The gpt-4o recovery judge is never validated. For numeric ρ-gradient values the adversary's answer rarely contains the exact `probe_value` surface form (e.g. "around 3,150" vs "3,200"), so the LLM-judge fallback fires non-trivially — and the worst-adversary ρ (→ **22/49 uncertifiable**) and exp04 bin-2 leak rates are frequently driven by the gpt-4o reasoner.
- **Impact:** The paper's "every recovery rate is scored by a validated judge / conservative lower bound" claim does not cover the gpt-4o-judged recoveries, which underpin the headline limit result. This is a **validation-coverage gap**, not a demonstrated error (the judge is shown the ground-truth value in `fact_text`, so it is a *matching* task gpt-4o is plausibly fine at — but it is unvalidated).
- **Evidence:** read both files; `_judge_recovery(self.model)` vs `validate_recovery_judge(config.JUDGE_MODEL)`. **NEEDS-VERIFICATION:** the *fraction* of ρ recovery decisions made by the LLM-judge fallback vs the substring path (greppable from the logged `answers` in `data/results/exp07_*.json` — offline).
- **Suggested fix (do not apply yet):** Either (a) lock the recovery judge to `config.JUDGE_MODEL` inside `_judge_recovery` regardless of the reasoner (one judge for all reasoners — restores the validation's coverage), or (b) additionally validate the gpt-4o recovery judge in `evaluation/judge.py` and report both. **This is a methodology change — needs author approval.**

---

### MEDIUM

#### M-01 — Authoring and measurement are only partially separated (author = reasoner-1 = its own recovery judge)
- **Location:** `data/generate_facts.py:35` (`AUTHOR_MODEL = config.JUDGE_MODEL` = gpt-4o-mini); `config.py:59,63` (`JUDGE_MODEL` and `REASONER_MODEL` both gpt-4o-mini); `data/validate_facts.py:5-12` (docstring acknowledging it).
- **Category:** B.
- **What's wrong:** The §3 invariant ("a model must never score an item it authored") is not strictly held: gpt-4o-mini authors the ρ-gradient facts **and** is reasoner-1 **and** (per H-01) its own recovery judge. The code defends this — the authored value is hidden from `estimate_rho` (only `world_context` is given), and the worst-adversary ρ uses the independent gpt-4o. That defense is reasonable, but the **per-reasoner gpt-4o-mini ρ column** (paper's tier means "mid 0.069", etc.) is author-confounded and should not be interpreted as an independent adversary.
- **Impact:** Headline (worst-adversary 22/49) is largely robust because gpt-4o (independent of authoring) dominates the `max` where it matters; the per-reasoner gpt-4o-mini ρ is the confounded quantity.
- **Evidence:** read `generate_facts.py` docstring + `AUTHOR_MODEL`, `validate_facts.py` reasoner loop.
- **Suggested fix:** Document the caveat in the paper, or author the ρ-gradient facts with a third model not used as a reasoner. **Methodology — approval needed.**

#### M-02 — Planner's default entailment model is the 41.7%-false-fire gpt-4o-mini
- **Location:** `experiments/exp03_planner.py:43` (`--entailment-model` default = `config.JUDGE_MODEL` = gpt-4o-mini).
- **Category:** B / E (reproducibility).
- **What's wrong / trigger:** The paper's planner headline (k=0.91, **0 spurious**) requires gpt-4o entailment (the as-run command passed `--entailment-model gpt-4o-2024-08-06`). The *default* is gpt-4o-mini, which `evaluation/judge.py` itself shows false-fires on 41.7% of insufficient operands → inflates collateral k and produces spurious bystander deletions. `python experiments/exp03_planner.py` with no flags reproduces a **worse, different** result than the paper.
- **Impact:** A reviewer re-running the default would see k inflated and spurious > 0 and conclude the paper's "0 spurious" doesn't reproduce. The as-run number is correct; the default is a footgun.
- **Evidence:** `exp03_planner.py:43-44`, cross-referenced with `evaluation/judge.py:156-157` and the session's as-run command.
- **Suggested fix:** Change the default to `config.SECOND_MODEL` (gpt-4o), or hard-fail/warn if the entailment model is gpt-4o-mini. **Changing the default touches a methodology knob — approval needed.**

#### M-03 — The multi-hop near-miss dataset gate uses gpt-4o-mini (the false-firing model)
- **Location:** `data/validate_facts.py:237` (`EntailmentDetector(model=config.JUDGE_MODEL)` = gpt-4o-mini) inside the multi-hop near-miss gate.
- **Category:** B / D.
- **What's wrong:** The gate admits a multi-hop fact iff the joint operands fire AND **neither single operand** is judged a full "YES". Judging single operands with gpt-4o-mini (41.7% false-fire on insufficient operands) means it wrongly says "single operand recovers" on ~4/10 cases → those facts are **discarded**. Direction is conservative (over-discard), but it **selects** the multi-hop set toward facts where even a false-firing judge agrees the single operand is insufficient — a selection effect on the dataset that exp03/exp04 then run on. Also inconsistent with the planner, which (correctly) must use gpt-4o.
- **Impact:** The composition of `multi_hop_facts.json` (hence the bin rates and planner candidates) is partly determined by a known-unreliable judge. Not a number error, but a dataset-construction confound a reviewer will ask about.
- **Evidence:** read `validate_facts.py:233-263`; the asymmetric criteria (single uses `answer=="YES"`, joint uses `confidence>=0.5`) compound it.
- **Suggested fix:** Gate the near-miss property with `config.SECOND_MODEL` (gpt-4o, 0% false-fire). **Methodology — approval needed.**

#### M-04 — `ENTAILMENT_THRESHOLD = 0.50` is defined but never governs the planner (which uses τ = 0.10)
- **Location:** `config.py:77`; `planner/optimizer.py:99` (`if conf <= self.tau: break`) and `:120` (`> self.tau`).
- **Category:** C (config single-source).
- **What's wrong:** The planner co-deletes any candidate whose entailment confidence exceeds **`self.tau` (0.10)**, not `ENTAILMENT_THRESHOLD` (0.50). `ENTAILMENT_THRESHOLD` is used only in `evaluation/judge.py` validation and `validate_facts.py`. So "we draw an ENTAILS edge at confidence 0.50" (the documented/validated threshold) is **not** the rule the planner actually applies. The threshold heuristic's re-probing masks this (it stops once recoverable < τ, so k stays minimal), but the depth-first comparator's large spurious count is a direct consequence of the 0.10 cutoff.
- **Impact:** Conceptual inconsistency between the stated entailment threshold and the planner's behavior; a config knob that looks load-bearing but isn't. No as-run number error.
- **Evidence:** read `optimizer.py:91-124`, `config.py:77`.
- **Suggested fix:** Either use `config.ENTAILMENT_THRESHOLD` as the co-deletion cutoff, or remove/rename it and document that the planner cutoff is τ. **Methodology — approval needed (it changes which candidates co-delete).**

#### M-05 — Experiment defaults (`--n 6`) don't match the paper's n=34
- **Location:** `experiments/exp03_planner.py:41`, `experiments/exp04_parametric.py:54` (both `--n` default 6); `[: args.n]` slices at `exp03:56`, `exp04:66`.
- **Category:** E (reproducibility).
- **What's wrong:** Default `--n 6` takes the first 6 multi-hop facts (the old dataset size), not all 34 (17/17 bins). A no-arg re-run reproduces the *old* numbers, and for exp04 yields unbalanced bins.
- **Impact:** Reproducibility footgun; the paper's numbers require explicit `--n 34`.
- **Evidence:** read both files.
- **Suggested fix:** Default `--n` to "all facts in the file" (e.g. `None` → full set). Engineering change, low risk, but confirm intent.

#### M-06 — ρ is not seed-reproducible across runs
- **Location:** `probes/parametric_probe.py:100-115` (`estimate_rho`: `temperature=0.7, use_cache=False`); `experiments/exp07_rho_gradient.py:64-65` (seeds `random`/`numpy` only).
- **Category:** E.
- **What's wrong:** ρ is a rate over stochastic temp-0.7 samples drawn with `use_cache=False`. `random.seed`/`np.random.seed` do **not** control OpenAI's server-side sampling, and no API `seed` is passed. So re-running exp07 yields different ρ values; only the *logged answers* (re-scored offline) are fixed.
- **Impact:** The paper's ρ numbers are reproducible only from the committed logged answers, not from a fresh run. Worth an explicit statement; not a bug.
- **Evidence:** read both; `use_cache=False` is required for correctness (caching would collapse the samples — that part is right).
- **Suggested fix:** Pass `seed=` to the OpenAI call where supported and document that ρ reproducibility is best-effort; or state that re-scoring the logged answers is the reproducible path.

#### M-07 — `LLM_PROVIDER` defaults to `anthropic`, not the `openai` that produced the paper
- **Location:** `config.py:33`; `config.py:3-4` docstring claims "reproducible from a clean checkout".
- **Category:** E.
- **What's wrong:** Without `.env`/env setting `LLM_PROVIDER=openai`, a clean checkout runs the judge/reasoner on Claude (`claude-haiku-4-5`), producing different numbers than the paper. The "sensible defaults … reproducible from a clean checkout" docstring is contradicted by this default.
- **Impact:** Reproducibility footgun.
- **Evidence:** read `config.py:33,55-59`.
- **Suggested fix:** Default `LLM_PROVIDER` to `openai`, or fail loudly if it isn't the provider that produced the committed results.

#### M-08 — exp03 certificate mislabels `re_derivation_score` as the overall max recoverability
- **Location:** `experiments/exp03_planner.py:99-106` (passes `rederivation=plan.residual_recoverability` and `final_recoverability=plan.residual_recoverability`); `planner/optimizer.py:128` (`residual_recoverability = max(residual, rederiv, rho)`).
- **Category:** C.
- **What's wrong:** `plan.residual_recoverability` is the **max over all three channels**, but exp03 stores it in the certificate's `re_derivation_score` field. So that field is not the re-derivation channel; and since `residual=0` is also passed, `floor_reaching = max(0, final) < τ` collapses to equal `completeness_certified`. Numerically harmless **only because ρ≈0 for multi-hop facts** (so max = rederivation); if a multi-hop fact had ρ>0 the field would silently fold ρ into "re-derivation".
- **Impact:** Mislabeled certificate field; the floor-reaching/certified distinction is degenerate for exp03 certs. No current number error.
- **Evidence:** read `exp03_planner.py:99-106` and `optimizer.py:_finalize`.
- **Suggested fix:** Pass the *channel* values separately (the planner has them in `pr.trace`); compute `final` inside `make_certificate`. **Touches certificate construction — approval needed.**

---

### LOW

- **L-01 — Two recovery definitions.** `parametric_probe._recovered` (probe_value substring ∪ LLM-judge, `parametric_probe.py:71-87`) is the live scorer; `evaluation/recovery.numeric_recovered` (number ∪ relative tolerance, `recovery.py:48-61`) scores the exp07 mid-tier tolerance sweep (`exp07:113-119`). Same logged answers, two criteria. Labeled in the docstrings, but "ρ" (headline) and "the floor at each tolerance" (sweep) are not the identical scale. *Clarify in text.*
- **L-02 — Hardcoded constants that look like config.** MIA bootstrap/permutation use `seed=42` hardcoded (`membership_inference.py:41,51,66`), not `config.GLOBAL_SEED`; the ρ "hard floor" bin boundary `0.5` is hardcoded in `exp07:159,173`. Both happen to be the intended values; move to `config` for single-source.
- **L-03 — `value_segment` fallback.** `recovery.py:20-24`: if the answer has no "Value:" marker it returns the *entire* answer, so substring scoring can hit the value inside reasoning text (false positive). The value-first prompt mitigates but doesn't guarantee.
- **L-04 — Refusal over-detection.** `recovery.REFUSAL_MARKERS` (`recovery.py:64-68`) includes generic tokens ("cannot", "insufficient", "no information") that can appear in committed answers → may over-count refusals. Direction is conservative for the ρ-lower-bound framing.
- **L-05 — `chat_json` returns `{}` on parse failure** (`llm.py:71-83`); callers default conservatively (entailment → "NO" capped ≤0.2; twin → original text). A persistent judge-format failure would silently push results toward "not recovered"/"no entailment". Add a counter/log of empty-parse rate.
- **L-06 — Cache write is whole-file, last-writer-wins** (`llm.py:30-32`). Under concurrent *processes* (e.g. two experiments at once) each holds its own in-memory `_cache` and overwrites the file → lost cache entries → redundant **paid** calls (cost, not correctness). Budget footgun (§4-F).
- **L-07 — PARTIAL entailment can fire.** `entailment_detector.py:50-51` caps only "NO" to ≤0.2; a "PARTIAL" with confidence > 0.5 still returns >0.5 and (under M-04) would co-delete, despite the comment "PARTIAL shouldn't read as a full recovery." With gpt-4o this is rare; worth a guard.
- **L-08 — Adapter contract under-specified.** `systems/base.py:24` declares `query(user_id, query)` but it's called as `query(user_id, q, top_k=1, threshold=0.0)` (`membership_inference.py:24`); `inject_fact` gains `infer`. Mem0 implements the extended signature; **NEEDS-VERIFICATION that `zep_adapter`/`letta_adapter` accept the same kwargs and that `memory_text` extracts the right field for each** (a wrong field would mis-measure residual cross-system).
- **L-09 — Design/implementation drift.** The design names `embedding_neighbor` and `summary_residue` probes; neither exists as a file (`probes/` has exact_match, paraphrase, kg_node_residue, parametric, membership_inference, base). The recoverability `max` in practice uses exact_match (residual) + run_rederivation + estimate_rho; the embedding-neighbor channel is not implemented. Confirm the paper doesn't claim an embedding-neighbor probe.

---

## 3. Verified-correct (what you *can* trust)

- **ρ sampling is NOT cache-collapsed.** `estimate_rho` passes `use_cache=False` for its temp-0.7 draws (`parametric_probe.py:111`) — genuinely independent samples. (This was my top initial worry; it's handled.)
- **Recoverability = max over three independent channels.** `certificate/emitter.py:50-51`, `planner/optimizer.py:39-43,128`, `exp04:100`, `exp07:138`. Residual (`exact_match` scans `list_memories` text), re-derivation (`run_rederivation` gives the surviving store + world knowledge), and ρ (`estimate_rho`/`run_parametric` condition on `world_context` only, never the store — `_ELICIT_CTX` explicitly says "NO access to any records"). No cross-channel leakage.
- **Parametric probe runs with memory genuinely off** — conditions on the `world_context` string only; never reads the adapter.
- **Statistics are correct.** `wilson_ci` (`stats.py:25-39`) is the textbook Wilson score interval, clamped to [0,1], nan at n=0. `bootstrap_mean_ci` is a correct percentile bootstrap, seeded. `auc` (`membership_inference.py:30-37`) is the Mann-Whitney AUC and the test suite checks it within 1e-6 of `sklearn.roc_auc_score`. `permutation_p` and `bootstrap_ci` are correct. CIs are applied to the right k/n (`exp04:137-138`, `exp07:98-100,184`, `exp03:116-117`).
- **Certificate logic is correct.** `final = max(residual, rederivation, rho)`; `floor_reaching = max(residual, rederivation) < τ`; status COMPLETE(<τ)/PARTIAL(<0.5)/INCOMPLETE(≥0.5). The 13 status-boundary tests pass. `judge_recall` is resolved from the latest `judge_validation_*.json` with a documented fallback.
- **Worst-adversary ρ and the certifiable count are computed, not hardcoded.** `exp07:131` `max(rho_by_fact[...].values())`; the 27/49 certifiable and the bimodality verdict are derived from the certs (`exp07:164-194`).
- **Data integrity holds.** All 4 datasets have **uniform schemas** (every key present on every record — no "field missing on most records" bug), and each experiment loads the dataset that actually carries the fields it reads (exp07→ρ-gradient has `subject`/`world_context`/`tier`; exp03/04→multi-hop has `co_delete_required`/`rederivation_basis`/`delete_value`). Required `["id"]/["text"]/["probe_value"]` accesses are safe.
- **Deletion is content/search-based and verified.** `delete_value_rows` uses the narrow `delete_value` (not the broad `probe_value`) so residual-cleanup doesn't remove operands (`optimizer.py:53-55`, `exp04:81`); `Deleter.delete_records` re-lists and reports failures rather than swallowing them.
- **Judge/entailment calls are deterministic** (temperature 0.0) and cached; `value_twins` is temp 0.0.
- **Seeds are set** in exp01/02/03/04/07 (`random` + `numpy`); MIA stats are internally seeded.
- **Offline test suite: 46/46 pass.**

---

## 4. Open questions for the author

1. **Recovery judge (H-01):** is `_judge_recovery` *intended* to use the reasoner (`self.model`), or should it be locked to `config.JUDGE_MODEL` for all reasoners? The validation only covers gpt-4o-mini.
2. **Planner cutoff (M-04):** should the planner co-delete at `ENTAILMENT_THRESHOLD` (0.50) or at `τ` (0.10)? Right now `ENTAILMENT_THRESHOLD` is effectively dead.
3. **Defaults (M-02/M-05/M-07):** should the *defaults* (entailment model, `--n`, `LLM_PROVIDER`) be the ones that reproduce the paper, given a reviewer will run them blind?
4. **Multi-hop gate (M-03):** is gpt-4o-mini the intended judge for the near-miss dataset gate, knowing its 41.7% false-fire rate selects the kept facts?
5. **Cross-system adapters (L-08):** do `zep_adapter`/`letta_adapter` honor the extended `query(..., top_k, threshold)` / `inject_fact(..., infer)` signatures, and does `memory_text` extract the correct field for each? (Not reviewed in depth — would confirm the exp09/10/11 residual measurements.)
6. **exp03 certificate (M-08):** intended to store the overall max in `re_derivation_score`, or the channel value?

---

*End of report. No code was modified. Awaiting your direction on which findings (if any) to fix, per §6 — Critical/High first, smallest safe diffs, methodology changes flagged for explicit approval.*
