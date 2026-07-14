# Response plan: external reviewer critique (pre-expansion) + Tan's feedback

**Date:** 2026-07-14. The external review targeted the **pre-expansion** paper; much of it is
already answered. This maps every point to current state + action. Numbers verified in
`docs/reviews/STATS_AUDIT.md`.

---

## A. Re-run scope (Muhammad's question: if we re-run for the certification stat, how many experiments?)

**Only ONE experiment: `exp07` (rho_gradient).** It is the sole experiment whose headline
depends on per-fact ρ sampling. Not the others:

- `exp03` / `exp12` (planner) — DAG-deterministic; completeness/collateral don't depend on sampling.
- `exp04` / `exp11` (re-derivation) — ρ ≈ 0 throughout (synthetic subjects); not the certification number.
- `exp08` (MIA), judge validation — separate, already adequately powered (194 negatives, 1,370 pairs).

**Why exp07 and the sample math.** Certification = ρ < τ (τ=0.1). To make it a real *confidence
bound* (UCB < τ) rather than a point estimate, with 0 observed recoveries you need n ≥ 29
(one-sided 95%: `1 − 0.05^(1/n) < 0.1`). Current design = **8 samples/reasoner**.

| Design | trials/fact | 95% UCB at 0 recoveries |
|---|---|---|
| per-reasoner, 8 samples (reviewer's assumption) | 8 | 31.2% ✗ |
| pool the 4-reasoner panel (current data, no re-run) | 32 | **8.9%** ✓ (borderline; models correlated) |
| re-run exp07 at 30 samples/reasoner | 30 | 9.8% ✓ per-reasoner (clean) |

**Cost of the exp07 re-run** (generations = facts × reasoners × samples × 2 for context+baserate):
- current: 250 × 4 × 8 × 2 = **16k**
- full re-run @30/reasoner: 250 × 4 × 30 × 2 = **60k** (~3.75×)
- **sequential (recommended):** keep the 8 already collected as a screen; draw 22 more only for
  the ~205 non-decisive facts → **~36k additional**, ~52k total. Frontier models (Sonnet 5,
  GPT-5.5, gpt-4o) dominate cost; gpt-4o-mini is cheap. Sequential is the reviewer's own
  cost-reduction suggestion.

**Cascade if re-run:** shifts 86/250, the 164 certifiable, the 41-fact mid-band, and possibly
the R11 certificate example → abstract + results + cert figure need the new numbers.

**Cheaper alternative (no re-run):** adopt the **pooled-panel UCB** (0/32 → 8.9%), recompute
`certified` as UCB < τ from existing data, and state the model-correlation caveat honestly.
This answers the reviewer's #1 without spending compute. Decide with Tan.

---

## B. Reviewer triage — already fixed vs still open

**Already answered by the expansion (do not re-litigate):**

| Reviewer objection | Status |
|---|---|
| "Minimal co-deletion overstated; solve exact optimum, report gap, test high-arity/chains" | ✅ exp12: exact min-hitting-set + optimality gap ≈0 (≤0 every topology), 6 topologies |
| "Zero false-accepts on only 8 negatives (UCB 0.32)" | ✅ now 0/194, Wilson UCB 0.019; 351 gold, 1,370 pairs |
| "Comparator deliberately weak" | ✅ added re-probing threshold greedy (k=1.14) + true k* |
| "Only 10 targets/system" | ◑ exp11 now n=298; exp09/10 n=30 (from 3) |
| "Base-rate control should be central" | ✅ `context_lift = ρ_context − ρ_baserate` already logged per fact — feature it |
| "Novelty overlaps P2E2 / Agentic Unlearning / ForgetEval" | ✅ paper already hedges honestly (lines 140, 183) — keep |

**Still open — act before July 21:**
1. **Certification statistic** — §A above. UCB reframe (cheap) or exp07 re-run.
2. **Headline reframe** — §C.
3. **Language fixes** — §D.

**Future work (say so; not feasible by deadline):** organic/longitudinal benchmark,
counterfactual never-saw-it baseline, human blind annotation.

---

## C. #2 — Reframe the headline (scaffold; rewrite in your voice)

Good news: the abstract **already leads with the framework**, and the floor is contribution #3,
not #1. So this is a tone tweak, not surgery. Do:

- Frame **86/250 as a property of *this benchmark + threshold + panel*, not a law** ("not '34% of
  facts can't be forgotten'"). One clause in the abstract + results.
- Lead the **Results narrative** with the cross-architecture failures (Mem0 duplicates, Graphiti
  stale summaries, Letta archival residue) + the planner, and present the floor as the
  *boundary condition* that bounds what any deletion can achieve.
- Contribution ordering to voice: (1) three-channel decomposition, (2) minimal co-deletion
  planner + measured optimality, (3) the certificate, (4) cross-architecture evidence,
  (5) the world recall as a measured boundary — **not** the lead.

## D. #3 — Language fixes (specific)

- **Legal framing (line ~914, "Right-to-be-forgotten compliance…"):** soften — your criterion is
  *stricter* than controller-side erasure; don't equate the ρ-floor with GDPR non-compliance.
  Your certificate already encodes the reviewer's 3-way split (`floor_reaching` = stored + system
  inference closed; `completeness_certified` = also below the external floor; R11 = the limit
  case). Say that explicitly; call the third condition *world-inferability*, not *incomplete deletion*.
- **Novelty:** already honest (lines 140, 183) — leave as is; if anything, sharpen "integration +
  operationalization" wording.
- **Oracle-DAG relativity → first-class certificate field.** Add a field (e.g.
  `graph_coverage`/`entailer_discovery`) recording that completeness is relative to discovered
  paths, and report entailment-discovery recall (0% multi-hop miss) separately from planning
  quality. This is a `certificate/schema.py` + emitter change (code, not prose) — can do on request.
- **Chakraborty citation at NP-hardness:** ✅ DONE — added `\citep{p2e2}` to Prop 1 (line 285).

---

## E. De-stale status (Tan: "make sure nothing is stale")

- **Paper numbers are already current:** abstract 86/250, 298 targets, 250 facts, judge 351/194/
  1,370, residual 97.2% — all match the data. The one stale number ([0.96,1.0] CI) is fixed.
- **Remaining non-number paper items (Tan):** "early version" phrasing (line 859) → your voice;
  `\S\ref` → "Section~X" (×41, pending Tan's sample); "Salman" rename (thematic — chosen);
  define SDR (= σ_red) at first use; italic vs \texttt for function names — pick one.
- **Docs:** README pre-wave table is disclaimed ("Do not cite the table"); `docs/reviews/REVIEW_FINDINGS*`
  are historical logs (old numbers expected). Live docs (RESULTS_3X_WAVE, JUDGE_UPGRADE,
  PROJECT_*) are current post-fix.

**Policy for edits:** I de-stale *facts/numbers* and make *markup* changes (citations, section
format) directly; *prose voice* (reframe, legal softening, "early version" wording) I scaffold —
because Claude-written prose re-inflates the AI-detection score you're trying to lower.
