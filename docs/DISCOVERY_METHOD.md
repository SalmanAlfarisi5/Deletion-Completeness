# Method: Discovering Re-Derivation Paths by Black-Box Intervention

*Canonical spec of the new approach. Supersedes the method sections of `DISCOVERY_PIVOT_PLAN.md` (kept as the plain-language explainer).*

---

## 1. The problem

A user asks the agent to forget value `V` (e.g. Alice's salary, `S$8,500`). We delete the memory stating it. But surviving memories can **re-derive** `V`:

- `m1` = "Alice is a Senior SWE at Google Singapore"
- `m2` = "A Senior SWE at Google Singapore earns ~S$8,500/month"
- `m3` = "Alice's S$4,000 rent is 47% of her salary"

`{m1,m2}` re-derives `V`. So does `{m3}` alone. So does `{m1}` + world knowledge. Real forgetting = delete enough memories to break **every** such path.

## 2. What changes

| | Old | New |
|---|---|---|
| The DAG (which memory-sets re-derive `V`) | **Given** — we wrote it when generating data | **Discovered** — by testing the live system |
| Deletion solver | ours | unchanged (reused) |
| Certificate | verdict + scores | + discovered paths, miss-bound, monotonicity violations |

Everything already built (adapters, judge, solver, certificate, results) becomes the **second half**. The new work is the first half.

## 3. Contribution

> **Discover the re-derivation DAG by black-box intervention, and evaluate how complete that discovery is.**

Of the stages below, **Stage 1 (retrieval) and the co-deletion solve inside Stage 3 are standard and not claimed as novel.** The contribution is the **masking oracle** (Stage 2), the **path discovery** that runs on it (Stage 3), and the **evaluation** of completeness and non-monotone behaviour (Stage 4).

## 4. The algorithm

### Stage 1 — Narrow (no LLM)

Reduce thousands of memories to ~20 candidates `C`.

1. **Query expansion**: query with `V`'s surface forms + subject + attribute (not one string).
2. **BM25** (exact/rare tokens: `8500`, names, IDs) **∪ dense embeddings** (paraphrase: "compensation" ≈ "salary") → top ~100.
3. **Cross-encoder reranker** (e.g. BGE-reranker, local, free) → top ~20.

**Recall-first**: over-including is cheap (Stage 3 prunes); under-including loses a path forever. We **measure** filter recall and fold misses into the miss-bound.

### Stage 2 — The oracle (the one primitive)

```
ORACLE(S, V) -> yes/no
    # "If memory holds exactly S (+ fixed world knowledge),
    #  can the adversary reconstruct V?"
    votes = [judge(adversary_LLM(context=S, ask_for=V), V)
             for _ in range(n_samples)]
    return majority(votes)          # cost: n_samples LLM calls
```

- **World knowledge is fixed background** — we vary only which stored memories are present. A memory counts only if it lifts recovery above the world-only baseline (our existing *context lift*).
- **Noisy by nature.** The adversary *is* a stochastic LLM; that is the phenomenon under study, not a defect. We bound noise with `n_samples` + our gold-validated judge, not by removing it.
- **Working assumption: monotone** — adding memories never reduces recovery. Violations are detected (§6), not assumed away.

### Stage 3 — Discover the paths, then solve once

A **path** = a minimal set of memories that re-derives `V` (drop any member → it stops). Discovery has two parts (a, b); the solver is then called **once** (c).

**(a) Shrink — the cheap seeder** *(one path in ~|C| oracle calls, any size)*
```
SHRINK(S):                       # precondition: ORACLE(S)=yes
    for m in S:
        if ORACLE(S - {m}) == yes: S = S - {m}   # m was not needed
    return S                                      # a minimal path
```
Run it a few times from different starting subsets to seed some paths early — including large ones that (b) is too expensive to reach.

**(b) Level-wise — the completeness workhorse** *(finds every path of size ≤ k)*
```
for size = 1 .. k:
    for each subset T of C with |T| = size:
        if T contains an already-found path: skip   # superset -> not minimal
        if ORACLE(T) == yes: record T as a path
```
Superset pruning (using the paths (a) already found) removes most of the work. **Guarantee:** afterwards, every path of size ≤ k has been found. We never enumerate all 2^|C| subsets — real paths are small (our own data maxes at **4** memories), so a small k covers them.

**(c) Solve the co-deletion — once.** Collect all paths `P` from (a)+(b); that set of paths **is** the discovered DAG (§5). Hand it to the solver a single time:

- variable `x_i ∈ {0,1}` — delete memory *i* or not
- **minimize** `Σ x_i` (fewest deletions)
- **subject to** `Σ_{i∈P} x_i ≥ 1` for every path `P` (break every path)

A **solver** is an off-the-shelf program (ILP via PuLP/CBC, or MaxSAT) that returns the provably optimal deletion set `D` from that description — we don't write the search. Brute force already suffices at our scale; the solver only earns its place if paths/candidates grow or costs become non-uniform.

> *Why one solve, not a loop:* an alternative "duality loop" calls the solver repeatedly *during* discovery (delete the current best set, ask the oracle whether anything still leaks, isolate it, re-solve). It is more probe-efficient but harder to analyse. We prefer **discover-then-solve-once**: completeness comes cleanly from the level-wise guarantee (up to k), and the solver stays a single, well-understood final step.

### Stage 4 — Verify + evaluate

Actually delete `D`, then re-probe: `ORACLE(C − D)` should be *no*. We deliberately say **evaluate**, not *certify* — with a noisy oracle and completeness only up to size k, we report evidence and residual risk, not a guarantee. The **evaluation report** records: the discovered paths, the deleted set `D` and its size `k`, the post-deletion recovery check, the judge's measured error rates, the **miss-bound** (only paths *larger* than k could have escaped the level-wise sweep), and any **monotonicity violations** (§6). *(The code artifact is still named `certificate`; only the framing and the verb change.)*

### Grounding: how each stage maps to established work

- **Stage 1 (retrieval).** Recall-oriented retrieval is a named sub-field — **High-Recall IR / Technology-Assisted Review (TAR)**, goal: find *substantially all* relevant items (Cormack & Grossman, *Continuous Active Learning*, SIGIR 2014). We adopt its recall-first stance; the concrete retriever is the standard hybrid RAG stack (BM25 ∪ dense embeddings, fused, + cross-encoder reranker). Honest limit to cite: TAR recall plateaus at ~80–90% before the long tail — exactly the Stage-1 recall gap we fold into the miss-bound.
- **Stage 2 (the oracle).** Our masking primitive — ablate random subsets of context, run the LLM, observe whether V is reconstructed — **is ContextCite's measurement layer** (Cohen-Wang et al., NeurIPS 2024). We build on it and differ in the **decoder**: ContextCite (and CAMAB, AttriBoT/leave-one-out, TokenShapley) fit a *linear/additive surrogate* and emit **per-source importance scores**, which *structurally cannot* express conjunction (A∧B required, neither alone). We recover the **boolean minimal-sufficient-set structure** instead. None of these has been applied to deletion/unlearning — that use is open.
- **Stage 3 (set recovery).** Recovering minimal sufficient sets from yes/no queries is **membership-query / monotone-DNF learning** (Angluin lineage; Abasi, Bshouty & Mazzawi, COCOA 2014): a monotone function's DNF terms *are* its minimal sufficient sets, with query cost scaling in the number/size of sets, not 2^|C|. We cite this as the frame and contribute the **adaptation to a noisy, possibly non-monotone LLM oracle**, which the classical clean-oracle algorithms do not tolerate.
- **Stage 3(c) (co-deletion).** Minimum hitting set over the discovered sets = **axiom pinpointing / Reiter hitting-set repair** and the minimal-deletion-set idea of **Deep Unlearning** (arXiv 2410.15153). Standard; not claimed as novel.

## 5. How the DAG is built (simpler than it sounds)

**The DAG *is* the list of minimal paths.** No tree construction.

- one path = an **AND** group (all members needed)
- several paths = **OR** (any one suffices)

Found `P1={m1,m2}`, `P2={m3}` ⟹ **`V` recoverable ⟺ (m1 ∧ m2) ∨ m3**.

Thresholds fall out for free: "≥2 of {a,b,c}" appears as paths `{a,b}, {a,c}, {b,c}`.

## 6. Non-monotonicity (detected, not assumed away)

A memory can **suppress** recovery — e.g. `m4` = "Correction: that salary record was an error." Then `{m1,m2}` leaks but `{m1,m2,m4}` does not.

**Detection rule:** whenever `ORACLE(smaller) = yes` while `ORACLE(bigger) = no`, log a violation.

**Why it matters:** "currently unrecoverable" ≠ "safely forgotten" — deleting the *masking* memory `m4` brings `V` back. Measuring how often this happens is itself a finding; formal-logic methods cannot address it (formal entailment is always monotone).

## 7. Ground truth: needed for evaluation, not operation

| Purpose | Needed? |
|---|---|
| **Run the method in the wild** | **No** — the oracle test *is* the measurement. A real user's true DAG is unknowable and unnecessary. |
| **Evaluate it for the paper** | **Yes** — to say "discovery recovered 90% of the true paths." |

We already have it: the **298 multi-hop facts carry the true DAG** we generated → free gold labels. The synthetic generator (§Experiments) supplies unlimited more.

## 8. Assumptions and limits

1. **Read access to memory texts** (`list_memories`, `memory_text`) — already in our adapter interface and threat model. No model internals needed.
2. **Monotone recovery** for the core guarantee; violations measured and reported.
3. **Completeness only up to size k** — larger paths may be missed; the evaluation report says so.
4. **Filter recall** — a memory missed in Stage 1 is a path never found; measured and folded into the bound.
5. **Uniform deletion cost** — we have no utility-loss data, so weighted hitting set stays future work.

## 9. Positioning (must be stated, not hidden)

**Cite head-on; do NOT claim as new:** the re-derivation concept + minimal deletion set + hitting-set repair (*Deep Unlearning*, arXiv 2410.15153; axiom pinpointing); the masking measurement primitive (*ContextCite*, NeurIPS 2024); recovering minimal sufficient sets from yes/no queries (monotone-DNF membership-query learning); and "a deleted value may still be inferable" (inference-aware DB deletion; privacy onion-effect). ContextCite even already models *suppressive* sources — so we do not claim novelty for the existence of non-monotone behaviour, only its **deletion-safety consequence**.

**Our contribution is the specific combination none of them has:** discovering the re-derivation structure of a *deployed LLM agent's natural-language memory* by **black-box masking**, for **right-to-be-forgotten**, with (i) a **validated-judge oracle** under noise, (ii) a **boolean set-recovery decoder** where context attribution stops at linear per-source scores, (iii) an explicit **miss-bound** (residual-risk estimate, not a guarantee), and (iv) a **deletion-safety characterization of suppressor (non-monotone) memories** — deleting a masking memory re-opens the leak. The closest applied works **assume** the dependency graph (Agentic Unlearning 2602.17692; MemLineage; P2E2 2507.00343); we **recover** it.

*Caveat before citing 2026 preprints as "they assume, we discover": verify that wording from their PDFs.*
