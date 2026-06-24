# References (verified 2026-06-23)

## Core prior work
- **arXiv:2507.00343** — *Meaningful Data Erasure in the Presence of Dependencies*
  (VLDB'25). The P2E2 / never-stored-prior grounding for deletion under
  dependencies. Cite for the formal deletion-completeness definition.
- **arXiv:2604.00326** — *Inference-Aware & Privacy-Preserving Deletion in
  Databases* (submitted 2026-03-31). Cite **by this title**, NOT "SeQureDB"
  (that is the workshop name, not the paper).
- **arXiv:2602.17692** — *Agentic Unlearning*. Confirmed. NOTE: its "backflow"
  already covers the parametric + memory recovery split — so do **not** claim the
  residual-survival / re-derivation decomposition itself as novel. It assumes
  **weight access** (a dual-pathway model edit); **we are memory-store-only**
  (black-box base model, no training-time access). Our novelty is the
  per-artifact-layer operationalization, the planner+certificate, and the
  empirical measurement on real agent-memory systems.

## Mem0 duplication finding (exp05)
Reported as a documented Mem0 behaviour, not an artifact of our setup:
- Mem0 issue **#4896** — hash-only dedup; semantic/paraphrase duplicates slip
  through (matches our paraphrase-dominant duplicates).
- Mem0 issue **#4573** — production audit, ~37.6% near-duplicates; observed with
  both a local model and Claude Sonnet 4.6 (i.e. embedder-independent).
- Mem0 issue **#687** — async write race (the byte-identical subset of dups).

## Related-work positioning (read in full 2026-06-24)

Three distinguished neighbours + the DB lineage. The thread none of the three
agent-memory works pull: **theoretical deletion-under-dependencies grounding**
(P2E2 / SeQureDB) brought to *deployed* agent memory.

- **ForgetEval** — **arXiv:2606.15903** (MIT). The closest neighbour: benchmarks
  **all three of our systems + ~10 more** (Mem0 **68.3% / 43.6%**, Graphiti
  **7.0%**, Letta **65.5%**). **Different, weaker question:** it checks whether a
  **forget command leaves the value in top-k retrieval** — *necessary but not
  sufficient* for completeness. We use a **strictly stronger, causally-decomposed**
  recoverability notion (residual / re-derivation / parametric) on the systems it
  covers, so **system coverage is NOT our novelty** — the stronger notion is.
  - **Mem0-number trap (pre-empt explicitly):** their Mem0 % = forget-command
    success in top-k; **ours = post-deletion recoverability by *any* channel.**
    **Complementary, not contradictory** — say so in-text.
  - **The agent-loop gap (this is what makes C7/exp10 novel):** ForgetEval
    **deliberately BYPASSED Letta's agent loop** — "address archival-memory REST
    endpoints directly, keep the LLM out of the recall hot path." **We tested the
    agent loop they excluded** (vague RTBF → `memory_replace` scrubs core, misses
    archival). Cite the bypass as the gap we fill.
  - **Independent corroboration of our convergence thesis:** their per-system
    notes name the *same mechanisms* we measure — Graphiti "**sheds surface forms /
    synthesised fact string**" (= our stale-summary residual, exp09); Mem0 router
    "**link-and-keep over delete-old**" (= our duplication residual, exp01/05).
    Cite as external support for the three-family convergence.
  - Also: ForgetEval avoids an LLM judge — cite when justifying our judge
    validation (false-accept rate vs oracle, second-judge κ).
- **ForgetAgent** — *IJRASET*. A **synthetic** unlearning **method** (deletion
  receipts + counterfactual-indistinguishability guarantees) on a constructed
  setup. We differ on every axis: **deployed** systems (not synthetic),
  **re-derivation + parametric** channels (not just receipts), and a **diagnostic
  certificate** (audit, not a method-with-guarantees). Neighbour, not overlap.
- **P2E2 / SeQureDB** (**2507.00343**, **2604.00326**) — the **DB-theory lineage**
  for deletion under dependencies (the formal completeness definition + co-deletion
  grounding). **The bridge none of the three agent-memory works make** — our
  co-deletion planner operationalizes this theory on deployed agent memory.
