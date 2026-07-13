# 3× Wave Results — frontier-judge overlay (2026-07-13)

Headline numbers at ~3× scale (datasets: isolated **253**, multi-hop **298**, context
**963**, rho **250**). Adversary panel: gpt-4o-mini, gpt-4o, Claude Sonnet 5, GPT-5.5.
τ = 0.10. **Judges = Claude Sonnet 5** (frontier — recovery *and* entailment), validated on
a **351-case** recovery gold + 1370 entailment pairs; **pinned gpt-4o-mini/gpt-4o reported
as the reproducibility anchor**. Rationale + full decision: **`docs/JUDGE_UPGRADE.md`**.
This file is the authoritative source for propagation.

Correctness note: rho/re-derivation use `probes/parametric_probe` hardened so a
rate-limit/timeout can never be miscounted as a refusal (re-raises instead). Verified via
`evaluation/verify_wave.py` (**ALL CHECKS PASS**) + the rho refusal-pattern check.

## Verified results (✅ = corruption/sanity checked; Sonnet 5 production judge)

| exp | result | status |
|---|---|---|
| **exp01** residual (naive) | **97.23%** [94.4, 98.7] (Mem0 dup 97.23%, extraction 98.02%) — *judge-independent (ExactMatch)* | ✅ |
| **exp02** naive → artifact-aware | **97.23% → 0.00%** [0, 1.5] — *judge-independent* | ✅ |
| **exp03** planner (exact) | **100% complete** [98.7,100], **k=1.03** [0.98,1.08], **0 spurious**, 467 spared | ✅ |
| **exp12** minimality (vs optimum k*) | exact **gap −0.067 (≤0 on EVERY topology: stored/chain/diamond/join/or_and +0.000, stored+world −0.27, threshold +0.000)**; threshold k=**1.14** (gap +0.04); depth_first **k=6.60, gap +5.50, 1192 spurious**; threshold topology k*=2 | ✅ |
| **exp04** re-derivation (Mem0) | bin1 97–100%→**0**; bin2 ops **62/69/69/66%** (mini/4o/S5/G5.5)→**2.7%** (F043 value-coupling residue); 5 structured topologies 100%→0; ρ=0 | ✅ |
| **exp07** rho limit result | **86/250 uncertifiable** at τ=0.1 (measured bins: low/certifiable **164** / mid **41** / high **45**); refusals **30, all high-tier (authored)** = no rate-limit corruption; 0 errors | ✅ |
| **exp08** MIA (n=253 members, 759 twins) | intact **0.66** [.637,.688] / naive **0.66** [.637,.687] p=.001 / aware **0.51** [.498,.523] p=.04 — *judge-independent* | ✅ |
| **exp09** Graphiti KG residue (n=30) | edge **20%** / summary **83%** — *judge-independent* | ✅ |
| **exp10** Letta faithfulness (n=30) | vague **0% faithful / 100% archival**; core residue **10%**; paraphrase 0% | ✅ |
| **exp11** Letta re-derivation (**full 298**, was n=40) | bin1 99–100%→**0**; bin2 62/65/65/68%→**0**; 5 structured topologies 100%→**0**; faithful co-delete **100%**; bystanders **100%**; ρ=0 | ✅ |
| **judge** recovery false-accept (n=**351** gold, 194 neg) | mini **.0206** / 4o **.0052** / **S5 0** [0,.019] / G5.5 0; recall mini .75 / 4o .93 / **S5 .98** / G5.5 .98 | ✅ |
| **judge** entailment (n=1370) | **multi-hop miss = 0.0 (all 4)**; near-miss false-fire mini **.757** / 4o **.455** / G5.5 **.305** / **S5 .034** | ✅ |

## Battery + cross-system — COMPLETE (all judge-dependent exps re-run with Sonnet judge)
- **Judge = Sonnet 5** (`judge_validation_20260713T105713Z.json`): production recovery +
  entailment; 0% false-accept / 3.4% false-fire / 0 multi-hop miss on the expanded gold.
- exp03 exact / threshold / depth_first comparators — **done** (k=**1.03 / 1.14 / 6.60**);
  exp12 minimality **done** (exact provably minimal, gap ≤0 every topology).
- exp04 re-derivation by bin × 4 reasoners (flat + or_and/diamond/threshold/join/chain) — **done**.
- exp07 rho — **done** (86/250). exp11 Letta re-derivation — **done, full 298**.
  exp10 Letta — **done**. exp09 Graphiti / exp05 duplication (80–82%) / exp01-02 / exp08 —
  **judge-independent, unchanged** (not re-run).

## Propagation status (frontier-judge wave)

- [x] `docs/JUDGE_UPGRADE.md` — decision + config + full results (authoritative for the judge change)
- [x] `docs/RESULTS_3X_WAVE.md` — this file
- [ ] `docs/PROJECT_EXPLAINED_SIMPLE.md`, `CODEBASE_EXPLAINED.md`, `PROJECT_STATUS_REPORT.md`,
      `CONTEXT_NOT_IN_CODE.md`, `EXPANSION_PLAN.md`
- [ ] `README.md`
- [ ] `paper/deletion_completeness_aaai.tex`, `paper/supplementary.tex`, `paper/CLAIMS_LEDGER.md`
- [ ] memory

**User-side only:** Overleaf compile + 7-page check (no local LaTeX).

## Notable shifts from the pinned-judge (3× wave) numbers
- **Judge: pinned gpt-4o-mini/gpt-4o → frontier Claude Sonnet 5** (production), pinned kept as
  reproducibility anchor; recovery gold 229 → **351** (22 curated hard cases). On the harder
  gold the frontier judge holds **0% false-accept** while gpt-4o-mini rose to 2%.
- rho limit **84 → 86/250** uncertifiable (higher-recall judge caught 2 more borderline facts).
- planner **k 1.04 → 1.03** (F040 value-carrier fix), 466 → **467** spared, exact gap ≤0 on
  every topology (provably minimal, airtight); comparators threshold 1.10→1.14, depth 6.18→6.60.
- exp11 Letta **n=40 → full 298** (all topologies) — fixes the "cross-system n is modest"
  weakness; everything → 0 after co-delete. exp10 core residue 13% → 10%.
- Closure claims **held** under the stricter judge (planner 100%, re-derivation → 0); the
  limit result and the judge both got stronger. See `docs/JUDGE_UPGRADE.md` → "Net effect".
