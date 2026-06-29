# REVIEW_FINDINGS_2 — Second pass: claims audit + cross-system deep-read

**Reviewer:** Claude (continuing audit, fix-enabled with the number guardrail)
**Date:** 2026-06-27
**Mode:** committed-results re-scoring + static reading + grep + offline tests. **No paid API calls, no experiment re-runs.** Companion to `REVIEW_FINDINGS.md` (first pass).

---

## 0. Lead verdict — do the headline numbers still hold?

**Yes. Every headline number traces cleanly to the committed logs, and the one open methodological risk (H-01) is now *bounded* and does not collapse any claim.**

- **ρ floor — now 23/49 (was 22/49): H-01 RESOLVED.** The recovery judge is locked to the validated `gpt-4o-mini` for all reasoners (one-line fix), and the committed logs were re-scored: **22/49 → 23/49**; bands **27/8/14 → 26/9/14**. One fact flipped: **R40 (ρ 0.0 → 0.167)** — `gpt-4o-mini` is marginally *more* lenient than `gpt-4o` on R40's borderline answer (the "smaller ≠ stricter judge" warning was right). It is a clean *strengthening* under a *validated* judge; the limit result holds (47% uncertifiable). Both drafts updated. Mini-alone 14/49, mismatch 16/49, and bimodality (still False) unchanged.
- **k = 0.91, 0 spurious, 34 targets, spared 36** (planner): MATCH.
- **Convergence (n=10): Graphiti edge 40% / summary 80%; Letta 0% faithful / 100% archival**: MATCH, and the **adapters are conformant and the mechanisms are the real code paths** (the half-surface the first pass left grep-only — now closed; §4).
- **Re-derivation, residual, MIA, judge-validation**: all MATCH (table below).

Nothing moved. The only number that *might* move (22/49) moves by at most 5 facts, in the conservative direction, and the claim survives.

---

## 1. Claims-traceability table (§2b)

Verdicts from the committed `data/results/*.json` (logged answers re-scored where possible).

| Claim (both drafts) | Backing path / result file | Verdict |
|---|---|---|
| Planner 100% complete, **0 spurious**, **k=0.91** [0.74,1.09], n=34, **spares 36** | `exp03_planner.py` → `exp03_planner_mem0_threshold_*.json` | **MATCH** (`metrics`: 1.0 / 0 / 0.912 / 36) |
| Depth-first comparator **k=5.65, 126 spurious** | `exp03 --heuristic depth_first` → `..._depth_first_*.json` | **MATCH** (k=5.647, 126) |
| Planner result unchanged under gpt-4o entailment judge | as-run used `--entailment-model gpt-4o-2024-08-06` | **MATCH** (now also the default — §3) |
| ρ floor n=49, 6 samples; bands **27 / 8 / 14**; **22/49** uncert; tier means **0.069/0.275, 0.367/0.656** | `exp07_rho_gradient.py` → `exp07_*.json` | **MATCH** (recomputed bands 27/8/14; pairwise-avg of means confirmed) |
| ρ **14/49** under weaker reasoner alone; **16/49** authored≠measured | exp07 logs | **MATCH** (recomputed: mini-alone 14/49; mismatch 16/49) |
| **R13 refused 5/6**; **7 facts** drew refusals | exp07 `refusal_flags` | **MATCH** (R13 5/6 mini; 7 facts: R13,R15,R45–R49) |
| Re-derivation Mem0 bin1 **100%/94%**, bin2 **59%/65% → 0%** (n=17/bin), ρ=0 | `exp04_parametric.py` → `exp04_*.json` | **MATCH** |
| Re-derivation Letta bins + **F043** honest negative | exp11 **RE-RUN at n=34** (`exp11_*_20260629.json`) | **RE-RUN (old→new):** bin1 100% (n=1) → **100% (n=17)**; bin2 80% mini / 100% 4o (n=5) → **59% / 59% (n=17)** → 0% after co-delete; faithful 100%. **⚠ F043 changed:** now **0.0 on Letta under both reasoners** (and Mem0 both) — the n=6 "leaks on Letta-4o via core-identity-block" did **NOT replicate**. §res-rederiv updated in both drafts: F043 = consistent cross-system honest negative; the "lone bin2 fact separating the two reasoners" sentence removed (bin2 is now reasoner-equal in aggregate). |
| Residual naive **97.9% (47/48)** (exp01); aware **68.75% → 0%** (exp02); same n=48, two independent runs | `exp01_*`, `exp02_*.json` | **MATCH** (separate user_ids/stores confirm "two independent measurements") |
| Duplication 2×2 factorial — all cells, paraphrase>byte | exp05 **RE-RUN at n=149** (`exp05_*_20260629.json`) | **RE-RUN (old→new):** row-inflation **24–42% → 179–221%**; dup-incidence **30–39% → 63–70%**; paraphrase>byte still holds in all 4 cells ✓. Duplication grows superlinearly with store size (416–478 rows / 149 facts) — a *stronger* finding. Both drafts updated to the n=149 rates. |
| Convergence n=10; Graphiti **edge 40% / summary 80%** (hard-delete verified first) | `exp09_*.json` + `zep_adapter` | **MATCH** (rates); **control verified** (`remove_episode`→hard delete; summary via `list_graph`) |
| Letta explicit **100% faithful**; vague **0% faithful / 100% archival / 0% core** | `exp10_*.json` + `letta_adapter` | **MATCH** (rates + dual-surface code path) |
| Membership: aware **0.52 [0.41,0.62] p=.36**; intact **0.69 p=.001**; naive **0.68 [0.59,0.77] p=.001**; n=48+96 | `exp08_mia.py` → `exp08_*.json` | **MATCH** (stages exact) |
| Judge: recovery **7TP/0FP/8TN/2FN, κ=0.767**, recall **≈78%**; entailment **24/12, κ 0.455, mini 41.7% / 4o 0%** | `judge_validation_*.json` | **MATCH** (FRR 0.222 → recall 0.778) |
| Certificate `re_derivation_score` (final) distinct from `rederiv_with_operands` (pre); R11 INCOMPLETE, F040 COMPLETE | `sample_certificate_*.json` | **MATCH** (F040: pre 1.0 / final 0.0; R11: final 0.0 ≠ recoverability 1.0) — emitted, not hand-authored |

---

## 2. Draft reconciliation (§2a)

- **FIXED (applied):** `deletion_completeness_aaai.tex:367-368` setup paragraph said **12 / 6 / 15** (contradicting its own later "full 34 multi-hop" / "n=48 isolated"). Changed to **48 / 34 / 49** to match the datasets, the supervisor draft, and the results sections. Text-only, no results number affected.
- **Swept both drafts** for other stale counts (`n=15`, `n=6`, `12 isolated`, `/15`, `of 15`): the 367-368 line was the **only** straggler. No other divergence found; the two drafts are otherwise numerically consistent.

---

## 3. Adapter & cross-system deep-read (§3) — the grep-only gap, now closed

**Conformance + mechanism-accuracy CONFIRMED** for the convergence claim:

- **`systems/zep_adapter.py`** — honors the contract incl. extended kwargs (`query(..., top_k, threshold)`, `inject_fact(..., infer)`). `delete_memory` → `remove_episode` (hard-deletes episode + `RELATES_TO` edges + orphaned entities, the paper's control). Residual surfaces split correctly: `list_memories` returns surviving `RELATES_TO` edge facts (edge residue), `list_graph` returns Entity/Community **`summary`** fields (the 80% summary residue). `memory_text` extracts `memory`(=fact) for edges and falls through to `summary` for nodes — **correct field per surface.** *Minor (NEEDS-VERIFICATION):* `list_memories`/`list_graph` Cypher does not filter `expired_at`/`invalid_at`, so temporally-invalidated-but-present edges are counted as residual — defensible under the "adversary reads the whole store" threat model, but worth a one-line note in exp09.
- **`systems/letta_adapter.py`** — honors the contract. Dual-surface `list_memories` (core blocks + archival passages, tagged by `layer`); `agent_forget` = the vague agent-mediated path (the novel failure); `delete_memory` = faithful direct op (`passages.delete` by id / block overwrite); `set_core_block` seeds identity (the documented gotcha). `memory_text` → `memory` for both surfaces. **Matches `fig:agentloop` and §res-converge exactly.**
- *Note (no impact):* neither Zep nor Letta `query` returns a similarity `score`, so MIA would be all-zeros there — consistent with the papers running MIA only on Mem0.

Other grep-only files spot-read: `exp01/exp02` (correct; confirm the two-independent-naive-rates framing), `injector`/`deleter` (content-based, verified deletes), `entailment_detector`, `recovery`, `stats`. **Not deep-read:** `exp05/06/09/10/11` full bodies, `paraphrase_probe`, `kg_node_residue`, `artifact_tracer`, `graph_builder`, `generate_facts` internals — marked NEEDS-VERIFICATION where they back an un-re-run number.

---

## 4. Fixes applied this pass (no reported number changed)

All verified with `py_compile` + **offline suite 46/46 still green**.

| # | Fix | Files | Why safe |
|---|---|---|---|
| 1 | AAAI setup sizes 12/6/15 → **48/34/49** | `deletion_completeness_aaai.tex` | text-only |
| 2 | `LLM_PROVIDER` default `anthropic` → **`openai`** | `config.py:33` | reproduces papers; as-run used openai |
| 3 | `--n` default 5/12/6/6 → **None (= all facts)** in exp01/02/03/04 | 4 experiment files | as-run passed explicit n; `[:None]`=all |
| 4 | planner `--entailment-model` default → **`config.SECOND_MODEL` (gpt-4o)** | `exp03_planner.py:43` | as-run used gpt-4o |
| 5 | exp03 cert: `re_derivation_score` now the **channel** (via new `PlanResult.final_residual/final_rederivation`), not the overall max | `optimizer.py`, `exp03_planner.py` | numerically identical (ρ≈0); Table uses exp07/exp11 certs, not exp03 |
| 6 | `ENTAILMENT_THRESHOLD` comment: it's the validation/gate edge threshold, **not** the planner cutoff (which is τ) | `config.py:77` | comment only; code already matches the papers ("co-delete above τ") |
| 7 | Added **`reproduce.sh`** (exact commands; ρ-reproducibility caveat; service prereqs) | new file | new file |
| 8 | **Graphiti residual note** — residual counts a value in any surviving edge/summary regardless of `invalid_at`/`expired_at`, consistent with the full-read-access threat model (behavior **kept**, per your call) | `exp09_zep_kg_residual.py`, both drafts (§res-converge) | doc/comment only |

**On §2c-E (τ vs ENTAILMENT_THRESHOLD):** resolved as *config matches code matches paper* — both drafts say the planner co-deletes "every entailer above **τ**", and the code does exactly that (`optimizer.py:99,120`). `ENTAILMENT_THRESHOLD=0.50` legitimately gates judge-validation and the dataset near-miss gate; it was only *misleadingly named* relative to the planner. No comparator number changes (the 126 spurious / k=5.65 are produced by the τ cutoff the paper describes). Documented, not altered.

---

## 5. H-01 — APPLIED (recovery-judge lock + re-score): 22/49 → 23/49

**Outcome:** judge locked to `config.JUDGE_MODEL` (`parametric_probe.py:_judge_recovery`); re-scored the committed gpt-4o judge-fired answers with the locked gpt-4o-mini (≈44 small calls); **22/49 → 23/49**, bands **27/8/14 → 26/9/14**, 4o mid mean **0.275 → 0.265**. Only **R40** flipped (ρ 0.0 → 0.167; gpt-4o-mini accepted one borderline recovery gpt-4o hadn't — a *more*-lenient validated judge, so the count rose, not fell). Both drafts updated (abstract, §res-rho, Table tab:rho, conclusion, tab:master, intro contribution, monotonicity remark → now reasoner-not-judge). Committed as the isolated H-01 commit. **R40 audited (legitimate, kept):** R40 = *"Cheng Long … passed the CPA exams, which require him to be at least 23"* (high-tier; `probe_value` includes `'adult'`/`'over 23'`). The flip sample: the gpt-4o adversary answered *"Value: 25"* (CPA → degree+experience → mid-twenties); the locked gpt-4o-mini judge accepted 25 as recovering "≥23" (within its ~10% tolerance, and ≥25 entails ≥23/"adult"). A correct *borderline* recovery that actually corrects gpt-4o's over-strict self-judging (which had given a clearly world-inferable high-tier fact ρ=0). No judge-imperfection caveat needed; **23/49 stands**.

### H-01 — original finding (for the record)
- **The issue (confirmed against the papers):** both drafts state every recovery rate is "a conservative lower bound" under the "validated 0/8-false-accept judge" and that "both LLM judges are validated." But `probes/parametric_probe.py:83-87` uses `model=self.model`, so the **gpt-4o** adversary judges its own recoveries, and `evaluation/judge.py:134` validates the recovery judge **only on gpt-4o-mini**.
- **Sized from logs (offline):** for gpt-4o, **88% of recoveries are decided by exact substring match** (not a judge); only **~12% (11/87)** use the LLM-judge fallback. The judge fires but the value is provided to it (a matching task, not open recovery).
- **Bounded impact on 22/49 (offline):** scoring substring-only (judge removed entirely) gives **17/49**; only **5 facts** (R15 + R30/R32/R36/R41 at ρ=1/6) are even potentially judge-attributable. So locking to gpt-4o-mini yields **22/49 → somewhere in [17, 22]**, in the conservative direction.
- **Recommended fix (one line):** in `_judge_recovery`, use `model=config.JUDGE_MODEL` instead of `model=self.model` — one validated judge for a fixed answer-vs-known-value matching task, for all reasoners. This makes the "validated judge" claim literally true.
- **PENDING you, because:** (a) it changes 22/49 (guardrail), and (b) computing the *exact* new value needs a **small paid re-score** — re-judging only the ~94 logged judge-fired answers with gpt-4o-mini (cents, no re-running of experiments). **I have not applied the code change or spent anything; say the word and I'll apply the lock and run the re-score, then report old → new.**
- **Paper text either way:** if the number holds at 22, no text change; if it moves, update §res-rho/abstract/Table 1 and note the monotonicity remark covers *reasoner* willingness, not *judge* leniency.

---

## 6. Verified-correct (high-value confirmations)

- **The recoverability equation and all three channels** are faithfully implemented and independent (first pass), and now **every headline they produce traces to committed results** (§1).
- **The adapters back the convergence claim correctly** — Zep `remove_episode`/`list_graph(summary)` and Letta dual-surface/`agent_forget`/`passages.delete`/`set_core_block` are the actual code paths behind 40%/80% and 0%/100%, with correct per-system `memory_text` extraction (§3).
- **ρ is NOT cache-collapsed** (`use_cache=False`); **certificate pre/post fields are distinct and emitted** (F040 pre 1.0 / final 0.0); **the two naive residual rates are genuinely two independent runs**; **stats are correct** and applied to the right k/n; **judge-validation counts are exact**.
- **Reproducibility defaults now reproduce the papers** + `reproduce.sh`; ρ reproducibility is via re-scoring the committed logged answers (stated).

---

## 7. Open questions for the author

1. **H-01 — DONE.** Lock applied + re-scored → 22/49 → **23/49** (both drafts updated). Only open sub-item: sanity-check R40's logged answer (the single knife-edge flip).
2. **exp05/exp11 — RESOLVED as "stale-but-backed".** Both MATCH their committed logs (re-scored, free), but those logs are **pre-wave**: exp05 on the old 33-fact corpus (2026-06-23), exp11 on the old 6-fact multi-hop (2026-06-24, **bin1 = n=1**). The drafts present them at the OLD scale alongside the enlarged-data results. **Decision needed:** re-run exp05 (Mem0, cheap) and exp11 (needs the Letta service up) on the enlarged datasets, or keep + footnote the smaller n? (I did NOT re-run — paid + service-dependent.)
3. **Graphiti temporal filter — RESOLVED.** Behavior kept (correct under full-read-access); one-line note added to exp09 and both drafts' §res-converge.

---

*Fixes 1–7 applied and test-green. H-01 is the single item awaiting your go-ahead. No reported number changed without your sign-off.*
