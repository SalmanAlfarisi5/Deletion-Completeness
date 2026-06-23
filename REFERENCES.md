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
  residual-survival / re-derivation decomposition itself as novel. Our novelty is
  the per-artifact-layer operationalization, the planner+certificate, and the
  empirical measurement on a real agent-memory system.

## Mem0 duplication finding (exp05)
Reported as a documented Mem0 behaviour, not an artifact of our setup:
- Mem0 issue **#4896** — hash-only dedup; semantic/paraphrase duplicates slip
  through (matches our paraphrase-dominant duplicates).
- Mem0 issue **#4573** — production audit, ~37.6% near-duplicates; observed with
  both a local model and Claude Sonnet 4.6 (i.e. embedder-independent).
- Mem0 issue **#687** — async write race (the byte-identical subset of dups).

## Method positioning
- **ForgetEval** — avoids an LLM judge entirely; cite when justifying our judge
  validation (false-accept rate vs oracle, second-judge κ).
