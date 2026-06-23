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

# exp04 — re-derivation & the parametric floor (emits certificates)
python experiments/exp04_parametric.py --n 6 -v
```

### First results (mem0 oss + gpt-4o-mini + local MiniLM, 2026-06-23)

| experiment | metric | result |
|---|---|---|
| exp01 naive | residual survival after deleting the surfaced record | **~75%** (= Mem0's duplicate-row rate) |
| exp02 | residual: naive → artifact-aware | **83% → 0%** |
| exp04 | residual after artifact-complete purge | **0%** |
| exp04 | **re-derivable from surviving entailing facts** | **67% (4/6)** |
| exp04 | re-derivable after co-deletion | **0%** |
| exp04 | parametric floor ρ | **0%** (synthetic subjects) |

**Story:** naive single-record deletion is incomplete because Mem0 silently
duplicates facts (exp01); artifact-aware deletion fixes residual survival
(exp02); but even artifact-complete deletion leaves a re-derivation channel —
2/3 of multi-hop facts are reconstructable from surviving entailing facts —
which only co-deletion closes (exp04), down to the parametric floor ρ.

### Key methodology notes
- Deletion is **content/search-based**, not via Mem0's `add()` ids (which lag).
- exp04 stores facts **verbatim (`infer=False`)** to keep injection controlled;
  exp01/exp02 use `infer=True` (realistic, but Mem0 rewrites/merges facts).
- Recovery is scored by an **LLM judge** (numeric approximation ok; wrong values rejected).
- Caveats: the duplication rate may depend on embedder/cadence; ρ=0 by construction
  (fictional subjects); some re-derivations fail on the model's stale/weak world knowledge.
