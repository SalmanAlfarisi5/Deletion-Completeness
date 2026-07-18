# Positioning & Related Work — Consolidated Research Findings

*Single reference for where our methodology sits. Consolidates three literature passes: (1) mechanism/novelty check, (2) end-to-end pipeline novelty check, (3) Stage 1+2 grounding. Each claim below carries a confidence flag. Companion to `DISCOVERY_METHOD.md`.*

---

## 1. Verdict

**NOVEL as an end-to-end pipeline; each individual component is prior art.** The untaken piece is **discovering the re-derivation structure of a deployed LLM agent's natural-language memory by black-box masking, for right-to-be-forgotten**, together with the evaluation apparatus (validated-judge oracle under noise, boolean set-recovery, miss-bound, suppressor/non-monotone deletion-safety). We must **cite the neighbours head-on** and claim novelty only on the *combination + setting + decoder*, never on the mechanism. *(Confidence: medium-high — a synthesis judgment; the individual collisions are high-confidence.)*

## 2. What we claim vs what we only cite

| We CLAIM as our contribution | We CITE, do NOT claim as new |
|---|---|
| Discover (not assume) the structure by **black-box masking** of a deployed LLM's NL memory | The re-derivation concept ("deleted value still inferable") |
| **Boolean set-recovery decoder** (minimal sufficient sets) where attribution stops at per-source scores | Minimum **hitting-set** deletion / repair |
| **Validated-judge oracle** under noise; **miss-bound** (residual-risk estimate) | The **masking measurement primitive** (ContextCite) |
| **Deletion-safety** consequence of suppressor (non-monotone) memories | Recovering sufficient sets from yes/no queries (monotone-DNF learning) |
| The RTBF / **deployed-agent-memory** instantiation | The mere *existence* of suppressive sources (ContextCite models them) |

## 3. Closest prior art, by area

### A. Formal-logic mechanism — axiom pinpointing / justifications *(strongest mechanism collision; high confidence)*
The exact abstract mechanism (find minimal entailing subsets → repair by hitting set) is a mature SAT/MUS field.
- **Peñaloza, *Axiom Pinpointing* survey** (arXiv 2003.08298) — minimal entailing sub-ontologies; repair = hitting set over justifications.
- **Moodley, Meyer & Varzinczak** (RR 2011) — treats the reasoner as a **black-box yes/no oracle**, computes *all* justifications via Reiter's Hitting Set Tree, deletion = minimal hitting set. Closest structural analogue.
- Also: Schlobach & Cornet 2003; Kalyanpur–Parsia–Horridge–Sirin (ISWC 2007); Sebastiani & Vescovi 2009; Arif–Mencía–Marques-Silva (arXiv 1505.04365, EL⁺ pinpointing = group-MUS via SAT).
- **Gap:** formal ontology + *sound, monotone* reasoner. We have natural language + a *noisy* LLM. → cite as the mechanism we transfer.

### B. LLM-memory unlearning — closest *application* *(they ASSUME the graph; 2026 preprints = abstract-depth, verify before citing as contrast)*
- **Agentic Unlearning / SBU** (arXiv 2602.17692, Feb 2026) — dependency-closure deletion over a **write-time-recorded** provenance graph. Assumes structure; no discovery, no SAT.
- **MemLineage** (arXiv 2605.14421, May 2026) — records the derivation DAG **at write time**; trust by graph traversal. Assumes structure.
- **P2E2 / "Meaningful Data Erasure in the Presence of Dependencies"** (VLDB 2025, arXiv 2507.00343) — min-cost cell-nulling to block inference (hitting-set-style, NP-hard); **assumes dependency rules given, explicitly defers their discovery**; relational DB, not NL.
- **"Do LLMs Really Forget?"** (Wei et al. 2025, arXiv 2506.05735) — validates our *motivation* (unlearning misses inferential dependencies) but is **evaluation-only**, no deletion method. → cite as motivation.

### C. Deep unlearning — strongest re-derivation collision *(MUST CITE; high confidence)*
- **"Evaluating Deep Unlearning in LLMs"** (arXiv 2410.15153, Oct 2024) — defines deep unlearning (a fact must not be re-deducible from retained knowledge), a **minimal deep-unlearning set**, and **hitting-set-style pruning**. **BUT:** deduction rules are **given** (hand-written + MQuAKE), knowledge is **parametric weights** (not stored NL memories), it is an **evaluation benchmark**, monotone logical entailment only, no LLM judge, no non-monotone cases.
- **Why it matters:** it independently has re-derivation + minimal set + hitting set, so it **pre-empts any novelty claim of the form "we first note a deleted fact re-derives and compute a minimal deletion set."** It does **not** collide with our core (discovery-by-intervention over NL memory), but it forces novelty to be pinned to discovery + setting + decoder.

### D. Context attribution — closest Stage-2 *method* *(high confidence, unanimous)*
All output **per-source importance SCORES, not minimal sufficient SETS** — a linear/additive surrogate *structurally cannot* represent conjunction (A∧B required, neither alone).
- **ContextCite** (Cohen-Wang, Madry et al., NeurIPS 2024, arXiv 2409.00729) — masks random subsets → fits Lasso → per-source scores (~32 masked calls). **Uses our exact masking primitive**, but decodes to scores. Applications: verify statements, prune context, detect poisoning — **never deletion/RTBF**.
- **CAMAB** (arXiv 2506.19977) — bandit-based, per-segment scores.
- **AttriBoT / leave-one-out** (arXiv 2411.15102) — per-source marginal scores, ~|C| calls.
- **TokenShapley** (arXiv 2507.05261) — per-token Shapley scores.
- **How we differ:** same measurement layer, different **decoder** — we recover the boolean set structure. ContextCite already models *suppressive* sources, so our non-monotone claim is the **deletion-safety** consequence, not the observation.

### E. Set-recovery theory — Stage-3 frame *(high confidence)*
- **Monotone-DNF learning from membership queries** — Angluin lineage; **Abasi, Bshouty & Mazzawi** (COCOA 2014, arXiv 1405.0792). A monotone function's DNF terms **are** its minimal sufficient sets; query cost scales in number/size of terms, not 2^|C|.
- **Gap = our core technical contribution:** classical algorithms assume a **clean, monotone** oracle; ours is **noisy and possibly non-monotone**, which they do not tolerate without modification.

### F. Retrieval — Stage-1 frame *(recall side high confidence; hybrid stack assumed-not-verified)*
- **High-Recall IR / TAR / Continuous Active Learning** (Cormack & Grossman, SIGIR 2014; HiCAL SIGIR 2018; Zou & Kanoulas, TOIS 2020) — goal: find *substantially all* relevant items. **Honest limit:** recall plateaus at ~80–90%; the long tail needs near-exhaustive review → feeds our miss-bound.
- **Standard hybrid RAG stack** (BM25 + dense/DPR/ColBERT, fused via RRF, + cross-encoder reranker) — treated as standard common knowledge; *this pass did not independently verify the canonical citations*.
- Note: CAL/TAR is a human-in-the-loop workflow; we adapt its recall-first principle to an automated Stage 1 (a positioning nuance, not a drop-in).

### G. Privacy / databases — the concept is prior art *(high confidence)*
- "Deleted value still inferable from what remains" is established: **privacy onion-effect** (arXiv 2206.10469); deep unlearning (C); inference-aware DB deletion.
- **Deletion propagation** (Buneman, Khanna & Tan, PODS 2002) and query **resilience** — assume the query/view (the derivation) is **given**.
- **Inference-aware & privacy-preserving deletion in DBs** (arXiv 2604.00326, 2026) — hitting-set deletion to block re-inference, but structure derived from **schema/functional dependencies**, relational setting.
- → We do **not** claim the concept "inferable after deletion"; only its discovery + LLM-memory instantiation.

## 4. The single strongest "already done" risk

**Deep Unlearning (arXiv 2410.15153).** It combines re-derivation, minimal deletion sets, and hitting-set pruning. It does **not** collide with our core because it assumes given logical rules over parametric weights and is evaluation-only — but it means our novelty **must** be pinned to *black-box discovery over NL memory + noisy oracle + set-recovery decoder + evaluation*, never to re-derivation-awareness or hitting-set deletion.

## 5. One-sentence positioning

> We are the first to **discover** the re-derivation structure of a deployed LLM agent's **natural-language memory** by **black-box masking**, for **right-to-be-forgotten** — recovering **minimal sufficient sets** (where context attribution stops at per-source scores) via a **validated-judge oracle under noise**, and reporting a **miss-bound** and the **deletion-safety of suppressor memories** — building on axiom-pinpointing, context attribution (ContextCite), and monotone-DNF learning rather than claiming them.

## 6. Open risks & caveats

1. **Noisy + non-monotone oracle vs clean-oracle theory** — the core technical gap (§3E). Both our differentiator *and* the main thing that could break; must be shown to work (synthetic Phase-A experiments: sweep noise, inject suppressors).
2. **2026 preprints read at abstract depth** — verify the "assume vs discover" wording of Agentic Unlearning (2602.17692), MemLineage (2605.14421), and DB deletion (2604.00326) from their PDFs before citing as contrast.
3. **Negative existentials** ("no one applied context attribution to RTBF", "no full-pipeline match") cannot be proven exhaustively — consistent with novel, not proof.
4. **Hybrid retrieval stack** cited as standard but not independently verified in these passes.

## 7. Citation quick-list

| Tag | Ref |
|---|---|
| Deep Unlearning | arXiv 2410.15153 (2024) |
| ContextCite | NeurIPS 2024, arXiv 2409.00729 |
| CAMAB / AttriBoT / TokenShapley | 2506.19977 / 2411.15102 / 2507.05261 |
| Agentic Unlearning | arXiv 2602.17692 (2026) |
| MemLineage | arXiv 2605.14421 (2026) |
| P2E2 (VLDB'25) | arXiv 2507.00343 |
| Do LLMs Really Forget? | arXiv 2506.05735 (2025) |
| Monotone-DNF MQ learning | Abasi–Bshouty–Mazzawi, COCOA 2014, arXiv 1405.0792 |
| Axiom pinpointing | Peñaloza 2003.08298; Moodley RR 2011; Arif 1505.04365 |
| High-Recall IR / TAR | Cormack & Grossman SIGIR 2014; Zou & Kanoulas TOIS 2020 |
| Privacy onion-effect | arXiv 2206.10469 |
| Deletion propagation | Buneman, Khanna & Tan, PODS 2002 |
| Inference-aware DB deletion | arXiv 2604.00326 (2026) |
