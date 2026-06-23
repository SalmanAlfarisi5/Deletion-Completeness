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

## First result

```bash
python experiments/exp01_baseline.py --system mem0 \
    --facts data/facts/isolated_facts.json --n 5 --verbose
```

Establishes the baseline: after a naive raw delete, what fraction of facts are
still recoverable, and from which artifact layer.
