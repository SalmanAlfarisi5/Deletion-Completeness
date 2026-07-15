# Deletion-Completeness Planner & Certificate

A planner + certificate for the **right to be forgotten** in LLM-agent memory
systems. When a user asks a memory system to delete a fact, the raw record is
removed — but the fact may survive in *derived artifacts* (summaries, KG
nodes/edges, profile attributes, embeddings) or be *re-derivable* from other
surviving facts. This project detects, decomposes, plans, and certifies
deletion completeness.

Recoverability is decomposed into three channels — residual survival,
re-derivation from surviving facts, and an irreducible world recall:

1. **Residual survival** — a derived artifact still physically contains the fact.
   *Fix:* propagate deletion to derived artifacts.
2. **Re-derivation** — all artifacts are gone but the fact is entailed by
   surviving facts and/or the base model's parametric knowledge.
   *Fix:* co-delete the entailing facts (Opt-P2E2, NP-hard → greedy heuristics);
   an irreducible **world recall ρ** may remain.

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

### Zep/Graphiti (secondary system)

Uses a local Neo4j — installed with **no Docker / no sudo** via JDK + Neo4j
tarballs under `~/neo4j-stack`:

```bash
JAVA_HOME=~/neo4j-stack/jdk-21* ~/neo4j-stack/neo4j-community-5.26.0/bin/neo4j start  # bolt :7687
pip install graphiti-core==0.29.2
# stop:  JAVA_HOME=~/neo4j-stack/jdk-21* ~/neo4j-stack/neo4j-community-5.26.0/bin/neo4j stop
```
Credentials live in `config.NEO4J_*` (default user `neo4j`, password `deletetest123`).

## Experiments

```bash
# exp01 — naive deletion baseline (delete the single surfaced record)
python experiments/exp01_baseline.py --facts data/facts/isolated_facts.json --n 12 -v
# exp02 — artifact-aware deletion (purge every row carrying the value)
python experiments/exp02_artifact_purge.py --facts data/facts/isolated_facts.json --n 12 --verbose
# exp03 — planner end-to-end (threshold heuristic; emits certificates)
python experiments/exp03_planner.py --n 6 -v
# exp04 — re-derivation control + world recall (operands-only, 2 reasoners)
python experiments/exp04_parametric.py --n 6 -v
# exp05 — Mem0 duplication factorial (embedder x cadence)
python experiments/exp05_duplication.py
# exp06 — infer=True derivation-capture check
python experiments/exp06_derivation_capture.py -v
# exp07 — world recall rho on a gradient (measured, 2 reasoners)
python experiments/exp07_rho_gradient.py --n-samples 6 -v
# exp08 — membership inference (retrieval-score, naive vs artifact-aware)
python experiments/exp08_mia.py
# judge validation (recovery false-accept rate + entailment kappa)
python evaluation/judge.py
# exp09 — Zep/Graphiti KG-node residual (needs local Neo4j running; see Setup)
python experiments/exp09_zep_kg_residual.py -v
# exp10 — Letta/MemGPT agent-mediated deletion faithfulness (needs Letta server; see Setup)
python experiments/exp10_letta.py -v
# exp11 — Letta/MemGPT re-derivation + faithful co-delete (operands-only control, 2 reasoners)
python experiments/exp11_letta_rederivation.py --n 6 -v
```

### Results (pre-wave snapshot, 2026-06-23 — SUPERSEDED)

> The table below is the small-scale pre-wave snapshot. The current numbers
> (the **3× wave**: 253 isolated / 298 multi-hop / 963 context / 250 rho) live in
> `docs/RESULTS_3X_WAVE.md`, the paper drafts (`paper/`), and `CLAIMS_LEDGER.md` —
> e.g. residual **97.2% / 97.2%→0%** (exp01/02), **86/250** uncertifiable at τ=0.1
> (exp07), MIA naive AUC **0.66** (p=.001) / aware **0.51** (exp08), planner
> **exact k=1.03 / 0 spurious** with a measured optimality gap −0.067 (exp03), and a new
> **exp12** minimality result (depth-first over-deletes 6× with 1192 spurious). The
> planner now solves the exact min-hitting-set over a boolean **entailment DAG**, and
> the multi-hop set adds 5 hard topologies (join, chain, disjunctive, diamond,
> threshold). Do not cite the table.

| experiment | metric | result |
|---|---|---|
| exp01 naive | residual survival after deleting the surfaced record | **75%** (tracks per-fact duplication) |
| exp02 | residual: naive → artifact-aware | **83% → 0%** |
| exp05 | duplication: row-inflation (MiniLM/OpenAI × 0/1.5s) | **24–42%**, embedder/cadence-independent |
| exp05 | duplicate type | **paraphrase-dominant** (7–9) vs byte-identical (4–5) |
| exp06 | infer=True derivation-capture | **0%** (it's consolidation, not derivation) |
| exp04 | re-derivable, **bin1 stored-alone** | **100%** → 0% after co-delete |
| exp04 | re-derivable, **bin2 stored+world** | **.56–.74 (4 reasoners)** → 0% after co-delete |
| exp04 | world recall ρ | **0%** (synthetic subjects) |
| exp03 | planner: completeness / spurious / mean k | **100% / 0 / 0.90** |
| exp07 | world recall ρ by tier (gpt-4o-mini / gpt-4o) | low **0.00**, mid **0.03 / 0.63**, high **0.83 / 1.00** |
| exp07 | certs NOT certified-complete (ρ>τ, residual=0) | **30/81** (the limit result) |
| exp08 | MIA AUC (n=33, bootstrap CI): intact / naive / aware | **0.72** (p=.002) / 0.61 (p=.07, ns) / **0.51** (CI incl. 0.5) → artifact-aware restores indistinguishability |
| judge | recovery false-accept / entailment κ (trivial→hard neg) | **0%** / 0.83 → **0.46**; gpt-4o-mini false-fires **42%** on partial operands (gpt-4o 0%) |
| exp09 | Zep/Graphiti KG residue after `remove_episode` (n=3) | edge **33%**, **summary 67%** (entity+community) — residual via stale summaries, not edge-invalidation |
| exp10 | Letta/MemGPT agent-mediated deletion faithfulness (n=3) | **explicit dual-surface → 100% faithful**; **vague RTBF → 0% faithful / 100% archival residue** (agent scrubs core, misses archival) |
| exp11 | Letta re-derivation (operands-only control, 4 reasoners) | bin1 **100%**, bin2 **.74–.78** → **0% after co-delete**; ρ **0%**; faithful direct co-delete **100%**, bystanders intact **100%** |

**Story:** naive single-record deletion is incomplete because Mem0 silently
**duplicates** facts (exp01/05, a documented Mem0 limitation, not our embedder);
artifact-aware deletion fixes residual survival (exp02); but even with residual=0
a **re-derivation** channel remains — multi-hop facts are reconstructable from
surviving entailing facts (exp04, binned, four reasoners) — which the planner
closes with near-minimal collateral (exp03), down to the world recall ρ.

### Key methodology notes
- Deletion is **content/search-based**, not via Mem0's `add()` ids (which lag).
- Residual-survival experiments use `infer=True` (realistic). exp04 is a
  **contamination-free control**: it injects *source facts only* (never the
  target value), verbatim, and verifies the target is absent before probing.
- Recovery is scored by a **validated LLM judge** — the production judge is now
  **Claude Sonnet 5** (frontier, gold-validated), with the pinned **gpt-4o-mini/gpt-4o**
  judge reported as the reproducibility anchor — checked across all 4 models on
  n=351 gold (false-accept **0** [0,.019] for Sonnet5/GPT-5.5, **.0052** gpt-4o /
  **.0206** gpt-4o-mini → reported leak rates are lower bounds to within the production
  judge's ~0% false-accept margin; κ up to .98 vs gold).
- Re-derivation is **binned by mechanism, never aggregated**, and run on the **4-reasoner
  adversary panel** (gpt-4o-mini, gpt-4o, Claude Sonnet 5, GPT-5.5), taking the worst.
- The world recall **ρ is measured on a gradient** (exp07), not asserted:
  some facts stay recoverable from non-deletable world knowledge alone, so
  completeness cannot be certified (ρ>τ) even with residual=0 — the limit result.
- Both re-derivation and ρ are **reasoner-model-dependent**, so they are run on the
  4-reasoner panel (gpt-4o-mini, gpt-4o, Claude Sonnet 5, GPT-5.5), certifying by the worst.
- **Membership inference (exp08)** is powered (n=253 members + 3 matched twins
  each = 759 controls, bootstrap 95% CI + label-permutation p): artifact-aware
  deletion drives the AUC to **0.51** (CI [0.498, 0.523] includes 0.5, though the
  permutation test is marginally significant, p=.04) — it attenuates the signal
  toward chance but does not provably eliminate it. Naive single-record deletion
  **does** leave a detectable signal (AUC 0.66, p=.001); the intact sanity
  (AUC 0.66, p=.001) confirms the test has power.
- The **entailment judge** is validated across all 4 models on n=1370 pairs: every
  model has a **0% multi-hop miss-rate** (never loses a true entailer — the safety
  property). On near-miss partial operands, false-fire is mini **75.7%** / gpt-4o
  **45.5%** / GPT-5.5 **30.5%** / Sonnet5 **3.4%**; the production entailment judge is
  now **Claude Sonnet 5** (pinned **gpt-4o** kept as the reproducibility anchor), and
  because the planner co-deletes over the *known* entailment DAG (not the judge), a
  judge's false-fire cannot inflate collateral *k*.
- **Cross-system (exp09, Zep/Graphiti):** explicit `remove_episode` is *clean* for
  edges, but the deleted fact survives in **stale entity/community summaries** (not
  recomputed on deletion) — a by-design KG-residual channel, distinct from Mem0's
  dedup-failure duplication. Same probe/planner/certificate stack, new adapter.
- **Cross-system (exp10–11, Letta/MemGPT):** deletion is **agent-mediated** across
  two surfaces (core blocks + archival). A vague but realistic RTBF request makes
  the agent scrub the *core* block it reasons about and **silently miss archival**
  (exp10: 0% faithful, 100% archival residue) — surface-incomplete deletion. The
  re-derivation channel and near-minimal co-deletion **port unchanged** (exp11: same
  probe/certificate stack), with the planner's co-deletes issued through the
  **direct, verified-faithful** op (not the agent) so the channel is measured cleanly.
- **Three architecture families, one phenomenon:** residual survival appears in all
  three by *different by-design mechanisms* — Mem0 **duplication** (dedup pipeline),
  Graphiti **stale summaries** (bi-temporal KG), Letta **surface-incomplete
  agent-mediated deletion** (LLM-paging) — generalising the deletion-completeness gap.
