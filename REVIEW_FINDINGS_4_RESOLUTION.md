# REVIEW_FINDINGS_4 — Resolution log

**Date:** 2026-07-02. Companion to `REVIEW_FINDINGS_4.md`. Records how each RF4
finding was resolved. All numbers verified against re-runs on the fixed dataset;
paper edits are surgical (both drafts). **Two items need OpenAI credits to finish
(429 insufficient_quota mid-session) and are marked BLOCKED.**

## Critical

### C-01 — "isolated" set shared probe values → exp02 naive arm corrupted — **FIXED**
Confirmed real: 10 facts shared exact values (`9123-4567`, `AB+`, IMEI, park);
in the committed exp02, **13/15 naive-"successes" had `value_rows_before=0`** —
pre-purged by an earlier same-value fact. Fixes:
- **Dataset:** regenerated **16** colliding facts to globally-unique high-entropy
  values (phones/IMEIs/park/account; dropped bare "coffee" from F111; converted 4
  nesting blood-type facts to unique medical facts). 0 collisions under a
  digit-normalizing check across the full isolated+context store.
- **Gate:** new `check_value_uniqueness()` in `data/validate_facts.py`, wired into
  PASS/FAIL (it caught a *pre-existing* F113⊂F115 collision). Fixed `build_isolated`
  id-reuse.
- **exp02:** two separated passes (all naive first, then all aware purges) —
  contamination-proof regardless of value overlap.
- **Re-run (old→new):** exp01 97.9%→**95.8%** (46/48); exp02 naive **68.75%→91.7%**
  [80.5,96.7], **0/48** naive-zeros are now contamination (was 13/15); aware 0%.
  The two naive arms (95.8% vs 91.7%) now **converge**, turning the falsified
  "two independent measurements / stochastic dedup" sentence into a true one.
- **Papers/ledger/README:** all propagated; cross-subject-collateral concern is
  moot (unique values → aware purge touches only the fact's own rows).

## High

### exp05 dup-incidence confound — **FIXED**
Confirmed: 32/149 (21.5%) of facts' values appeared in another fact's text.
Metric now denominates over **corpus-unique** facts only. Re-run: dup-incidence
**63–70% → 76–78%** (clean), paraphrase-dominant in all 4 cells. Drafts reframed;
the confounded "30–39%→63–70% scale" sentence removed.

### H-04 — self-contradictory judge-robustness claim — **FIXED**
Ran exp03 with `gpt-4o-mini` entailment: k **0.91→1.0**, spurious **0→2** (mini
false-fires). So the planner result is judge-**dependent**, not robust. Both
drafts reworded ("we use gpt-4o deliberately … prevents k inflating", backed by
the mini numbers). Provenance (`entailment_model`, `heuristic`, `n_bystanders`)
now recorded in exp03's JSON.

### H-03 — conflicting ρ tier annotations — **FIXED**
Stripped the baked-in `measured_rho/measured_tier/tier_flag` (196 fields, a third
MC draw with 0.25/0.65 boundaries → 18/49) from `rho_gradient_facts.json`; ρ is
now measured only by exp07 (τ=0.10/0.5 → the paper's 16/49). Aligned
`validate_facts.TIER_LO_HI` to `(config.TAU, 0.5)`. Nothing read the stripped
fields (verified). Paper unchanged (it already used exp07's 16/49; the
contradiction was dataset-side).

## Medium

- **M-09** planner pool — **DISCLOSED** (pool = operands + 4 fixed bystanders,
  stated in both drafts as a controlled set; full-pool stress test = future work).
  A `--bystanders 34` run was attempted but **BLOCKED** (quota).
- **M-10** depth-first is clamp-driven — **FIXED**: reframed in both drafts as an
  unfiltered co-delete-all upper bound whose τ filter is inert under the 0.2 NO
  clamp (consistent with RF3/H-02).
- **M-11** judge-validation vintage — **DISCLOSED / BLOCKED**: the 41.7% false-fire
  rests on the original F040–F045 near-miss bench; extending it to the enlarged
  set + re-running `judge.py` needs credits (quota).
- **M-12** README contradictions — **FIXED**: three-channel wording, current MIA
  numbers, fixed the crashing `exp08_mia.py --n 6 --corpus 27` command, marked the
  pre-wave results table as superseded with a pointer to the paper/status report.
- **M-13** date drift — **FIXED**: `config.EXPERIMENT_DATE` pins the prompt/cache
  date instead of `date.today()`.
- **M-14** live key in archive — **user action** (rotate + exclude `.env`).
- **ρ-Def scope** (Claude Code #2) — **FIXED**: the "6 draws at T=0.7 throughout"
  is scoped to the ρ-gradient; exp03/04/11 carry the single-draw T=0 point estimate.
- **`validate_recovery_judge` arg** — **FIXED**: no longer mislabels the locked judge.
- **exp04/exp11 primary-reasoner certificates** vs worst-adversary schema — **NOTED /
  BLOCKED**: emitting max-over-reasoners ρ needs a two-reasoner re-run (quota); the
  ρ-gradient (exp07) already reports the worst-adversary floor that the paper cites.

## Low / hygiene — FIXED
exp11 `--n` default→all; exp09 `--communities` toggleable + `PAIRS[:None]` no-op
removed; reproduce.sh now runs exp05/exp11. Remaining Lows (dead code
graph_builder/artifact_tracer, `parse_number` "km", cache O(n²), bib placeholders)
are catalogued for a cleanup pass.

## Update — completed (credits restored + parallel subagent cleanup)
Supersedes the "DISCLOSED/BLOCKED" statuses above.
- **M-09 — DONE.** Full 34-bystander planner run: **100% complete, k=1.0, 0 spurious** —
  selectivity holds against a realistic pool, not just the 4 fixed distractors. Both
  drafts now report it (was "future work").
- **M-11 — DONE.** Entailment near-miss bench broadened from 12 curated to **78**
  negatives (12 curated + 66 single-operand, generated from the multi-hop corpus).
  Curated result reproduces exactly (mini **41.7%** / gpt-4o **0%**); on the fuzzier
  single-operand set both fire more (mini **72.7%** / gpt-4o **50%**), gpt-4o still
  the more conservative. Recovery-judge 0% false-accept holds. Drafts + tab:master
  updated.
- **exp04/exp11 worst-adversary certs — DONE (code).** Both emit ρ = max over
  reasoners into the cert (Def. 4); per-reasoner row logging unchanged; stable
  model-slug uids (L-13). exp04 re-run confirms ρ_worst = 0 for multi-hop, so cert
  numbers are unchanged. exp11 is code-fixed but not re-run (needs Letta); committed
  06-27 exp04 stays canonical.
- **Date pin corrected.** `EXPERIMENT_DATE` → **2026-06-27** (the canonical wave
  date) so date-sensitive re-derivation reproduces the paper; a 07-02 exp04
  transient (bin2 drift 59→65 from the wrong date) was discarded.
- **Lows via parallel subagents — DONE.** L-10 planner completeness → floor-reaching
  (excludes ρ; mirrors the cert's `floor_reaching`); L-11 depth-first missing-purge
  documented; L-14 exp10 prefers the row's `layer` field (forward-compatible). Plus
  earlier: dead `graph_builder`/`artifact_tracer` removed, `parse_number` "km" fixed,
  cache batched O(n²)→O(n/50).

Still open (needs **Letta**, not credits): a two-reasoner exp11 re-run to regenerate
its certificates under the already-applied worst-adversary code.
