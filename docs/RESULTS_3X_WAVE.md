# 3× Wave Results (2026-07-12/13)

Headline numbers from the hardened re-run at ~3× scale (datasets: isolated **253**,
multi-hop **298**, context **963**, rho **250**). Adversary panel: gpt-4o-mini, gpt-4o,
Claude Sonnet 5, GPT-5.5. τ = 0.10. Judges pinned: recovery gpt-4o-mini, entailment
gpt-4o (both validated across all 4 models). This file is the source for propagation.

Correctness note: rho/re-derivation were re-run with `probes/parametric_probe` hardened so
a rate-limit/timeout can never be miscounted as a refusal (re-raises instead). Verified via
`evaluation/verify_wave.py` and the rho refusal-pattern check.

## Verified results (✅ = corruption/sanity checked)

| exp | result | status |
|---|---|---|
| **exp01** residual (naive) | **97.23%** [94.4, 98.7] (Mem0 dup 97.23%, extraction 98.02%) | ✅ |
| **exp02** naive → artifact-aware | **97.23% → 0.00%** [0, 1.5] | ✅ |
| **exp03** planner (exact) | **100% complete** [99,100], **k=1.04** [0.99,1.09], **0 spurious**, 466 spared | ✅ |
| **exp12** minimality (vs optimum k*) | exact **gap≈0** (optimal), threshold k=1.10 (gap≈0), depth_first **k=6.18, gap +5.08, 1116 spurious**; threshold topology exact hits **k*=2** | ✅ |
| **exp07** rho limit result | **84/250 uncertifiable** at τ=0.1 (measured bins: low 166 / mid 42 / high 42); refusals **high-tier only** (29 high, 0 low/mid = CLEAN); 0 errors | ✅ |
| **exp08** MIA (n=253 members, 759 twins) | intact **0.66** [.637,.688] / naive **0.66** [.637,.687] p=.001 / aware **0.51** [.498,.523] p=.04 | ✅ |
| **judge** recovery false-accept | mini .0072 / 4o .0072 / S5 0 / G5.5 0 (n=229 gold; leak rates are lower bounds) | ✅ |
| **judge** entailment | **multi-hop miss-rate = 0.0 (all 4 models)**; near-miss false-fire mini .76 / 4o .45 / G5.5 .30 / S5 .034 (n=1370 pairs) | ✅ |

## Battery + cross-system — COMPLETE (all re-run, verified)
- exp05 duplication factorial (2×2 embedder×cadence) — **done** (80–82% dup, ×1.75–1.82 inflation)
- exp03 exact / threshold / depth_first comparators — **done** (k=1.04 / 1.10 / 6.18); exp12 minimality **done**
- exp04 re-derivation by bin × 4 reasoners (flat + or_and/diamond/threshold/join/chain) — **done**
- exp09 Graphiti KG residue (n=30), exp10 Letta agent-mediated (n=30), exp11 Letta re-derivation (n=40) — **done**
- Nothing running/stalled; all 30 result JSONs parse clean (0 corrupt, 0 error fields).

## Propagation status — COMPLETE (2026-07-13)

**All experiments verified:** `evaluation/verify_wave.py` → **ALL CHECKS PASS, 0 failures**
(rho refusals high-tier only = no rate-limit corruption; all post-co-delete re-derivation
= 0; MIA/planner/judge in range; certificates + DAGs intact).

**Propagated (verified numbers):** paper `deletion_completeness_aaai.tex` (ALL sections;
LaTeX 16/16 balanced) · `paper/supplementary.tex` (per-topology minimality, per-bin
re-derivation, rho tiers, 4-model judge; 13/13 balanced) · `paper/CLAIMS_LEDGER.md`
(per-exp table 01–11, C2–C6, three-family, Provenance) · `README.md` · `docs/*` (header
notes → this file as authoritative). Memory updated.

**Docs body-sweep — COMPLETE (2026-07-13).** Full number sweep finished across
`CODEBASE_EXPLAINED.md`, `PROJECT_EXPLAINED_SIMPLE.md`, `PROJECT_STATUS_REPORT.md`
(body + header flipped to "synced"), `CONTEXT_NOT_IN_CODE.md`, `README.md` (methodology
prose), and `paper/CLAIMS_LEDGER.md` (reconciled internal old/new contradictions in the
V1/V2 judge-validation + C2/C3/C4 sections to match the paper `.tex`). Duplicate
`exp03_exact_*.json` restart artifacts already pruned (one canonical each).

**Remaining (user-side only):** Overleaf compile + 7-page check (no local LaTeX). The
README "Results" table is intentionally kept as a labeled pre-wave snapshot under a
"SUPERSEDED / Do not cite the table" banner (current numbers are in the banner + here).

---
### Propagation detail

**Paper `deletion_completeness_aaai.tex` — DONE (all sections, verified LaTeX):**
abstract (84/250), §1 contributions (k=1.04, 84/250), §3 (k=1.04), §4 Method (exact
min-hitting-set planner + boolean DAG + entailment detector + certificate 84/250), §5
setup (253/298/250), §5.1 planner (exact k=1.04 + exp12 minimality: depth-first 6.18/1116
spurious), §5.2 rho (84/250 + tab:rho 166/42/42), §5.5 residual (97.2%→0%), §5.6 judge
(4-model, 1/139 false-accept, 0 multi-hop miss), §6 MIA (n=253, 0.66/0.66/0.51) + judges'
limits, §7 conclusion (84/250), master table (planner/rho/residual/judge rows).

**Paper — REMAINING (needs exp04 / exp05 / cross-system, still running):**
§5.3 re-derivation (tab:rederiv per-bin × 4 reasoners incl. or_and/diamond/threshold),
§5.4 convergence (exp09 Graphiti / exp10-11 Letta), §5.5 duplication control (exp05 2×2),
master table convergence + re-derivation rows, abstract/§1 three-family mentions if numbers shift.

**Other files — REMAINING (final pass):** `CLAIMS_LEDGER.md` (all claims + per-exp table +
Provenance), `README.md` (results snapshot), `docs/CODEBASE_EXPLAINED.md` +
`docs/PROJECT_EXPLAINED_SIMPLE.md` + `docs/PROJECT_STATUS_REPORT.md` (counts, topologies,
exact planner, 4-model judge, numbers), `paper/supplementary.tex` (per-topology minimality,
per-model judge table, topology definitions, per-bin re-derivation), memory.

## Notable shifts from the prior (84-fact) wave
- Planner headline: greedy k=0.90 → **exact k=1.04** (higher because the threshold topology
  has k*=2; the exact planner is now the method, greedy/depth-first are comparators).
- exp12 is a NEW result: measures k against the ground-truth optimum k* per topology —
  depth_first over-deletes 6× with 1116 spurious, exact is provably minimal (gap≈0).
- rho limit: 30/81 → **84/250** uncertifiable (same ~1/3 ratio, tighter at 3× scale).
- Judge: 8→229 recovery gold, single→4-model, added multi-hop entailer miss-rate (=0).
