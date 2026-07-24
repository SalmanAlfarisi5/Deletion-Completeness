# Pivot the Deletion-Completeness paper to discovery-based minimum co-deletion

## What this is

This repo contains a completed study on deletion-completeness in LLM agent memory
(Mem0, Zep/Graphiti, Letta). I am NOT starting a follow-up paper. I am CHANGING
THIS PAPER'S METHODOLOGY and rewriting the draft around a new contribution.

OLD contribution (being retired): a three-channel recoverability decomposition
plus a per-fact certificate, with the entailment DAG ASSUMED as given.

NEW contribution: DISCOVER the re-derivation structure by black-box probing,
compute the MINIMUM co-deletion set from what was discovered, and measure how
often that deletion is FRAGILE — i.e. it only holds because some other fact is
currently suppressing recovery, so the leak re-opens if that fact ever goes.

Scope: the new study covers FOUR systems — Mem0, Mem0g (graph variant),
Zep/Graphiti, and Letta. The old study covered three; Mem0g is new and must be
built. Phases 5, 6, and 6b run on a single PRIMARY system (Mem0) to develop and
tune the method; Phase 7 then runs the full comparison across all four.

Certification is dropped entirely. No certificates, no tau-gated completeness
verdicts, no certificate emission. See Phase 1.

## The three research questions this must answer

Every result must serve one of these. If a number answers none of them, cut it.

RQ1 — REALISTIC. Is this scalable and deployable to an actual agentic memory
      system? Measured by oracle calls and latency per deletion, how those grow
      with store size, cache amortisation, and whether the retrieval stage
      actually finds the true operands.

RQ2 — SAFE. Is the fact genuinely gone, and no longer derivable from what
      remains plus world knowledge? Measured by an adversary model querying the
      surviving store, and by how often an apparent success is only contingent.

RQ3 — SEVERE. How many other facts get co-deleted per target, and how many of
      those were necessary versus unnecessary? Measured against ground-truth
      minimal sets and against bystanders that should never be touched.

Work through the phases in order. STOP at each CHECKPOINT and report. Do not
skip ahead. Do not batch phases together.

## Ground rules

1. Work on a new git branch `discovery-pivot`. Commit at each checkpoint with a
   clear message. Never commit to main.
2. Existing seed datasets under `data/facts/_seed/` are FROZEN. Never modify them.
   The working copies in `data/facts/` are also frozen for this pivot — new data
   goes in new files.
3. Existing result files in `data/results/` are FROZEN. New results go in
   `data/results/v2/`. Exception: Phase 1 removes `data/results/certificates/`,
   which is deliberate and covered there.
4. If any change would alter a number that currently appears in
   `paper/deletion_completeness_aaai.tex` or `paper/supplementary.tex`, STOP and
   show me old -> new before proceeding. This rule holds for the whole task.
5. Before any loop that makes paid API calls: estimate total call count and USD
   cost, report it, and wait for my go-ahead.
6. Never assert a ground-truth value by hand. Compute it in code and verify it.
7. Do not print or commit anything from `.env`.

## Phase 0 — Survey and plan (read-only)

Read and report concisely on:
- `config.py` — confirm JUDGE_MODEL, REASONER_MODEL, SECOND_MODEL,
  ENTAILMENT_JUDGE_MODEL, TAU, and how provider selection works
- `planner/entailment_dag.py` — the existing formula builders (formula_flat,
  formula_or_and, formula_threshold, formula_chain, formula_join,
  formula_diamond) and how min_hitting_sets / min_codelete_size are computed
- `planner/optimizer.py` — GreedyPlanner and its three heuristics
  (heuristic_threshold, heuristic_exact, heuristic_depth_first)
- `planner/entailment_detector.py` — the current entailment oracle
- `evaluation/judge.py`, `evaluation/recovery.py` — judge validation and
  recovery scoring
- `systems/base.py` and the three adapters — the MemorySystemAdapter interface
- `certificate/` — every place it is imported or referenced (grep the whole repo)
- `docs/DISCOVERY_PIVOT_PLAN.md`, `docs/DISCOVERY_METHOD.md`,
  `docs/DISCOVERY_EXPERIMENTS.md` — an earlier pivot plan exists; tell me what
  in it is still valid and what conflicts with this prompt. THIS PROMPT WINS on
  any conflict, especially regarding certificates.
- Which of `python-sat`, `rank_bm25`, `ortools` are installed (I believe none
  are; `sentence-transformers`, `networkx`, `scipy` are present)

Then write `docs/PIVOT_V2.md`: a one-page plain-language statement of the new
contribution, what is being retired, the three RQs, and the phase plan.

CHECKPOINT 0 — report and wait.

## Phase 1 — Retire certification

- Delete the `certificate/` package and `tests/test_certificate_status.py`.
- Remove `data/results/certificates/` (they are frozen artifacts of the old
  framing; delete on the branch, they stay in git history).
- Remove `paper/sample_certificate_complete.json` and
  `paper/sample_certificate_incomplete.json`.
- In `planner/optimizer.py`, remove `achieved_completeness` from PlanResult and
  every tau-gated completeness verdict. Keep raw recoverability measurements —
  we still measure whether the target is recoverable; we just stop issuing a
  pass/fail certificate about it.
- Grep the whole repo for `certificate`, `certified`, `floor_reaching`,
  `completeness_certified` and clean up every remaining reference.
- Keep rho as a MEASURED quantity (the adversary legitimately has world
  knowledge, and RQ2 is about "world knowledge + remaining facts"). Drop only
  the rho-vs-tau certification logic.
- Run `make test` and fix anything that breaks.

CHECKPOINT 1 — report what was removed, what broke, and the test result. Wait.

## Phase 1b — Build the Mem0g adapter (dev only, no API loops)

Do this now rather than at Phase 7. It is free — no paid calls — and if Mem0's
graph mode has problems, I want to know before the expensive phases, not after.

- Add graph support: either a flag on `systems/mem0_adapter.py` or a new
  `systems/mem0g_adapter.py`, whichever fits `MemorySystemAdapter` more cleanly.
- Implement `list_graph` and `supports_graph`.
- ISOLATE THE GRAPH STORE. Mem0g and Zep/Graphiti would otherwise share the
  Neo4j instance at NEO4J_URI and contaminate each other. Use a separate Neo4j
  database or a namespace prefix per system, and add the setting to config.py.
  Verify isolation: write to one, confirm the other's graph is unchanged.
- Smoke test on ~10 facts: inject, query, list_graph, delete_memory,
  delete_all_memories. Confirm delete_memory actually removes graph nodes and
  edges, not just the vector row — Mem0 has a known issue where per-memory
  deletes orphan graph data. Report exactly what survives a delete.

CHECKPOINT 1b — report the adapter design, the isolation verification, and what
the smoke test found surviving deletion. Wait.

## Phase 2 — Structure search (a GATE, before generating any data)

I need to know empirically whether minimum-cardinality solving is even justified
at our scale. Do not assume it is.

- Randomly generate OR-of-AND boolean formulas over 4-12 leaf facts, varying:
  number of disjunctive paths (2-6), path length (1-4), and operand overlap
  between paths. Also generate at_least(r, n) for r in {2,3}, n in {4,5,6}.
- For each formula compute the OPTIMAL minimum hitting set and what GREEDY
  set cover returns over the same paths.
- Install `python-sat` and use `pysat.examples.hitman.Hitman` for the optimum.
  Cross-check it against the existing brute-force `min_hitting_sets` in
  `planner/entailment_dag.py` on small instances — they must agree. If they
  disagree, stop and show me.

Report a table per structure family: distribution of k*, the fraction of
instances where greedy > optimal, and the mean gap.

GATE 2 — If fewer than ~20% of instances in EVERY family show greedy > optimal,
say so plainly and stop. That would mean minimum-cardinality solving is not
justified at this scale, and the paper's centre of gravity should move to the
fragility/non-monotone contribution instead. I need that answer before we build
hundreds of targets on the assumption. Do not soften a negative result here.

CHECKPOINT 2 — report the table and the gate outcome. Wait.

## Phase 3 — New datasets

Write to `data/facts/v2/`. Reuse the existing field conventions from
`data/facts/multi_hop_facts.json` (id, subject, category, text, utterance,
question, delete_value, probe_value, entailed_by, entailment_dag) so existing
loaders work. Add new fields where needed.

Every record with a derivation carries an entailment_dag with leaves, formula,
topology, min_codelete_size, min_hitting_sets_ids — all COMPUTED with Hitman,
never hand-written. Extend `planner/entailment_dag.py` with the new formula
builders rather than writing generation logic elsewhere.

Families:

(a) or_structured — whichever structures survived GATE 2. Spread k* across
    1,2,3,4,5. Do not let k*<=2 dominate.

(b) nonmonotone_contradiction — operands O1,O2 jointly derive Z; a suppressor S
    retracts or contradicts an operand so the adversary hedges while S is present.
    Ground truth: sufficient({O1,O2}) = True, sufficient({O1,O2,S}) = False.
    Label suppressor_ids and true_min_deletion.

(c) nonmonotone_crowding — operands O1,O2 derive Z; N distractors with high
    cosine similarity to the deletion query but ZERO derivational content, tuned
    so O2 falls below retrieval rank k.
    VERIFY IN CODE with the repo's embedding model: assert rank(O2) > k with
    distractors present and rank(O2) <= k without. Fail loudly on any record
    where the assertion does not hold. Do not ship unverified crowding cases.

(d) near_miss — same subject AND object as a true operand but not entailing;
    plus partial operands that almost-but-don't suffice (supply exactly r-1 of
    an at_least(r,n)). These must NEVER be deleted. They measure over-deletion.

(e) surface_survival — verbatim duplicate, paraphrase, and summary-absorbed
    variants of a target. Label the channel.

Domain mix, enforced in code, assert before writing:
  arithmetic ~25%, temporal ~25%, relational ~25%, clinical/domain-rule ~25%.
  Financial must not exceed 25% overall (it is currently 57% in the old data).
  Temporal cases must use interval/validity-window reasoning, since
  Zep/Graphiti is bi-temporal and this exercises a real deployed feature.

Scale: ~50-80 targets per family, ~400-650 total, spread across a derivation
depth gradient (1-5) and the k* gradient. Do not sample only hard cases.

All entities fictional. Use Faker (SG locale) for surface PII values. Every
value must be arbitrary enough that a base model cannot guess it — run the
existing parametric probe as a gate and drop any fact the base model recovers.

CHECKPOINT 3 — report per-family counts, k* histogram, domain mix, Type (c)
verification pass rate, and how many facts the parametric gate dropped. Wait.

## Phase 4 — The oracle

The sufficiency oracle is NOT an abstract entailment question. Implement it as
actual recovery:

    def sufficient(target, subset):
        answers = [adversary(target["question"], subset) for _ in range(k_samples)]
        votes   = [recovery_judge(a, target["probe_value"]) for a in answers]
        return majority(votes)

- Build on `evaluation/recovery.py` and the existing recovery judge. Lock the
  judge to `config.JUDGE_MODEL`.
- k_samples = 5, majority vote. Add SPRT so unambiguous cases stop early.
- Cache on (target_id, frozenset(subset_ids), model). Persist to disk under
  `data/results/v2/oracle_cache/`.
- Optional NLI cross-encoder pre-filter before paying for an LLM call. Measure
  the savings and its false-negative rate; do not enable it if FN rate is
  material.
- Note: the existing `planner/entailment_detector.py` measured entailment, and
  its agreement was weak on hard near-misses. Prefer this recovery-based oracle.
  Keep the entailment detector available for comparison only.
- Report judge self-agreement on a held-out labelled subset.

GATE 4 — if judge self-agreement < 80%, stop and report. Nothing downstream is
trustworthy below that.

CHECKPOINT 4 — report cost per oracle call, cache hit rate, pre-filter savings,
and self-agreement. Wait.

## Phase 5 — The pipeline

New module `discovery/`. Five stages, plus an optional stage 4b:

1. NARROW — BM25 (`rank_bm25`) + dense retrieval + cross-encoder rerank, fused
   by reciprocal rank fusion, down to 10-20 candidates. Zero LLM calls.
   Log NARROW recall@k — the fraction of the target's true operands that survive
   into the candidate set. This feeds RQ1.

2. ENUMERATE — QuickXplain over 8 random orderings to find minimal sufficient
   sets ("leak paths"). Dedup across seeds.
   Design this stage to accept an ARBITRARY store state as input, not just the
   live store. Stage 4b depends on calling it repeatedly against hypothetical
   states; if it is hard-wired to the live store, 4b becomes a rewrite.

3. HIT — `pysat.examples.hitman.Hitman` over the discovered leak paths for the
   cardinality-minimum deletion set D.

4. FRAGILITY SWEEP — the new layer, two sweeps. Both are MEASUREMENTS, not
   certificates:
     add_back:      for each f in D, test sufficient(R + {f}). If recovery DROPS
                    when f is returned, f was suppressing. Diagnostic.
     leave_one_out: for each f still in the candidate pool, test
                    sufficient(R - {f}). If Z becomes recoverable, the deletion
                    was CONTINGENT on f.
   Emit `fragile: bool` and `contingent_on: [ids]` per target. Report the
   FRAGILITY RATE across the dataset. Do not emit any pass/fail verdict.

4b. FRAGILITY REPAIR (implement the interface now, run only if budget allows)
    When leave_one_out finds Z recoverable from R - {f}, the fix is NOT to
    delete f — deleting f is what opens the leak. The fix is to close the path
    f was masking.
    Formulation: find the minimum D such that Z is unrecoverable from
    (R \ D) - {f} for EVERY f in the candidate pool.
    Mechanically: re-run stage 2 discovery inside each R - {f} scenario, pool
    those leak paths with the originals, re-solve Hitman over the union.
    Cost ~ |pool| x stage 2. Report robust_deletion_size next to the plain
    minimum so the price of robustness is visible.

5. VERIFY — adversary probes against the surviving store: paraphrase, multi-hop,
   reverse query, role-play, prefix injection.

Log oracle calls and wall-clock time per stage per target. This feeds RQ1.

## Phase 6 — Ours vs comparators

Run all of the following against the same oracle and datasets:

  OURS            — the Phase 5 pipeline, end to end
  A0  native delete       — each system's own delete API, unmodified
  A1  subject scrub       — delete everything mentioning the subject
  A2  target + top-k RAG  — the realistic engineer's heuristic
  B3  greedy set cover    — ABLATION of our stage 3: same narrow + enumerate,
                            greedy instead of Hitman
  B4  ddmin alone         — ABLATION of stages 2+3: 1-minimal, not minimum
  B5  existing heuristics — prior work; reuse GreedyPlanner's
                            heuristic_threshold and heuristic_depth_first
  ORACLE CEILING          — our stages 3-5 given the ground-truth DAG instead
                            of discovered paths

Report these two gaps explicitly, they are the paper's core numbers:
  CEILING - OURS  = discovery error   (cost of probing instead of knowing)
  B3 - OURS       = value of minimum-cardinality solving

Treat B3 and B4 as ABLATIONS in the writeup, not as external baselines.

The fragility sweep is a POST-HOC EVALUATION applied identically to every row's
output. It is part of OURS as a pipeline stage, but for A0/A1/A2/B3/B4/B5 it is
run externally, after the method has finished, and its result is NOT fed back
into that method. Do not build the sweep into any comparator — the contrast is
the whole point.

Expect the ORACLE CEILING to be fragile on families (b) and (c). The
ground-truth DAG encodes logical structure; suppression and crowding are runtime
effects absent from it. If the ceiling is NOT fragile there, something is wrong
with the family (b)/(c) generators — report it.

On families (b) and (c), NEVER report success rate without fragility rate beside
it. A method that leaves the suppressor in place scores a trivially high success
rate while the leak is one deletion away from re-opening.

Report per-family, not just in aggregate. For each family (a)-(e), produce a
table: rows = methods, columns = deletion count, success rate, fragility rate,
necessary/unnecessary split. State plainly in which families OURS does NOT win
— on low-k* structures greedy is expected to tie, and on family (d) subject
scrub may score well on success while failing badly on precision. Do not
suppress a family where we lose.

Use paired statistical tests across targets for the headline comparisons
(OURS vs B3, OURS vs A0) with confidence intervals, not bare means.

CHECKPOINT 6 — report the per-family tables and the two gap numbers. Wait.

## Phase 6b — Scaling sweep (this answers RQ1)

Everything so far runs at one store size, which cannot support a deployability
claim. Vary it.

- Build stores of ~100, 500, 1000, and 5000 facts by padding the v2 targets with
  generated bystanders. The target set stays fixed; only the surrounding store
  grows.
- For each size, run OURS end to end on a fixed sample of ~40 targets and record:
    oracle calls per deletion, split by stage
    wall-clock latency per deletion, split by stage
    cache hit rate
    NARROW recall@k — the fraction of true operands that survive into the
      candidate set. This is the deployability bottleneck: if retrieval drops an
      operand, every downstream stage is working from an incomplete picture and
      the deletion silently misses a path.
- Plot each against store size. State whether cost grows sub-linearly, linearly,
  or worse, and where the dominant term sits.
- Report a PROVENANCE COUNTERFACTUAL: if the memory system maintained a
  derivation lineage at write time, stage 2 would collapse to a graph lookup.
  Compute what total cost would become if stage 2 were free. This is the
  deployability recommendation.

CHECKPOINT 6b — report the scaling curves and wait.

## Phase 7 — Memory systems

Now expand from the primary system to all four: Mem0, Mem0g, Zep/Graphiti, Letta.
The Mem0g adapter was built in Phase 1b — reuse it, do not rebuild.

Before running, confirm Neo4j isolation still holds between Mem0g and
Zep/Graphiti. A cross-contaminated graph invalidates every residual-survival
number in this phase.

Mem0g needs BUILDING — `systems/mem0_adapter.py` currently has no graph support.
Add graph mode over the existing Neo4j instance (NEO4J_URI etc. are already in
config.py for Zep). Either extend the Mem0 adapter with a graph flag or add
`systems/mem0g_adapter.py`, whichever fits `MemorySystemAdapter` more cleanly.
Implement `list_graph` and `supports_graph` for it.

Include Letta — do NOT exclude it for non-atomicity. Run two conditions:
  direct_injection: one fact per memory item via API, no conversational turns.
                    This is the controlled substrate across all four systems.
  conversational:   same facts through dialogue, letting each system's write-time
                    pipeline extract/dedup/summarise as it normally does.

Report ATOMICITY FIDELITY per system: artifacts stored per injected fact, and
where extras live (duplicates, triples, summaries, core-memory copies). This is
a finding, not a confound to hide.

CHECKPOINT 7 — report per-system results and atomicity fidelity. Wait.

## Phase 8 — Results and paper rewrite

Write all results to `data/results/v2/` as JSON + CSV, matching the existing
naming convention. Organise every table under the RQ it answers.

RQ1 — REALISTIC
  1a. Oracle calls per deletion, by stage and by method
  1b. Wall-clock latency per deletion, by stage
  1c. Scaling curves over store size (from Phase 6b)
  1d. NARROW recall@k by store size
  1e. Cache hit rate, and the provenance counterfactual cost

RQ2 — SAFE
  2a. Post-deletion recovery rate under each of the five adversary probe types,
      by family and by system
  2b. OURS vs A0 native delete — the headline safety delta
  2c. Fragility rate by family and method
  2d. Fragile-but-undetected rate by method on families (b) and (c)

RQ3 — SEVERE
  3a. Deletion count |D| by k* and by family, all methods
  3b. Necessary vs unnecessary split, defined as:
        necessary   = |D ∩ M|, M = the ground-truth minimal set closest to D
        unnecessary = |D| - necessary
        precision   = necessary / |D|
        recall      = necessary / k*
  3c. Bystander false-deletion rate on family (d)
  3d. Collateral: how many OTHER targets' recoverability changed as a side
      effect of deleting D
  3e. CEILING - OURS (discovery error) and B3 - OURS (value of minimum solving)

CROSS-CUTTING
  4. Atomicity fidelity per system and injection condition

Report as curves over derivation depth and k* wherever the metric supports it,
never as a single aggregate.

Then rewrite `paper/deletion_completeness_aaai.tex`:
- New framing: discovery of re-derivation structure + minimum co-deletion +
  fragility measurement.
- Structure the results section around RQ1/RQ2/RQ3, one subsection each.
- Remove the certificate contribution and every certificate claim.
- Keep the three-channel decomposition ONLY as background/motivation, not as
  the headline contribution.
- Update `paper/CLAIMS_LEDGER.md` so every claim maps to a v2 result file.
- Every number must come from a file in `data/results/v2/`. Flag any number you
  cannot source.

Before editing the .tex, show me a section-by-section diff plan and wait.

## Start

Begin with Phase 0 and stop at CHECKPOINT 0.