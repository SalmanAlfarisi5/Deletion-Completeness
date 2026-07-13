# Frontier-Judge Wave (2026-07-13)

**Decision (grounded, locked by Salman).** Move the load-bearing LLM judges from the
pinned OpenAI backbone to the **frontier model Claude Sonnet 5** — the smartest model we
have — because an LLM-as-judge should be as capable as possible. All decisions are
grounded in gold-label validation, and the gold set was **expanded** to make the
validation concrete and defensible.

## What changed

| Role | Before | After |
|---|---|---|
| Recovery judge (`config.JUDGE_MODEL`) | `gpt-4o-mini-2024-07-18` | **`claude-sonnet-5`** |
| Entailment judge (`config.ENTAILMENT_JUDGE_MODEL`, new) | `gpt-4o-2024-08-06` | **`claude-sonnet-5`** |
| Adversary panel (`reasoner_models()`) | mini, 4o, Sonnet 5, GPT-5.5 | **unchanged** — mini, 4o, Sonnet 5, GPT-5.5 |
| Recovery gold set | 229 cases (6 curated) | **351 cases (22 curated hard cases)** |

Sonnet 5 is now **both an adversary and the judge** — a deliberate, accepted overlap.

## Why it's defensible

1. **Gold validation is the guarantee, not call-independence.** The judge is validated
   against a ground-truth-by-construction gold set (now n=351: 157 positive / 194
   negative, incl. 22 adversarial grey-zone cases — reconstruction phrasings,
   category-vs-specific, hedges, one-token flips). We report the judge's false-accept and
   recall on that gold. A judge validated to ~0% false-accept scores reliably regardless
   of which adversary produced the answer. This is the sentence for the paper — **not**
   "separate API calls are independent" (same-model errors are correlated even across
   calls; gold validation is what actually certifies the judge).
2. **Smartest model = most capable judge.** On the prior 4-model validation Sonnet 5 was
   already the best judge (0% recovery false-accept; 3.4% entailment near-miss false-fire
   vs gpt-4o's 45%). Using it as the judge is the strongest LLM-as-judge choice.
3. **Reproducibility caveat + anchor.** `claude-sonnet-5` / `gpt-5.5` have no dated
   snapshot (moving aliases), so the frontier judge is less reproducible than a pinned
   snapshot. Mitigation: we still report the **pinned `gpt-4o-mini`/`gpt-4o` judge numbers
   as a reproducibility cross-check** (near-free — the 4-model validation already produces
   them), and we record the access date. This answers both "your judge is too weak" and
   "your judge isn't reproducible."

## Config (env-driven, reproducible)

    JUDGE_MODEL=claude-sonnet-5              # recovery judge
    ENTAILMENT_JUDGE_MODEL=claude-sonnet-5  # entailment judge (decoupled from SECOND_MODEL)
    REASONER_MODEL=gpt-4o-mini-2024-07-18   # backbone reasoner #1 (kept — else it defaults to JUDGE_MODEL)
    SECOND_MODEL=gpt-4o-2024-08-06          # backbone reasoner #2 / dataset validation (unchanged)
    USE_FRONTIER_REASONERS=1                # 4-model adversary panel

Sonnet judge calls run with `thinking:{type:disabled}` (config default) and temperature
omitted (`model_rejects_temperature`), so the JSON verdict can't be truncated by thinking
overhead. Verified by smoke test (recovery match/non-match + entailment separation).

## Re-run scope (judge-dependent only)

**Re-run:** exp03 (planner), exp04 (re-derivation), exp07 (rho), exp10 (Letta faithfulness
— core-residue uses the recovery judge), exp11 (Letta re-derivation), exp12 (minimality),
judge-validation.
**NOT re-run (judge-independent — string/structural/statistical):** exp01/exp02 (residual
= ExactMatch), exp05 (duplication), exp08 (MIA), exp09 (KG residue).

## Expected direction of change (stated up front)

A higher-recall judge (Sonnet recall .98 vs gpt-4o-mini .72) confirms **more** recoveries:
- **Strengthens:** residual-with-operands, ρ (realized **86/250**, up from 84),
  re-derivation-before-co-delete — the adversary and the limit result get stronger.
- **May soften closure claims:** post-co-delete "→0%", planner "100% complete", clean `k`
  could pick up small non-zeros if the smarter judge catches recoveries the entailment DAG
  didn't model. Reported honestly either way — defensibility over a specific number.

## Status

- [x] Config decouple (`ENTAILMENT_JUDGE_MODEL`) + exp03/exp12 wiring + 46 tests pass
- [x] Sonnet judge smoke test (recovery + entailment) OK
- [x] Gold set expanded 229 → 351 (22 curated)
- [x] **judge-validation re-run DONE** (`judge_validation_20260713T083303Z.json`) — see below
- [ ] exp07 (rho) re-run — RUNNING (Runner A)
- [ ] exp03 + exp12 + exp04 re-run — RUNNING (Runner B, Mem0)
- [ ] exp11 + exp10 re-run — RUNNING (Runner C, Letta); exp11 now FULL 298 (all topologies),
      up from n=40 → cross-system re-derivation now consistent with exp04's scope
- [ ] fix `select_recovery/entailment_judge` to report the frontier production judge +
      pinned anchor (currently still prints the old "pinned-preferred" recommendation),
      then re-emit judge_validation (numbers unchanged; only the `selection` field)
- [ ] verify_wave + propagate all numbers to every doc/paper/ledger/memory

## Results (frontier judge)

### Judge validation on expanded gold (n=351 recovery / 1370 entailment)

**Recovery judge** (194 negatives; lower false-accept = safer):

| model | acc | false-accept [95% CI] | recall | κ vs gold |
|---|---|---|---|---|
| gpt-4o-mini | 0.878 | 0.0206 [.008,.052] | 0.752 | 0.747 |
| gpt-4o | 0.966 | 0.0052 [.001,.029] | 0.930 | 0.930 |
| **claude-sonnet-5 (production)** | **0.992** | **0.000 [0,.019]** | **0.981** | **0.983** |
| gpt-5.5 (corroboration) | 0.992 | 0.000 [0,.019] | 0.981 | 0.983 |

**Entailment judge** (1370 pairs):

| model | near-miss false-fire | recall(true) | multi-hop miss |
|---|---|---|---|
| gpt-4o-mini | 0.757 | 1.000 | 0.0 |
| gpt-4o | 0.455 | 0.977 | 0.0 |
| **claude-sonnet-5 (production)** | **0.034** | 0.943 | **0.0** |
| gpt-5.5 (corroboration) | 0.305 | 0.963 | 0.0 |

**Takeaway (defensibility):** on a *larger, harder* gold set the frontier judge
(Sonnet 5) holds **0% recovery false-accept** and **3.4% entailment false-fire** with
**0 multi-hop miss** — best on every safety-critical axis, while the older pinned models
slip (gpt-4o-mini recovery false-accept rose to 2% on the harder gold). Pinned
gpt-4o-mini/gpt-4o numbers are retained above as the reproducibility anchor. Higher Sonnet
recall (.98 vs .75) is the expected mechanism by which leak rates rise and closure cells
may soften in the experiment re-runs.

### Experiments (frontier judge = Sonnet 5)

**exp03 planner (exact) + exp12 minimality — DONE (Sonnet recovery + entailment judge).**
Closure HELD under the stricter judge (I flagged it might soften — it did not):
- exp03: **100% complete** [98.7,100] (0 targets failed to close), **k=1.034**, **0 spurious**,
  467 spared. k-dist 240×1 / 34×2 / 24×0.
- exp12: exact **k=1.034, gap −0.067**, per-topology gap **≤ 0 on every topology** (provably
  minimal). Comparators (entailment judge changed → slight shift): threshold k=1.138 (gap
  +0.037), depth_first k=6.601 (gap +5.500, 1192 spurious).

**exp04 re-derivation — DONE (Sonnet recovery judge).** Closure held:
- bin1 operands 97–100% → **0%** after co-delete (all 4 reasoners).
- bin2 operands **62 / 69 / 69 / 66%** (mini / 4o / Sonnet 5 / GPT-5.5) → **2.7%** after
  co-delete (still just F043, the value-coupling honest-negative — the stricter judge found
  no *new* residual recoveries). ρ = 0 on fictional bins.

**exp07 ρ — DONE (Sonnet recovery judge).** Limit result STRENGTHENED, as predicted:
- **86 / 250 uncertifiable** at τ=0.1 (was 84/250) — measured bins low/certifiable **164** /
  mid **41** / high **45**. The higher-recall judge caught 2 more borderline facts.
- Refusals: **30** flags (26 overlap the prior wave's 29). All are genuine content refusals
  from the frontier reasoners (Sonnet 5 / GPT-5.5) + gpt-4o-mini on facts *authored* as
  sensitive (R15/R40/R41/R42/R44/R245/R249/R47…); the probe hardening guarantees these are
  content-400s, not rate-limit artifacts. By measured bin they read 22 high / 7 mid / 1 low;
  `verify_wave` classifies by authored tier (all sensitive) → expected to pass.

**exp11 Letta re-derivation — DONE, now FULL 298 (was n=40).** Strengthened cross-system
result: bin1 (n=74) 99–100% → **0**, bin2 (n=74) 62/65/65/68% (mini/4o/S5/G5.5) → **0**, and
**all 5 structured topologies (n=30 each) 100% → 0**. Faithful direct co-delete **100%**,
bystanders intact **100%**, ρ=0. (Letta closes cleaner than Mem0 — direct `passages.delete`,
no F043 value-coupling residue.)

**exp10 Letta faithfulness — DONE (Sonnet judge on core).** Hook unchanged: vague request
**0% faithful / 100% archival residue**; core residue **10%** (was 13% — stricter judge),
paraphrase residue 0% (n=30).

## Final verification

`evaluation/verify_wave.py` → **ALL CHECKS PASS**. Refusals classify as **30 high-tier
(authored)** → no rate-limit corruption. Judge false-accepts, exp12 exact gap ≤ 0, MIA,
DAGs all in range. Selector now reports **production = claude-sonnet-5, anchor = gpt-4o**
(`judge_validation_20260713T105713Z.json`).

## Net effect (defensible, as predicted)
- **Strengthened:** limit result 84→**86/250**; the judge itself (0% false-accept on a
  larger, harder gold); exp11 now full-298 across all topologies (fixes the "n=40" weakness).
- **Held (did NOT soften):** planner 100% complete + provably-minimal k=1.03; re-derivation
  → 0 (Mem0 bin2 → 2.7% F043 only; Letta → 0 everywhere); artifact-aware residual (judge-
  independent).
- **Unchanged (judge-independent):** exp01/02 97.2%→0, exp05 dup, exp08 MIA .66/.66/.51,
  exp09 Graphiti 20%/83%.
