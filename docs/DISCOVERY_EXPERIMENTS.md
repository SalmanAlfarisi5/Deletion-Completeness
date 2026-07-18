# Experiment Plan: Discovery of Re-Derivation Paths

*Companion to `DISCOVERY_METHOD.md`. Every experiment names the claim it backs. Cheap-first: synthetic proves the algorithm, real LLM demonstrates it.*

---

## 1. Baseline ladder (used throughout)

| # | Method | What it represents |
|---|---|---|
| B0 | Delete only the stated record | naive deletion (today's systems) |
| B1 | Pairwise LLM entailment scoring | **our current paper** — no discovery, per-memory scores |
| B2 | **Discovery (ours)** | build the DAG by intervention |
| B3 | True DAG handed to the solver | **upper bound** — what the old paper assumed |

`B3 − B2` = **the price of not knowing the DAG.** `B2 − B1` = **what discovery buys.**

## 2. Phase A — Synthetic oracle (free, no API, no GPU)

We generate hidden path-structures where the answer is known, then let the algorithm probe them, injecting noise at our judge's **measured** rates.

**Generator knobs:** #candidates `|C|`, #paths, path size (1–5), overlap, oracle false-accept / false-reject rate, non-monotonicity rate.

| ID | Experiment | Claim it backs |
|---|---|---|
| **A1** | Discovery accuracy vs known structure (path precision / recall / exact-DAG match) | the algorithm recovers the true structure |
| **A2** | **Completeness-vs-cost curve**: paths found and probes spent as `k` = 1→5 | the guarantee has a measurable price |
| **A3** | **Noise sensitivity**: sweep oracle error 0→20%, measure degradation | robust at our real judge's error rate |
| **A4** | **Miss-bound calibration**: over many runs, does "no path ≤ k missed w.p. ≥ 1−δ" actually hold? | our certificate is honest, not decorative |
| **A5** | **Non-monotone stress**: inject masking memories, measure discovery breakage | we know when the method fails |
| **A6** | **Cost scaling**: probes vs `|C|` and `k` | the method is affordable / where it isn't |

Phase A is the scientific core: unlimited instances, exact ground truth, zero cost.

## 3. Phase B — Real LLM oracle on existing data (small, gold-labelled)

Uses the **298 multi-hop facts**, whose true DAG we already have → **free answer key, no new labelling.**

| ID | Experiment | Claim it backs |
|---|---|---|
| **B1e** | **Discovery accuracy vs true DAG** — path precision/recall on real facts | discovery works with a *real* noisy LLM |
| **B2e** | **Price of discovery**: run the solver on discovered DAG (B2) vs true DAG (B3); compare collateral `k`, deletion correctness | quantifies what not-knowing-the-graph costs — **headline** |
| **B3e** | **Baseline ladder**: B0 vs B1 vs B2 vs B3 on post-deletion recovery | discovery beats pairwise scoring and naive deletion |
| **B4e** | **Filter recall study**: BM25 vs dense vs hybrid vs +reranker — how often is a true path member missed? | justifies the retrieval stack; quantifies one miss source |
| **B5e** | **Non-monotonicity rate in the wild**: how often does adding a memory *reduce* recovery? | **novel finding** — impossible for formal-logic methods |
| **B6e** | **Bounded certification**: exhaustive to `k=2`, report "no path ≤ 2 missed" | a real guarantee, not a hope |

## 4. Phase C — Deployed systems (demonstration)

Run the full pipeline unchanged on **Mem0 / Zep-Graphiti / Letta** over a small sensitive-PII set.

| ID | Experiment | Claim it backs |
|---|---|---|
| **C1** | End-to-end audit + certificate per system | the framework runs on real deployed memory |
| **C2** | Cross-system discovery differences | re-derivation structure is system-dependent |
| **C3** | Retained findings (duplication / stale summaries / agent-loop) | preserves our existing empirical contribution |

## 5. Metrics

| Metric | Definition |
|---|---|
| **Path precision / recall** | discovered paths vs true paths |
| **Exact-DAG match** | discovered path-set == true path-set |
| **Deletion correctness** | after deleting `D`, is `V` unrecoverable? |
| **Collateral `k` vs `k*`** | our deletions vs optimum from the true DAG |
| **Probes / target** | LLM calls consumed |
| **Filter recall** | fraction of true path members surviving Stage 1 |
| **Non-monotonicity rate** | % of tests where adding a memory reduced recovery |
| **Miss-bound calibration** | claimed δ vs observed miss frequency |

## 6. Cost

Per target ≈ `(#paths + 1) × |C| × n_samples` LLM calls. With `|C|=20`, 3 paths, `n_samples=4` → **~320 calls (~$0.30–$3)**.

| Level | Subsets | Calls | Where |
|---|---|---|---|
| k ≤ 1 | 20 | ~80 | real |
| k ≤ 2 | 190 | ~760 | **real — affordable certification** |
| k ≤ 3 | 1,140 | ~4,560 | borderline (pruning helps) |
| k ≤ 4 | 4,845 | ~19,400 | **synthetic only** |

Dozens of real targets fit inside the $200 budget. This is exactly why Phase A carries the algorithmic claims and Phase B/C stay small — and a small real eval is **defensible** because each target is genuinely expensive and graded against gold.

## 7. Ablations

- **Retrieval**: BM25 / dense / hybrid / +reranker (→ B4e)
- **Discovery**: shrink-only vs level-wise vs hybrid
- **`n_samples`**: 1 / 4 / 8 — noise vs cost
- **`k`**: completeness vs budget (→ A2)
- **Judge**: production vs pinned — oracle quality → discovery quality

## 8. Data needed

| Need | Status |
|---|---|
| Gold answer key (facts with true DAG) | ✅ 298 multi-hop facts |
| Synthetic generator (+ noise knobs) | ⚠️ **build** — small, no API |
| Memory systems | ✅ Mem0 / Zep / Letta adapters |
| Oracle (adversary + validated judge) | ✅ 4-model panel + gold-validated judge |
| World-knowledge background (ρ / context lift) | ✅ existing |
| Reranker | ⚠️ add — local BGE-reranker, free |
| Per-memory deletion cost | ❌ none → uniform cost; weighted = future work |

**Only two small builds: the synthetic generator and the reranker.**

## 9. What we drop / keep from the current paper

**Keep:** residual vs re-derivation split, three adapters, operands-only control, the 298 facts (now as gold), system-specific residual findings, world-recall ρ as a **scope boundary**.

**Demote:** "minimal co-deletion" as a headline (it assumed the DAG); the solver as a contribution; ρ as the central theoretical result.

## 10. Order of work (abstract due 2026-07-21; method after)

1. **Now → 07-21**: lock framing; write abstract/title around discovery; close the two open prior-art risks.
2. **Week after**: synthetic generator + A1–A6 (the algorithmic claims).
3. **Then**: B1e–B6e on the 298 gold facts (**B2e and B5e are the headlines**).
4. **Last**: Phase C demonstration + certificates.
