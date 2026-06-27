# Deletion-Completeness — Project Status Report

**Project:** Decomposing Recoverability — Minimal Co-Deletion for the Right to be Forgotten in LLM Agent Memory
**Author:** Muhammad Salman Al Farisi (NUS School of Computing) · Advisor: Tan Tian Huat
**Target venue:** AAAI 2027 (abstract 2026-07-21, full paper 2026-07-28)
**Report date:** 2026-06-27
**Scope of this report:** full project state after the *robustness wave* (dataset scale-up, full experiment re-run, and paper sync) completed this session.

---

## 1. Executive summary

The project formalizes **deletion-completeness** for LLM agent memory: when a fact is "deleted," is it actually unrecoverable? It decomposes post-deletion recoverability into **three causally distinct channels** — residual survival, re-derivation from surviving facts, and a parametric floor — gives a **planner** that computes the minimal co-deletion closing the deletable channels, and emits an **auditable certificate**. Because the parametric floor cannot be deleted, certification has a hard limit.

This session took the project from **small-n point estimates** to **statistically-backed results with confidence intervals**, by scaling every dataset ~3–4×, re-running the full experiment battery, and honestly reframing the two findings that the larger sample overturned. Two backup commits checkpoint the work; the science is **locked** (ratified by the research-planning session). What remains is purely mechanical submission prep.

**Headline outcome:** every pillar survived at larger n with tighter CIs; the cross-system hooks replicated at n=10; and two claims were corrected in the open — the ρ-floor is a **measured gradient** (not a sharp bimodal split), and naive-deletion membership leakage became **statistically significant** at the powered sample.

---

## 2. Core contributions (locked framing)

1. **A formal, adversary-relative deletion-completeness criterion** for agent memory, strictly stronger than dependency-bounded database erasure (P2E2), decomposing recoverability into residual / re-derivation / parametric channels.
2. **A minimal co-deletion planner** for the resulting NP-hard problem (reduction from Minimum Hitting Set; Vertex Cover = the 2-operand regime), reaching completeness at **mean collateral k = 0.91** with **0 spurious deletions**, plus a machine-readable certificate separating what deletion achieved from what it cannot.
3. **A *measured* parametric floor ρ and its limit result:** under the worst modeled adversary, **22/49 facts cannot be certified erased** even at zero residual survival — and the count is threshold-dependent, so the certification threshold τ is a deliberate **policy dial**.
4. **Evidence of generality:** the same probe/planner/certificate stack, run on three memory architectures (Mem0 dedup pipeline, Graphiti bi-temporal KG, Letta paging agent), exposes residual survival in all three through *different by-design mechanisms* — including an agent-loop failure prior audits bypass.

**Claims we deliberately do NOT make:** first to evaluate these systems (ForgetEval already benchmarks all three); the parametric/memory split as novel (Agentic Unlearning's "backflow"); the agent-loop finding as a standalone contribution (it is the sharpest *instance* of generality, not the headline).

---

## 3. The robustness wave (this session)

### 3.1 Motivation
The pre-wave evidence rested on tiny samples: planner n=6, re-derivation **bin1 n=1** (a single fact), ρ-gradient n=15, cross-system n=3. Point estimates at those sizes carry enormous Wilson intervals, so the work was credible in mechanism but fragile in statistics.

### 3.2 The multi-agent build (Wave 1 + Wave 2)
Seven implementer agents executed a planned audit→build:

| Agent | Task | Result |
|------|------|--------|
| **A** | Worst-adversary certificate fix (`exp07_rho_gradient.py`) | ρ = max over reasoners; reproduced 9/15 on old data |
| **B** | `evaluation/stats.py` (Wilson + bootstrap CIs) wired into exp01–04/07 | CIs in print + JSON |
| **C** | Pin `mem0ai 2.0.7` / `letta 0.16.8` / `chromadb 1.5.9` + `requirements.lock` | reproducible env |
| **D** | Unit tests for number-handling functions | 46 tests pass, **no bugs found** |
| **E** | judge-recall-from-file; `value_segment` de-dup; untrack vendor file | hygiene |
| **F** | **Data generator + validator**; scale all datasets | enlarged data (see §3.3) |
| **G** | Re-run full battery on new data; scale cross-system; update paper | new numbers + paper sync (~$11) |

### 3.3 Dataset scale-up
New tooling: `data/generate_facts.py` (gpt-4o-mini authoring, kept **separate** from measurement to avoid circularity) + `data/validate_facts.py` (per-set invariant gates).

| Dataset | Before | After | Notes |
|--------|--------|-------|-------|
| `isolated_facts.json` | 12 | **48** | non-recoverable PII facts |
| `multi_hop_facts.json` | 6 | **34** | **bins: 17 stored / 17 stored+world** (bin1 was n=1) |
| `context_facts.json` | 21 | **101** | 67 entailing operands / 34 bystanders |
| `rho_gradient_facts.json` | 15 | **49** | hypothesis tiers 17/17/15 |
| Distinct personas | 3 | **21** | fictional, Singapore-plausible (Chinese/Malay/Indian/Eurasian) — kills the "effective n=3" objection |

**Methodological note (anti-selection-bias):** for the ρ-gradient set, mismatches between the *authored* tier hypothesis and the *measured* tier are **flagged, never discarded** — silently dropping mismatches would manufacture a clean gradient that doesn't exist. The validator's persona guard also caught and removed 2 real public figures (Halimah Yacob, Sukhbir Singh Badal).

### 3.4 Two incidents (and the lesson)
Both F and G hit the **same failure mode**: a long job was backgrounded and the agent ended its turn expecting an auto-resume that didn't fire. F additionally set up a `Monitor` on its own log, whose event envelopes ("the user sent you a new message…") it mistook for a user redirect and stopped. Both recovered — F's data was sound despite the messy loop; G was nudged back and drove the whole battery to completion. **Lesson (now in memory):** long-running subagents must run synchronously or background-wait actively, must not use `Monitor`/self-notification loops, and a stopped agent's on-disk output must be verified before it's trusted.

---

## 4. Final results — all numbers, old → new

All CIs are 95%. Computed via `evaluation/stats.py` (Wilson for proportions, bootstrap for means), re-verified from `data/results/*.json`.

| Experiment | Old | New | n |
|-----------|-----|-----|---|
| **exp01** naive residual (Mem0) | 75% | **97.9%** [89.1, 99.6] | 48 |
| **exp02** naive → aware residual | 83% → 0% | **68.75%** [54.7, 80.0] → **0%** [0, 7.4] | 48 |
| **exp03** planner completeness | 100% | **100%** [90, 100] | 34 |
| **exp03** mean collateral *k* | 1.17 | **0.91** [0.74, 1.09] | 34 |
| **exp03** spurious deletions | 0 | **0** | 34 |
| **exp03** depth-first comparator | k=5.5, 22 spurious | **k=5.65** [5.44, 5.85], **126 spurious** | 34 |
| **exp04** bin1 leak (stored) | 100% (n=1) | **100% / 94%** [0.73, 0.99] (mini/4o) | 17 |
| **exp04** bin2 leak (stored+world) | 80% (n=5) | **59% / 65%** [0.36, 0.83] (mini/4o) | 17 |
| **exp04** after co-delete | 0% | **0%** [0, 0.18] | 17 |
| **exp07** certifiable (ρ≤τ) | 6/15 | **27/49 = 55%** [41.3, 68.2] | 49 |
| **exp07** uncertifiable (worst-adv) | 9/15 (60%) | **22/49 (45%)** | 49 |
| **exp08** intact MIA | AUC .72, p=.002 | **AUC .69, p=.001** | 48+96 |
| **exp08** naive MIA | AUC .61, p=.065 (ns) | **AUC .68** [.59, .77], **p=.001 (SIGNIFICANT)** | 48+96 |
| **exp08** aware MIA | AUC .51 (ns) | **AUC .52** [.41, .62], p=.36 (ns) | 48+96 |
| **exp09** Graphiti edge / summary residue | 33% / 67% | **40% / 80%** | 10 |
| **exp10** Letta faithful / archival residue | 0% / 100% | **0% / 100% / 0% core** | 10 |

**Not re-run this session:** `exp11` (Letta re-derivation) and the Mem0 duplication factorial (`exp05`) — the paper carries their prior values, and `exp11`'s Letta bin rates (bin1 100%, bin2 80%/100%) are kept as the un-re-run port, mirrored verbatim in both paper versions.

---

## 5. The two reframes (ratified and locked)

### A — ρ floor: bimodality died, gradient + policy-dial survives
At n=15 the worst-adversary ρ was *sharply bimodal* (`{0 ×6, ≥0.5 ×9}`, nothing between), which made "9/15 uncertifiable" τ-invariant. **This did not replicate at n=49:** the split is **27 at ρ≤τ / 8 in an intermediate band / 14 at ρ≥0.5** (`is_bimodal=False`), and **16/49** facts measured a different tier than authored. Consequences, applied to both paper versions:
- Every "bimodal" / "τ-invariant" / "cherry-pick" line **deleted**.
- Reframed positively as a **measured gradient of parametric recoverability**, with τ a **deliberate policy dial** — real facts sit on either side of wherever the auditor sets it.
- The **limit result survives** (ρ≥τ ⇒ no deletion certifies erasure); only the bimodality/invariance gloss died. Uncertifiable fraction moved 60% → **45%**.

### B — MIA: borderline flipped to significant
At the powered sample (48 members + 96 matched twins), naive single-record deletion now leaves a **statistically significant** membership signal (AUC 0.68, p=.001, CI excludes 0.5), while **artifact-aware deletion still restores indistinguishability** (AUC 0.52, p=.36). The old §6 hedge ("not demonstrated to leak / borderline p=.065") is obsolete. MIA is treated as a **supporting result, not a 4th pillar** — it stays out of the abstract's contribution list and remains in §6 as the "retracted → powered → significant" credibility arc.

---

## 6. Repository state

### 6.1 Structure (post-tidy)
```
Deletion-Completeness/
├── README.md, REFERENCES.md          # entry point + citation notes
├── config.py, llm.py                 # top-level config + model client
├── Makefile, requirements.txt/.lock  # build + pinned env
├── certificate/  evaluation/  experiments/  pipeline/
├── planner/      probes/      systems/      tests/        # modular source
├── data/
│   ├── facts/                        # the 4 enlarged datasets (tracked)
│   ├── generate_facts.py, validate_facts.py   # data tooling
│   └── results/                      # experiment outputs (JSON tracked-as-needed;
│                                     #   chroma store / llm_cache / csv / certs gitignored)
├── paper/
│   ├── deletion_completeness_aaai.tex    # AAAI submission version (needs aaai2027.sty)
│   ├── supervisor_draft.tex              # self-contained version (compiles standalone)
│   ├── CLAIMS_LEDGER.md, references.bib
└── docs/
    ├── CODEBASE_EXPLAINED.md
    └── PROJECT_STATUS_REPORT.md       # this file
```

### 6.2 Tidying done this session
- Removed all `__pycache__/` and `.pytest_cache/` build noise.
- `.gitignore` now excludes the regenerable churn: Chroma vector store (`chroma_huggingface/`), `llm_cache.json`, `data/results/*.csv`, `data/results/certificates/`, `.pytest_cache/`. (Git status untracked count dropped 19 → 9.)
- Pruned `data/results/certificates/` from 178 → 83 (newest cert per fact ID), preserving the paper-cited **R11 (INCOMPLETE)** and **F040 (COMPLETE)**.
- Moved the deep-dive `CODEBASE_EXPLAINED.md` into `docs/` (it was unreferenced; `REFERENCES.md` kept at root because the locked ledger links it).

### 6.3 Commits (on `main`, **local — not yet pushed**)
- `0626e60` — robustness wave: scaled datasets, CIs, re-run battery, ρ-floor reframed.
- `7dff835` — lock §5.2: anti-selection-bias clause + "intermediate band".
- *(pending this session)* — supervisor_draft sync + repo tidy + this report.

The local Chroma vector store and `llm_cache.json` are intentionally untracked (large, regenerable).

---

## 7. What's left (all mechanical — no science)

1. **Push** the backup commits: `git push origin main` (run via `!git push origin main`).
2. **Compile for page count:** drop `aaai2027.sty` + `aaai.bst` into `paper/` and build `deletion_completeness_aaai.tex`; trim only if over the limit. (`supervisor_draft.tex` already compiles standalone.)
3. **References:** fill the author fields in `references.bib`; verify the 5 arXiv IDs / titles / venues against the real PDFs.

---

## 8. Reproducibility & key gotchas (for continuity)

- **Environment:** project venv at `/home/salman/Desktop/venv/myenv` (Python 3.12.3); pinned deps in `requirements.txt` + full lock in `requirements.lock`. `make test` runs the 46 unit tests.
- **Models:** OpenAI `gpt-4o-mini-2024-07-18` (primary reasoner + judge) and `gpt-4o-2024-08-06` (worst adversary); local `all-MiniLM-L6-v2` embeddings on GPU. τ = 0.10.
- **Local services** (start only for cross-system exp09/exp10; all torn down at session end): Postgres (`~/pg-env`, :5432), Letta server (:8283), Neo4j (`~/neo4j-stack`, :7687, user `neo4j`). Start commands are in the project memory.
- **Load-bearing gotchas:** Mem0 2.0.7 uses `filters={"user_id":…}` and returns `{"results":[…]}`; Mem0 silently duplicates facts at store scale (drives the residual numbers); `infer=True` rewrites/merges facts (exp04 uses `infer=False`); recovery scored by a validated LLM judge (0 false-accepts on n=8 gold negatives → lower-bound framing, Wilson upper ≈0.32); the entailment judge must be `gpt-4o` (gpt-4o-mini false-fires on 41.7% of insufficient partial operands, inflating collateral k).
- **Worst-adversary rule:** certificates certify erasure only under `ρ = max over modeled reasoners < τ`; this is why 22/49 (not 14/49 under the weaker reasoner alone) are uncertifiable.

---

*Generated as the consolidated status report for the Deletion-Completeness project. The science is locked; the paper exists in two synced versions; the remaining work is submission mechanics.*
