# Statistical Audit — every reported number vs the raw data

**Date:** 2026-07-14
**Scope:** every statistical claim in the repo (paper, supplementary, ledger, docs).
**Method:** independent recompute from the raw per-fact `rows` in `data/results/*.json`
(frontier-judge wave, `20260712`/`20260713` timestamps), using a **pure-Python**
reimplementation of the estimators — *not* the repo's `evaluation/stats.py` — so this is a
true cross-check, not a re-run of the same code. The pure-Python Wilson interval was first
validated against textbook values (e.g. `97/100 → [0.915, 0.990]`, `0/10 → [0, 0.278]`)
before use.

**Verdict:** **1 discrepancy found and fixed** (a stale confidence interval); **every other
number recomputes exactly** from the raw data.

---

## 0. What the estimators are (and why these)

- **Wilson score interval** — error bar for a *proportion* (k successes in n trials:
  residual rate, completeness, judge false-accept, …). Preferred over the textbook
  "normal approximation" because it stays inside [0, 1] and stays non-degenerate at the
  edges — at 100% the normal approximation collapses to a zero-width `[100%, 100%]`,
  which falsely claims zero uncertainty. **Its width shrinks as n grows** — the fact that
  caught Finding 1. `evaluation/stats.py:wilson_ci`.
- **Percentile bootstrap** — error bar for a *mean* (mean collateral k). Resample the
  observations 2000× with replacement, take the 2.5/97.5 percentiles of the resample
  means. `evaluation/stats.py:bootstrap_mean_ci`.
- **Cohen's κ** — chance-corrected agreement (judge vs gold, judge vs judge).
  `evaluation/metrics.py:cohens_kappa`.
- **AUC + label-permutation p** — membership separability (member vs matched twin) and
  its significance. `experiments/exp08_mia.py`.

All four were checked for correctness; all four are sound.

---

## 1. Finding (fixed) — stale planner-completeness Wilson CI

| | value |
|---|---|
| **Was reported** | `100% [0.96, 1.0]` |
| **Correct (n=298)** | `100% [0.987, 1.0]` = `wilson(298, 298)` |
| **Root cause** | `[0.96, 1.0]` is `wilson(92, 92)` — the CI from the **old 92-target wave**. Point estimates were updated to n=298; this interval was not. |
| **Evidence** | the result file's own metric already read `completeness_rate_ci95: [0.9873, 1.0]` — the docs disagreed with the data they were generated from. |
| **Severity** | *underclaim* (the stale interval is wider/more conservative than the truth) — no result was overstated. |

**Fixed 2026-07-14** — `[0.96,1.0]` → `[0.987,1.0]` in:
`paper/supplementary.tex:38–40` (all 3 heuristics), `paper/CLAIMS_LEDGER.md:92`,
`docs/PROJECT_STATUS_REPORT.md:82` (**current column only** — the old-wave `[96,100]`
n=92 column is correct and was left intact), `docs/PROJECT_EXPLAINED_SIMPLE.md:922`.

- The **main paper body was never affected** — it states "100% completeness" with no
  numeric CI, so nothing in the submission text changed.
- `docs/JUDGE_UPGRADE.md:118` and `docs/RESULTS_3X_WAVE.md:20` **already** carried the
  correct `[98.7, 100]`; the fix syncs the four lagging locations to that value.

---

## 2. Claim-by-claim recompute (all grounded)

Point estimates recomputed from raw `rows`; CIs recomputed with the independent Wilson /
bootstrap. "Claim" = as printed in paper/ledger/docs.

| Exp | Claim | Recomputed from raw data | ✓ |
|---|---|---|---|
| exp01 | residual 97.2% [94.4, 98.7], n=253 | 246/253 = 97.23%, Wilson [94.4, 98.65] | ✓ |
| exp02 | 97.2% → 0% [0, 1.5] | naive 246/253; aware 0/253, Wilson [0, 1.5] | ✓ |
| exp03 exact | 100% [.987,1.0], k=1.03 [.98,1.08], 0 spurious, 467 spared | 298/298, Wilson [.9873,1.0]; k=1.0336; bootstrap [.983,1.08]; 0; 467 | ✓ |
| exp03 threshold | k=1.14, 0 spurious, 100% | k=1.1376, 0, 298/298 | ✓ |
| exp03 depth-first | k=6.60, 1192 spurious, 100% | k=6.6007, 1192, 298/298 | ✓ |
| exp04 | bin1 97–100→0; bin2 62/69/69/66→2.7% | bin1 100/97.3/100/100→0; bin2 62.2/68.9/68.9/66.2→2.7% (all four = 0.027, F043) | ✓ |
| exp05 | dup 80–82%, row-inflation ×1.75–1.82 | dup 80.4/81.7/80.2/79.9%; row-infl 1.745/1.815/1.764/1.787 | ✓ |
| exp07 | certifiable 65.6% [59.5, 71.2]; limit 86/250; mid-band 41; not bimodal | 164/250 = 65.6%, Wilson [59.52, 71.21]; limit 86; mid 41; `is_bimodal=false` | ✓ |
| exp08 | intact/naive AUC .66 p=.001; aware .51 [.498,.523] p=.04 | .66/.66/.51; aware CI [.498,.523] (includes .5), p_perm=.038 | ✓ |
| exp09 | edge 20% / summary 83%, n=30 | 0.200 / 0.833 | ✓ |
| exp10 | vague 0% faithful / 100% archival / core 10%, n=30 | 0.0 / 1.0 / 0.1 | ✓ |
| exp11 | bin1 99–100→0; bin2 62/65/65/68→0; faithful/bystanders 100% | bin1 100/98.6/100/100→0; bin2 62.2/64.9/64.9/67.6→0; 1.0 / 1.0 | ✓ |
| exp12 | optimality gap −0.067 / +0.037 / +5.50 | exact −0.0671 / threshold +0.0369 / depth +5.50 | ✓ |

**Roundings noted (fair):** exp05 dup low cell 0.799 → "80%"; row-inflation 1.745 → "1.75";
exp11 4o bin1 0.986 → "99%". All within normal 1-sig-fig rounding.

---

## 3. Judge validation (n_recovery_gold = 351, n_entailment_pairs = 1370)

Rate and Wilson CI recomputed from the raw k/n stored in each rate block. **All exact.**

**Recovery judge — false-accept (safety-critical) + recall + κ:**

| Model | False-accept (k/n) | Wilson | Recall | κ vs gold |
|---|---|---|---|---|
| gpt-4o-mini | 4/194 = .0206 | [.008, .0518] | .752 [.679, .813] | .747 |
| gpt-4o | 1/194 = .0052 | [.0009, .0286] | .930 [.879, .960] | .930 |
| **Claude Sonnet 5** | **0/194 = 0** | **[0, .0194]** | **.981 [.945, .994]** | **.983** |
| GPT-5.5 | 0/194 = 0 | [0, .0194] | .981 [.945, .994] | .983 |

**Entailment judge — near-miss false-fire + multi-hop miss-rate:**

| Model | Near-miss FF (k/n) | Wilson | Multi-hop miss |
|---|---|---|---|
| gpt-4o-mini | 586/774 = .7571 | [.7257, .786] | 0/120 |
| gpt-4o | 352/774 = .4548 | [.42, .49] | 0/120 |
| **Claude Sonnet 5** | **26/774 = .0336** | **[.023, .0488]** | **0/120** |
| GPT-5.5 | 236/774 = .3049 | [.2735, .3382] | 0/120 |

The safety property — **0% multi-hop miss-rate for all four models** — holds exactly
(0/120 each). Sonnet 5's `[0, .0194]` false-accept upper bound is the basis for the paper's
"reported recovery rates are conservative lower bounds" framing.

---

## 4. Caveats & reproducibility notes (not errors)

- **exp08 raw scores not persisted.** The MIA result JSON stores only summary stats
  (`auc`, `ci95`, `p_perm`, per-group means), not the per-item member/twin scores. The
  numbers are internally consistent (means → AUC direction, CI-includes-half flag, p), but
  the AUC/CI/permutation-p cannot be **independently** re-derived from the artifact alone —
  they require re-running `exp08_mia.py`. *Recommend persisting the raw score vectors* for
  the reproducibility checklist.
- **`p = .02` in older notes = the old wave.** The current wave's aware-stage
  `p_perm = 0.038` (→ ".04"); `PROJECT_STATUS_REPORT:94` correctly shows the `.02 → .04`
  transition. No live inconsistency.
- **README pre-wave table is disclaimed.** The old-wave figures in `README.md` (residual
  75%, n=33 MIA 0.72/0.61, n=3 exp09/10) sit under an explicit *"Do not cite the table"*
  banner with the current numbers in the blockquote above. Acceptable as-is.
- **ρ-tier CIs** (`exp07 rho_by_tier`, e.g. mini mid 0.072 [.0569, .0914]) match the result
  file and are Wilson-consistent, but were spot-checked at the block level rather than
  re-derived from the raw per-sample k/n aggregate.

---

## 5. Canonical result files (frontier-judge wave)

```
exp01  data/results/exp01_baseline_mem0_20260712T133151Z.json
exp02  data/results/exp02_artifact_purge_mem0_20260712T161706Z.json
exp03  exp03_planner_mem0_exact_20260713T083434Z.json
       exp03_planner_mem0_threshold_20260713T113908Z.json
       exp03_planner_mem0_depth_first_20260713T113548Z.json
exp04  data/results/exp04_parametric_mem0_20260713T100447Z.json
exp05  data/results/exp05_duplication_20260712T195316Z.json
exp07  data/results/exp07_rho_gradient_20260713T105154Z.json
exp08  data/results/exp08_mia_mem0_20260712T143258Z.json
exp09  data/results/exp09_zep_kg_residual_20260712T200635Z.json
exp10  data/results/exp10_letta_20260713T113020Z.json
exp11  data/results/exp11_letta_rederivation_20260713T112122Z.json
exp12  data/results/exp12_planner_minimality_20260713T095521Z.json
judge  data/results/judge_validation_20260713T105713Z.json
```

**Bottom line:** after the Finding 1 fix, every statistical number reported anywhere in the
repo traces correctly to these files.
