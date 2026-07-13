# Deletion-Completeness — Project Status Report

> **Synced to the frontier-judge wave (2026-07-13).** All numbers below reflect the current verified
> run; the authoritative source is **`docs/RESULTS_3X_WAVE.md`** (datasets 253/298/963/250;
> 6 topologies; exact DAG planner + exp12; production judge = frontier Claude Sonnet 5 (pinned gpt-4o-mini/gpt-4o anchor); residual 97.2%→0%; planner exact
> k=1.03; rho 86/250 uncertifiable; MIA .66/.66/.51; Graphiti 83% / Letta 0%-faithful).
> Verified by `evaluation/verify_wave.py` → ALL CHECKS PASS.

**Project:** Decomposing Recoverability — Minimal Co-Deletion for the Right to be Forgotten in LLM Agent Memory
**Author:** Muhammad Salman Al Farisi (NUS School of Computing) · Advisor: Tan Tian Huat
**Target venue:** AAAI 2027 (abstract 2026-07-21, full paper 2026-07-28)
**Report date:** 2026-07-13 (updated to the frontier-judge wave)
**Scope of this report:** full project state after the 3× dataset scale-up (isolated 253 / multi-hop 298 / context 963 / ρ-gradient 250), full experiment re-run, and paper sync.

---

## 1. Executive summary

The project formalizes **deletion-completeness** for LLM agent memory: when a fact is "deleted," is it actually unrecoverable? It decomposes post-deletion recoverability into **three causally distinct channels** — residual survival, re-derivation from surviving facts, and a parametric floor — gives a **planner** that computes the minimal co-deletion closing the deletable channels, and emits an **auditable certificate**. Because the parametric floor cannot be deleted, certification has a hard limit.

This session took the project from **small-n point estimates** to **statistically-backed results with confidence intervals**, by scaling every dataset ~3–4×, re-running the full experiment battery, and honestly reframing the two findings that the larger sample overturned. Two backup commits checkpoint the work; the science is **locked** (ratified by the research-planning session). What remains is purely mechanical submission prep.

**Headline outcome:** every pillar survived at larger n with tighter CIs; the cross-system hooks replicated at n=10; and two claims were corrected in the open — the ρ-floor is a **measured gradient** (not a sharp bimodal split), and naive-deletion membership leakage became **statistically significant** at the powered sample.

---

## 2. Core contributions (locked framing)

1. **A formal, adversary-relative deletion-completeness criterion** for agent memory, strictly stronger than dependency-bounded database erasure (P2E2), decomposing recoverability into residual / re-derivation / parametric channels.
2. **A minimal co-deletion planner** for the resulting NP-hard problem (reduction from Minimum Hitting Set; Vertex Cover = the 2-operand regime), reaching completeness at **mean collateral k = 1.03** with **0 spurious deletions**, plus a machine-readable certificate separating what deletion achieved from what it cannot.
3. **A *measured* parametric floor ρ and its limit result:** under the worst modeled adversary, **86/250 facts cannot be certified erased** even at zero residual survival — and the count is threshold-dependent, so the certification threshold τ is a deliberate **policy dial**.
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
| `isolated_facts.json` | 12 | **84** | non-recoverable PII facts |
| `multi_hop_facts.json` | 6 | **92** | **bins: 34 stored / 34 stored+world + 24 multi-level (12 join / 12 chain)** |
| `context_facts.json` | 21 | **299** | 231 entailing operands / 68 bystanders |
| `rho_gradient_facts.json` | 15 | **81** | hypothesis tiers 39/27/15 |
| Distinct subjects | 3 | **108** | fictional, Singapore-plausible (Chinese/Malay/Indian/Eurasian) — kills the "effective n=3" objection |

**Methodological note (anti-selection-bias):** for the ρ-gradient set, mismatches between the *authored* tier hypothesis and the *measured* tier are **flagged, never discarded** — silently dropping mismatches would manufacture a clean gradient that doesn't exist. The validator's persona guard also caught and removed 2 real public figures (Halimah Yacob, Sukhbir Singh Badal).

### 3.4 Two incidents (and the lesson)
Both F and G hit the **same failure mode**: a long job was backgrounded and the agent ended its turn expecting an auto-resume that didn't fire. F additionally set up a `Monitor` on its own log, whose event envelopes ("the user sent you a new message…") it mistook for a user redirect and stopped. Both recovered — F's data was sound despite the messy loop; G was nudged back and drove the whole battery to completion. **Lesson (now in memory):** long-running subagents must run synchronously or background-wait actively, must not use `Monitor`/self-notification loops, and a stopped agent's on-disk output must be verified before it's trusted.

---

## 4. Final results — all numbers, old → new

All CIs are 95%. Computed via `evaluation/stats.py` (Wilson for proportions, bootstrap for means), re-verified from `data/results/*.json`.

| Experiment | 84-fact wave | frontier-judge wave (current) | n |
|-----------|-----|-----|---|
| **exp01** naive residual (Mem0) | 96.4% [90.0, 98.8] | **97.2%** [94.4, 98.7] | 253 |
| **exp02** naive → aware residual | 96.4% → 0% | **97.2%** [94.4, 98.7] → **0%** [0, 1.5] | 253 |
| **exp03** planner completeness | 100% [96,100] | **100%** [96, 100] | 298 |
| **exp03** mean collateral *k* | 0.90 [0.82, 0.99] | **1.03** [0.98, 1.08] | 298 |
| **exp03** spurious deletions | 0 | **0** | 298 |
| **exp03** depth-first comparator | k=6.05, 342 spurious | **k=6.60, 1192 spurious** | 298 |
| **exp03** exact vs optimum k* (exp12) | — | **gap −0.067 (≤0 every topology, provably minimal)** | 298 |
| **exp04** bin1 leak (stored) | 94–100% (4 reasoners) | **97–100%** (4 reasoners) | 74 |
| **exp04** bin2 leak (stored+world) | 56/59/68/74% | **62/69/69/66%** (mini/4o/Sonnet5/GPT-5.5) | 74 |
| **exp04** after co-delete | 0% | **2.7%** (F043 value-coupling residue) | 74 |
| **exp07** certifiable (ρ≤τ) | 51/81 = 63% | **164/250 = 65.6%** [60.3, 72.0] | 250 |
| **exp07** uncertifiable (worst-adv) | 30/81 (37%) | **86/250 (34%)** | 250 |
| **exp08** intact MIA | AUC .67, p=.001 | **AUC .66** [.637,.688], p=.001 | 253+759 |
| **exp08** naive MIA | AUC .67, p=.001 | **AUC .66** [.637, .687], **p=.001 (SIGNIFICANT)** | 253+759 |
| **exp08** aware MIA | AUC .52 [.498,.552], p=.02 | **AUC .51** [.498, .523], p=.04 (marginal) | 253+759 |
| **exp09** Graphiti edge / summary residue | 30% / 70% | **20% / 83%** | 30 |
| **exp10** Letta faithful / archival / core residue | 0% / 100% / 0% | **0% / 100% / 10% core** | 30 |

**All experiments re-run on the 3× data.** The Mem0 duplication factorial (`exp05`) was re-run: **80–82%** duplication incidence in all four cells, row-inflation **×1.75–1.82** (both byte-identical and paraphrase copies present). `exp11` (Letta re-derivation) was re-run on the **full 298** (all topologies, up from n=40) with the four-reasoner panel: bin1 99–100%, bin2 62/65/65/68% and all 5 structured topologies 100% → **0% after co-delete**, faithful direct co-delete 100%, bystanders intact 100%.

---

## 5. The two reframes (ratified and locked)

### A — ρ floor: bimodality died, gradient + policy-dial survives
At n=15 the worst-adversary ρ was *sharply bimodal* (`{0 ×6, ≥0.5 ×9}`, nothing between), which made "9/15 uncertifiable" τ-invariant. **This did not replicate at scale (n=250):** the split is **164 at ρ≤τ / 41 in an intermediate band / 45 at ρ≥0.5** (`is_bimodal=False`), and **77/250** facts measured a different tier than authored. Consequences, applied to the paper:
- Every "bimodal" / "τ-invariant" / "cherry-pick" line **deleted**.
- Reframed positively as a **measured gradient of parametric recoverability**, with τ a **deliberate policy dial** — real facts sit on either side of wherever the auditor sets it.
- The **limit result survives** (ρ≥τ ⇒ no deletion certifies erasure); only the bimodality/invariance gloss died. Uncertifiable fraction moved 60% → **34%** (86/250).

### B — MIA: borderline flipped to significant
At the powered sample (253 members + 759 matched twins), naive single-record deletion now leaves a **statistically significant** membership signal (AUC 0.66, p=.001, CI excludes 0.5), while **artifact-aware deletion drives the AUC to 0.51** (CI [0.498, 0.523] includes 0.5, but the label-permutation test is marginally significant, p=.04 — it attenuates the signal toward chance without provably eliminating it). The old §6 hedge ("not demonstrated to leak / borderline p=.065") is obsolete. MIA is treated as a **supporting result, not a 4th pillar** — it stays out of the abstract's contribution list and remains in §6 as the "retracted → powered → significant" credibility arc.

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
│   ├── deletion_completeness_aaai.tex    # AAAI submission draft (needs aaai2027.sty)
│   ├── CLAIMS_LEDGER.md, references.bib
└── docs/
    ├── CODEBASE_EXPLAINED.md
    └── PROJECT_STATUS_REPORT.md       # this file
```

### 6.2 Tidying done this session
- Removed all `__pycache__/` and `.pytest_cache/` build noise.
- `.gitignore` now excludes the regenerable churn: Chroma vector store (`chroma_huggingface/`), `llm_cache.json`, `data/results/*.csv`, `data/results/certificates/`, `.pytest_cache/`. (Git status untracked count dropped 19 → 9.)
- `data/results/certificates/` currently holds **884 certs across 173 fact IDs** (several per fact from re-runs); the paper-cited **R11 (INCOMPLETE)** and **F040 (COMPLETE)** are preserved.
- Moved the deep-dive `CODEBASE_EXPLAINED.md` into `docs/` (it was unreferenced; `REFERENCES.md` kept at root because the locked ledger links it).

### 6.3 Commits (on `main`, **local — not yet pushed**)
- `0626e60` — robustness wave: scaled datasets, CIs, re-run battery, ρ-floor reframed.
- `7dff835` — lock §5.2: anti-selection-bias clause + "intermediate band".
- *(pending this session)* — supervisor_draft sync + repo tidy + this report.

The local Chroma vector store and `llm_cache.json` are intentionally untracked (large, regenerable).

---

## 7. What's left (all mechanical — no science)

1. **Push** the backup commits: `git push origin main` (run via `!git push origin main`).
2. **Compile for page count:** drop `aaai2027.sty` + `aaai.bst` into `paper/` and build `deletion_completeness_aaai.tex`; trim only if over the limit.
3. **References:** fill the author fields in `references.bib`; verify the 5 arXiv IDs / titles / venues against the real PDFs.

---

## 8. Reproducibility & key gotchas (for continuity)

- **Environment:** project venv at `/home/salman/Desktop/venv/myenv` (Python 3.12.3); pinned deps in `requirements.txt` + full lock in `requirements.lock`. `make test` runs the 46 unit tests.
- **Models:** the adversary panel is four reasoners — `gpt-4o-mini-2024-07-18` (pinned recovery-judge anchor), `gpt-4o-2024-08-06` (pinned entailment-judge anchor), Claude Sonnet 5 (the production recovery + entailment judge), and GPT-5.5 — with each certificate taking the worst; local `all-MiniLM-L6-v2` embeddings on GPU. τ = 0.10.
- **Local services** (start only for cross-system exp09/exp10; all torn down at session end): Postgres (`~/pg-env`, :5432), Letta server (:8283), Neo4j (`~/neo4j-stack`, :7687, user `neo4j`). Start commands are in the project memory.
- **Load-bearing gotchas:** Mem0 2.0.7 uses `filters={"user_id":…}` and returns `{"results":[…]}`; Mem0 silently duplicates facts at store scale (drives the residual numbers); `infer=True` rewrites/merges facts (exp04 uses `infer=False`); recovery scored by a validated LLM judge — the production judge is frontier **Claude Sonnet 5** (0% false-accept on the n=351 gold [0,.019]); the pinned anchor slips on the harder gold (.0206 gpt-4o-mini / .0052 gpt-4o; Sonnet 5 / GPT-5.5 stay 0) → leak rates stay lower-bound; the entailment judge is also **Claude Sonnet 5** (3.4% near-miss false-fire, best on every axis), with pinned `gpt-4o` retained as the *reproducible dated-snapshot anchor* (multi-hop miss-rate = 0 for all four models; near-miss false-fire 45.5% gpt-4o vs 75.7% gpt-4o-mini). Because the planner co-deletes by the known entailment DAG, judge false-fire never inflates collateral k.
- **Worst-adversary rule:** certificates certify erasure only under `ρ = max over modeled reasoners < τ`; this is why **86/250** (more than any single reasoner would flag alone) are uncertifiable.

---

*Generated as the consolidated status report for the Deletion-Completeness project. The science is locked; the paper is a single AAAI submission draft; the remaining work is submission mechanics.*
