# 3× Expansion Plan & Requirements Checklist

*Working document for the dataset/experiment expansion requested 2026-07-12. Every
requirement the user gave is listed here so nothing is lost. Updated as work lands.*

## Decisions (locked with the user)

| Decision | Choice |
|---|---|
| Target size per dataset | **~250 each** (isolated / multi-hop / context / rho) |
| Budget | **No cap** — "just run it"; re-run the whole battery, update all numbers |
| Judge model | **Switched to the frontier best-validating model — Claude Sonnet 5** (recovery + entailment), decided from the 4-model gold validation. Gold-label validation (0% false-accept on the expanded n=351 gold) is the guarantee, not call-independence. Reproducibility is handled by keeping the **pinned `gpt-4o-mini`/`gpt-4o` numbers as an anchor**; the panel self-adversary overlap (H-01) is an accepted trade-off since gold validation, not call-independence, certifies the judge. |
| Style | Everything **clean and well-documented** |

## Requirements (source: user, 2026-07-12) — each maps to a task

1. **Isolated facts → ~250.** (task 2, 6)
2. **Multi-hop → ~250, much harder topologies** — `((A∨B)∧C)⊢D`, `A⊢B⊢C⊢D`,
   `(C∧D)⊢E with A⊢C, B⊢D`, plus more hard ones we devise. (task 1, 2)
3. **Context facts enlarged** to support the new multi-hop operands + bystanders. (task 2)
4. **rho-gradient → ~250, more diverse** relation families. (task 2)
5. **Recovery judge: many more gold samples** (17 is too small), **try all 4 models**. (task 5)
6. **Entailment judge: many more samples, all 4 models, everything grounded.** Be
   **very robust and careful — do not miss/lose an entailer.** (task 3, 5)
7. **Judge validation is precise:** measured confidence (**Wilson CIs**), **agreement
   (Cohen's κ)**, robust, generally applicable, **lots of samples**. (task 5)
8. **Switch to the best judge model** (with the grounded constraints above). (task 5)
9. **Re-run ALL experiments; update ALL result numbers.** (task 7, 8)
10. **Clean and well-documented.** (task 8, this doc)
11. **MIA sample increased**, and generally: **if any sample is too small, enlarge it
    and re-run.** (task 7)

## Design decisions (grounded)

- **Hard topologies are TEMPLATED (deterministic Python), not LLM-authored.** Grounded
  in the existing code + memory: gpt-4o-mini "reliably drifts to real-world billing with
  wrong arithmetic on multi-step chains," which is why the join/chain sets are already
  templated. Fictional orgs/rules ⇒ exact arithmetic and rho≈0 by construction.
- **Boolean entailment DAG is the single source of truth** (`planner/entailment_dag.py`).
  Each structured fact carries a boolean `formula` over its stored operands describing
  when the target is still re-derivable. The dataset gates, the planner (exact minimal
  co-deletion), and the experiments all read it — so a multi-hop entailer can **never be
  silently missed** by relying on the LLM judge to rediscover the recursion.
- **Minimal co-deletion = minimum hitting set of the formula** (the NP-hard Opt-P2E2).
  Solved exactly on these tiny DAGs. `threshold` (≥k of n) and `or_and` make the minimum
  non-trivial (>1, or greedy-suboptimal), so k-minimality is genuinely *measured*, not
  just asserted.
- **Three independent layers protect against a missed entailer:** (1) known DAG structure
  drives co-deletion; (2) the re-derivation probe reads the *whole* surviving store, so the
  leak is measured empirically; (3) the entailment judge is validated on **both** false-fire
  (over-delete) **and** miss-rate/recall on true entailers, single-hop and multi-hop.

## The hard multi-hop topologies (all templated, fictional, exact, rho≈0)

| Topology | Structure | Minimal co-deletion | What it stresses |
|---|---|---|---|
| `flat` (bin1/bin2) | `A ∧ B ⊢ T` | 1 (delete either) | baseline |
| `join` | `(A∧Ar)⊢B, (C∧Cr)⊢D, (B∧D)⊢T` | 1 | recursion past unstored B,D |
| `chain` | `A⊢B⊢C⊢T` (via r1,r2,r3) | 1 | deep transitive closure |
| `or_and` | `((A∨B)∧C)⊢T` | **1 = {C}** (greedy may pay 2) | OR-minimality; greedy suboptimality |
| `diamond` | `A⊢C, B⊢D, (C∧D)⊢T` | 1 (delete A or B) | recursion; direct entailer unstored |
| `threshold` | `(≥k of n)⊢T` | **n−k+1 (≥2)** | genuine min-hitting-set > 1 |

## Data-generation fixes made during the gate runs (grounded, recorded)

- **Cross-file id collisions** (isolated F132–F215 vs new multi-hop F-ids): isolated and
  multi-hop share the F-id namespace, so new ids are now minted from **disjoint blocks**
  above the global F-max — isolated at `[fmax+1..]`, multi-hop/structured at
  `[fmax+1000..]` (`build_structured` anchored with `f_min`). Gate `cross_file_id_uniqueness`
  catches any recurrence.
- **Isolated value-uniqueness over-strict**: excluded entailing OPERANDS from the check
  (they are never co-injected with isolated facts, so their dense numeric surface caused
  false-positive substring collisions).
- **Isolated authoring can't scale** (gpt-4o-mini reused values: only ~143 distinct of 384):
  added a **templated high-entropy identifier generator** (`author_isolated_templated`) —
  phone/serial/PIN/plate/postal/account, distinct by construction, ρ≈0. LLM authoring kept
  for natural variety; templated fills to ~250.
- **rho distinct-value too strict**: rho facts are measured independently (no exp02 purge
  contamination), so the SAME value may recur across DIFFERENT subjects — `build_rho` now
  skips only exact-duplicate `(subject, value)` facts, which lets rho reach ~250.

Verified (no-LLM build repro): **iso=254, rho=250, mh=258, 0 value/id/ref collisions.**
Final built datasets: **iso 253, mh 298 (74/74 flat + 30×5 structured), ctx 963, rho 250 (116 subjects).**

## Run-phase fixes (grounded)

- **judge.py + exp07 parallelized**: sequential 4-model judge validation would take ~9h
  (frontier models ~8s/call × ~6400 items); exp07 rho ~10h. Both now use a thread pool
  over independent items (llm cache is thread-safe) — judge ~20 min, exp07 ~1.5h. exp04
  stays sequential (Mem0/Chroma is not concurrency-safe: transformers import race + SQLite
  single-writer). Cross-model κ made index-aligned so abstentions don't misalign pairs.
- **venv dependency drift**: `huggingface_hub` had been downgraded to 0.36.2 (missing
  `is_offline_mode`), breaking `transformers 5.10.2` → `sentence_transformers` → Mem0's
  embedder → all Mem0 experiments crashed on import. Restored the locked
  **`huggingface_hub==1.8.0`** (in requirements.lock); embedder loads again.

## Judge validation results (DONE, all 4 models)

Recovery gold n=351, entailment pairs n=1370; Wilson CIs + pairwise Cohen's κ.
- **Recovery false-accept** (the safety-critical error): gpt-4o-mini 2.06%, gpt-4o 0.52%,
  Sonnet 5 0.0%, GPT-5.5 0.0% — Sonnet 5 holds the 0 floor on the harder gold → reported
  leak rates stay conservative lower bounds. Recall 0.75/0.93/0.98/0.98.
- **Entailment miss-rate on MULTI-HOP true entailers = 0.0 for ALL 4 models** (recall
  94–100%) → the judge does **not** miss a multi-hop entailer (answers the "don't lose an
  entailer" concern); and the planner co-deletes by the exact DAG regardless.
- **Near-miss false-fire** (over-delete risk): gpt-4o-mini 0.757, gpt-4o 0.455, GPT-5.5 0.305,
  **Sonnet 5 0.034** — high false-fire is exactly why the planner uses the exact DAG, not
  the LLM-judge greedy.
- **Production judges (grounded):** the recovery **and** entailment scoring that produced
  every leak number is now the frontier model **`claude-sonnet-5`** (`config.JUDGE_MODEL` =
  `config.ENTAILMENT_JUDGE_MODEL` = `claude-sonnet-5`), validated on the expanded gold — **0%
  recovery false-accept, 3.4% entailment near-miss false-fire, 0 multi-hop miss**, best on
  every safety axis. The **pinned `gpt-4o-mini-2024-07-18` / `gpt-4o-2024-08-06`** numbers are
  retained as the **reproducibility anchor** (near-free — the 4-model validation already
  produces them; on the harder gold gpt-4o-mini's recovery false-accept rose to 2%). Sonnet 5
  has no dated snapshot (rolling alias), mitigated by the pinned anchor + recorded access date,
  and is also a panel self-adversary (H-01) — an accepted overlap, since **gold validation,
  not call-independence, is what certifies the judge**. This honors "switch to the best" with
  reproducibility handled by the anchor rather than by pinning the judge itself.

## Status

- [x] Requirements captured (this doc)
- [x] task 1 — boolean-DAG module + hard-topology generators (self-tests pass)
- [x] task 2 — validator gates + builders + ~250 scaling (build repro passes)
- [x] task 3 — DAG-aware exact planner + greedy/depth-first comparators (mock-tested)
- [x] task 4 — experiment wiring for new bases (exp04/exp11 bin_of, exp03 exact default)
- [x] task 5 — 4-model judge validation harness (351 recovery gold, 414+ entailment pairs,
      CIs + κ + miss-rate/recall, grounded judge selection) — CODE done; run pending
- [~] task 6 — author + gate to ~250 (GATE: PASS) — v3 running after fixing 3 gate issues
- [ ] task 7 — full battery re-run (4 reasoners + services); exp07 parallelized; exp08/09/10
      enlarged
- [ ] task 8 — propagate numbers + document
- [x] task 9 — exp12 planner minimality (greedy vs exact vs depth-first per topology)
