# Deletion-Completeness Planner & Certificate

A planner + certificate for the **right to be forgotten** in LLM-agent memory
systems. When a user asks a memory system to delete a fact, the raw record is
removed — but the fact may survive in *derived artifacts* (summaries, KG
nodes/edges, profile attributes, embeddings) or be *re-derivable* from other
surviving facts. This project detects, decomposes, plans, and certifies
deletion completeness.

Recoverability is decomposed into exactly two causes:

1. **Residual survival** — a derived artifact still physically contains the fact.
   *Fix:* propagate deletion to derived artifacts.
2. **Re-derivation** — all artifacts are gone but the fact is entailed by
   surviving facts and/or the base model's parametric knowledge.
   *Fix:* co-delete the entailing facts (Opt-P2E2, NP-hard → greedy heuristics);
   an irreducible **parametric floor ρ** may remain.

Target systems: **Mem0** (primary), **Zep/Graphiti** (secondary),
**MemGPT/Letta** (tertiary). Black-box API only; no model training.

## Layout

```
config.py            # keys, models, thresholds, paths (reads .env)
data/facts/          # controlled fact datasets (isolated / multi_hop / context)
systems/             # memory-system adapters (base ABC + per-system)
pipeline/            # injector, artifact tracer, deleter, graph builder
probes/              # recoverability probes (exact, paraphrase, embedding, ...)
planner/             # entailment detector + greedy co-deletion heuristics
certificate/         # certificate schema + emitter
evaluation/          # runner, metrics, LLM-as-judge
experiments/         # exp01 baseline ... exp04 parametric
```

## Setup

```bash
source /home/salman/Desktop/venv/myenv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in keys
python config.py            # prints config + validates keys
```

`MEM0_MODE` selects open-source Mem0 (`oss`, local + reproducible) vs the hosted
platform (`hosted`). `LLM_PROVIDER` selects `anthropic` vs `openai` for
extraction/judging/paraphrasing.

## Experiments

```bash
# exp01 — naive deletion baseline (delete the single surfaced record)
python experiments/exp01_baseline.py --facts data/facts/isolated_facts.json --n 12 -v
# exp02 — artifact-aware deletion (purge every row carrying the value)
python experiments/exp02_artifact_purge.py --facts data/facts/isolated_facts.json --n 12 --verbose
# exp03 — planner end-to-end (threshold heuristic; emits certificates)
python experiments/exp03_planner.py --n 6 -v
# exp04 — re-derivation control + parametric floor (operands-only, 2 reasoners)
python experiments/exp04_parametric.py --n 6 -v
# exp05 — Mem0 duplication factorial (embedder x cadence)
python experiments/exp05_duplication.py
# exp06 — infer=True derivation-capture check
python experiments/exp06_derivation_capture.py -v
# exp07 — parametric floor rho on a gradient (measured, 2 reasoners)
python experiments/exp07_rho_gradient.py --n-samples 6 -v
# exp08 — membership inference (retrieval-score, naive vs artifact-aware)
python experiments/exp08_mia.py --n 6 --corpus 27 -v
# judge validation (recovery false-accept rate + entailment kappa)
python evaluation/judge.py
```

### Results (mem0 oss + gpt-4o-mini-2024-07-18 + local MiniLM, 2026-06-23)

| experiment | metric | result |
|---|---|---|
| exp01 naive | residual survival after deleting the surfaced record | **75%** (tracks per-fact duplication) |
| exp02 | residual: naive → artifact-aware | **83% → 0%** |
| exp05 | duplication: row-inflation (MiniLM/OpenAI × 0/1.5s) | **24–42%**, embedder/cadence-independent |
| exp05 | duplicate type | **paraphrase-dominant** (7–9) vs byte-identical (4–5) |
| exp06 | infer=True derivation-capture | **0%** (it's consolidation, not derivation) |
| exp04 | re-derivable, **bin1 stored-alone** | **100%** → 0% after co-delete |
| exp04 | re-derivable, **bin2 stored+world** | **80% (4/5)** → 0% after co-delete |
| exp04 | parametric floor ρ | **0%** (synthetic subjects) |
| exp03 | planner: completeness / spurious / mean k | **100% / 0 / 1.17** |
| exp07 | parametric floor ρ by tier (gpt-4o-mini / gpt-4o) | low **0.00**, mid **0.03 / 0.63**, high **0.83 / 1.00** |
| exp07 | certs NOT certified-complete (ρ>τ, residual=0) | **6/15** (the limit result) |
| exp08 | membership-inference AUC: naive → artifact-aware | **0.64 → 0.56** (consolidation trace persists) |
| judge | recovery **false-accept** / entailment κ | **0%** / **0.83** |

**Story:** naive single-record deletion is incomplete because Mem0 silently
**duplicates** facts (exp01/05, a documented Mem0 limitation, not our embedder);
artifact-aware deletion fixes residual survival (exp02); but even with residual=0
a **re-derivation** channel remains — multi-hop facts are reconstructable from
surviving entailing facts (exp04, binned, two reasoners) — which the planner
closes with minimal collateral (exp03), down to the parametric floor ρ.

### Key methodology notes
- Deletion is **content/search-based**, not via Mem0's `add()` ids (which lag).
- Residual-survival experiments use `infer=True` (realistic). exp04 is a
  **contamination-free control**: it injects *source facts only* (never the
  target value), verbatim, and verifies the target is absent before probing.
- Recovery is scored by a **validated LLM judge** (0% false-accept → reported
  leak rates are conservative lower bounds; κ=0.77 vs gold).
- Re-derivation is **binned by mechanism, never aggregated**, and run on **≥2
  reasoner models** (gpt-4o-mini, gpt-4o agree).
- The parametric floor **ρ is measured on a gradient** (exp07), not asserted:
  some facts stay recoverable from non-deletable world knowledge alone, so
  completeness cannot be certified (ρ>τ) even with residual=0 — the limit result.
- Both re-derivation and ρ are **reasoner-model-dependent**, so they are run on
  ≥2 reasoners (gpt-4o-mini, gpt-4o).
