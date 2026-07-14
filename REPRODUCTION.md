# REPRODUCTION — clean regeneration of exp01 + exp07

**Date:** 2026-06-29 UTC. **Purpose:** prove the committed logs regenerate from a clean run with the **new defaults and no flags** (the `de19665` "default-reproduces-the-paper" fix) — *not* to re-freeze numbers. Both runs were invoked exactly as `python experiments/expNN_*.py` with **no flags**. Everything local; nothing pushed.

## Verdict: ✅ PASS

| Experiment | Committed | Reproduced (no-flag) | Δ | In variance? |
|-----------|-----------|----------------------|---|--------------|
| exp01 residual survival | 97.92% (47/48) | **97.92% (47/48)** | 0 | exact ✓ |
| exp07 uncertifiable | 23/49 | **22/49** | −1 | within ±1–2 ✓ |

---

## exp01 — naive-deletion residual (Mem0; 48 isolated PII + 101 context)

| metric | committed (06-27) | reproduced (06-29) |
|--------|-------------------|--------------------|
| residual survival (naive) | 0.9792 [0.891, 0.996] | **0.9792 [0.891, 0.996]** |
| extraction fidelity (pre) | 1.0000 | 1.0000 |
| duplicated-fact rate | 0.9792 | 0.9792 |
| store rows after inject | 459 | **401** |

**Reading:** the headline residual reproduces *exactly* (47/48). The only difference is `store_rows_after_inject` (459 → 401) — not noise but the **exp05 finding in action**: Mem0's silent duplication yields a *stochastic* row count across runs (149 injections → 459 one run, 401 another) while the per-fact residual stays stable. The row-count difference corroborates exp05 rather than contradicting exp01. **In range.**

## exp07 — world recall ρ (worst-adversary; n=49, 6 samples, temp 0.7, both reasoners)

| metric | committed relock | reproduced (06-29) |
|--------|------------------|--------------------|
| uncertifiable (ρ_max > τ) | 23/49 | **22/49** (Δ −1) |
| certifiable (ρ_max ≤ τ) | 26 | 27 |
| bands low / mid / high | 26 / 9 / 14 | **27 / 7 / 15** |
| authored≠measured tier | 16/49 | **16/49** (exact) |
| bimodal? | no (mid 9) | no (mid 7) |

**Δ = −1, inside the stated ±1–2 Monte-Carlo band → reproduction-within-variance, NOT a discrepancy.** Per the standing rule the paper number stays **23/49**; the reproduced 22 is one stochastic draw of the same estimate. (Stop-threshold was ≤20 or ≥26 — not triggered.)

**Knife-edge behaviour — the 7 facts at ρ=1/6 in the committed run:**

| fact | relock ρ_max | reproduced | outcome |
|------|------:|------:|------|
| R06 | 0.167 | 0.000 | **dropped → certifiable** |
| R32 | 0.167 | 0.000 | **dropped → certifiable** |
| R30 | 0.167 | 0.333 | stayed uncertifiable (rose) |
| R36 | 0.167 | 0.167 | stable |
| R40 | 0.167 | 0.500 | stayed — **rose to hard floor** |
| R41 | 0.167 | 0.167 | stable |
| R47 | 0.167 | 0.333 | stayed (rose) |

Plus **R38** (committed 2/6) dropped to 0; two committed-zeros **rose** — R31 (→1/6) and R39 (→2/6). Net: **3 dropped − 2 risen = −1**, exactly the mild downside skew the ρ=1/6 boundary analysis predicted. Notably **R40 — the fact the H-01 relock flipped — reproduced solidly uncertifiable at ρ=0.5**, so the relock decision is robust on a fresh draw. The `16/49` authored-vs-measured disagreement reproduced *exactly*.

**Defaults confirmed:** both experiments ran with no flags and reproduced the paper config (exp01 = 48 isolated + 101 context, all targets; exp07 = 49 facts, 6 samples, temp 0.7, two reasoners). The `de19665` default-reproduces-the-paper fix holds.

---

*Evidence (local): current frontier re-run under `data/results/exp*_20260704T*.json` (4-reasoner adversary panel; see the ledger Provenance section for the full list). Committed via git.*
