# Deletion-Completeness — Claims & Results Ledger

**Purpose.** Every paper claim ↔ the experiment(s) that support it ↔ the headline
number ↔ **the control that backs it**. This is the anti-mismatch safety net: a
claim is only paper-eligible if its row names a control that rules out the obvious
confound. All numbers verified against `data/results/*.json` (timestamps in
§ Provenance), not from memory.

Stack (all runs): **local, no-sudo, pinned** — Mem0 OSS (`mem0ai 2.0.7`) + local
Chroma; Graphiti (`graphiti-core 0.29.2`) + Neo4j 5.26 (JDK21 tarball); Letta
(`letta 0.16.8`) + local Postgres 16.4 + pgvector. LLMs pinned:
`gpt-4o-mini-2024-07-18` (judge/primary reasoner) + `gpt-4o-2024-08-06` (second
reasoner / entailment). Embeddings: local `all-MiniLM-L6-v2`. Third-party
telemetry disabled. τ = 0.10.

---

## A. Claims ledger (one row per claim)

Claims are grouped by their role in the contribution (see § D). **H** = headline
number, **Ctrl** = the control that makes the claim defensible, **Scope** =
caveat / what it does *not* say.

### C1 — Recoverability decomposes into three orthogonal channels *(the framework)*
- **Claim:** post-"deletion" recoverability splits into **residual survival**
  (a surviving artifact still holds the value), **re-derivation** (entailed by
  surviving facts), and **parametric ρ** (knowable from the base model + world
  knowledge alone).
- **Support:** organizing framework; instantiated by exp02 (residual), exp04/11
  (re-derivation), exp07 (ρ).
- **H:** three channels measured by three separate probes with non-overlapping
  isolating controls.
- **Ctrl:** each channel is isolated so it cannot borrow signal from another —
  residual = exact-match on stored text; re-derivation = **operands-only**
  injection (residual = 0 by construction); ρ = **world-context-only** probe
  (never sees stored facts, so co-deletion cannot lower it).
- **Scope:** the *param-vs-memory* split alone is **not** claimed novel (Agentic
  Unlearning, 2602.17692, already separates backflow). Novelty is the
  **three-way** decomposition + the planner/certificate built on it.

### C2 — Naive deletion is residually incomplete because the store silently duplicates *(Mem0)*
- **Support:** exp01, exp02.
- **H:** naive single-record delete leaves the value in **75%** of isolated PII
  targets; residual **83% (naive) → 0% (artifact-aware)**.
- **Ctrl:** exp05 **2×2 factorial** (embedder MiniLM/OpenAI × cadence 0 s/1.5 s):
  row-inflation **24–42%**, duplication incidence **30–39%** in **all four**
  cells, and **paraphrase-variant duplicates ≥ byte-identical in every cell** →
  the duplication is a **semantic-dedup design limitation**, not our embedder and
  not an injection-timing race. Corroborated by Mem0 issues (#4896 hash-only
  dedup, #4573, #687).
- **Scope:** mechanism is Mem0-specific. Generalization is carried by the *other
  two families* (§ C); we do **not** claim all systems duplicate.

### C3 — At residual = 0, facts still re-derive from surviving operands; faithful co-deletion closes the channel
- **Support:** exp04 (Mem0), **exp11 (Letta)**.
- **H (Mem0):** leak **bin1 100%** (stored-alone) / **bin2 80%** (stored+world)
  → **0% after co-delete**; ρ = 0%. **Ports to Letta:** bin1 100%, bin2 80%
  (gpt-4o-mini) / 100% (gpt-4o) → **0% after co-delete**; ρ = 0%.
- **Ctrl:** **operands-only** control — target value never stored, so residual = 0
  by construction (verified with the **narrow `delete_value`**, not the broad
  `probe_value`, so an operand sharing a surface form is not miscounted); **≥ 2
  reasoners, binned and never aggregated**. On Letta the co-delete is the
  **direct, verified-faithful `passages.delete`** (by captured passage id):
  `faithful_codelete = 100%`, `bystanders_intact = 100%` → "re-derivation closed"
  is not confounded with "the delete silently didn't run" (keeps exp10 and exp11
  separate).
- **Scope:** re-derivation is **reasoner-dependent**; honest negative **F043**
  (CHS → Bishan: model won't make the leap). Recovery scored by a validated judge
  with **0% false-accept** (§ V1) ⇒ all leak rates are conservative lower bounds.

### C4 — A greedy co-deletion planner reaches completeness with minimal collateral, and emits a certificate
- **Support:** exp03.
- **H:** **100% completeness, 0 spurious bystander deletions, mean collateral
  k = 1.17** (operands spared by minimality = 4).
- **Ctrl:** bystanders must be **spared** (0 spurious is the selectivity test);
  result is **robust to entailment-judge choice** — re-run with gpt-4o entailment
  judge leaves k / spurious / completeness unchanged; backed by entailment
  near-miss validation (§ V2: gpt-4o **0%** vs gpt-4o-mini **41.7%** false-fire on
  partial operands → using gpt-4o is what keeps k from inflating).
- **Scope:** greedy heuristic for the NP-hard Opt-P2E2; "minimal" = co-deletes a
  *sufficient subset*, not a proven optimum.

### C5 — The parametric floor ρ is *measured* on a gradient; when ρ > τ, completeness cannot be certified even at residual = 0 *(the limit result)*
- **Support:** exp07.
- **H:** ρ by tier (gpt-4o-mini / gpt-4o): **low 0.00 / 0.00**, **mid 0.033 /
  0.633**, **high 0.833 / 1.00** — a monotone gradient. **6 of 15** certificates
  are **NOT** certified-complete (ρ > τ) despite residual = 0.
- **Ctrl:** ρ probe sees **world-context only** (never stored facts) → co-deletion
  *cannot* lower it; **2 reasoners**; **mid-tier numeric-tolerance sweep** (floor
  persists at all tolerances, magnitude is tolerance-dependent); **base-rate vs
  context-lift** split; **high-tier refusal audit** (R13 NSF→male: 5/6 refused on
  gpt-4o-mini → ρ for sensitive attrs is an adversarial *lower* bound).
- **Scope:** ρ is reasoner-dependent (mid is the contested tier — why ≥ 2
  reasoners are mandatory). A COMPLETE certificate is "complete **modulo
  recovery-judge recall ≈ 78%**"; INCOMPLETE and aggregate numbers are safe lower
  bounds.

### C6 — Artifact-aware deletion restores membership-indistinguishability; naive's residual signal is not significant at this n
- **Support:** exp08.
- **H:** retrieval-score MIA AUC — **intact 0.719** (p = .002, CI [.59, .84],
  excludes .5) · **naive 0.613** (p = .065, CI [.47, .74], **includes .5** → not
  significant) · **artifact-aware 0.514** (p = .44, CI [.38, .65], includes .5).
- **Ctrl:** **n = 33 members + 33 matched near-twins**, bootstrap 95% CI +
  label-permutation p, **continuous** retrieval scores (no thresholding). The
  **intact arm is the power sanity** (p = .002 shows the test can detect a real
  signal).
- **Scope:** the earlier n = 6 "consolidation-trace survives artifact-aware" claim
  was an underpowered artifact and is **retracted**. Naive = "**not demonstrated
  to leak** at this n," not "no leak"; a planned **n ≈ 60** (2nd matched control
  per fact) will test whether naive crosses p < .05.

### C7 — *(HOOK — sharpest instance, NOT the headline contribution)* Agent-mediated deletion is surface-incomplete
- **Support:** exp10 (Letta).
- **H:** explicit dual-surface "delete from core **and** archival" → **100%
  faithful**; a **vague but realistic** RTBF request ("I'm not comfortable with
  you keeping X") with the fact also in archival → agent calls `memory_replace`,
  scrubs **core**, never clears **archival** → **0% faithful / 100% archival
  residue / 0% core residue**.
- **Ctrl:** the **explicit-instruction baseline (100% faithful)** isolates the
  failure to *phrasing/surface coverage*, not to a missing capability; n = 3
  sensitive-PII targets.
- **Novelty (confirmed vs ForgetEval):** ForgetEval **deliberately bypassed
  Letta's agent loop** — "address archival-memory REST endpoints directly, keep the
  LLM out of the recall hot path." **We tested the agent loop they excluded**, so
  this finding is genuinely new — *not* refuted by "ForgetEval already showed
  deployed systems leak." Cite the bypass as the gap.
- **Scope:** still the **hook + sharpest *instance*** of the generalization, **not
  the headline contribution** — credit comes from C1/C4/C5 (decomposition +
  planner/certificate + measured ρ). Hook with the memorable finding, get credited
  for the novel framework (see § D, § E, § G).

### Validation claims (load-bearing for everything above)

- **V1 — Recovery judge makes all leak rates lower bounds.** exp `judge`:
  n = 17, **false-accept 0.0** (tp 7 / fp 0 / tn 8 / fn 2), κ = 0.767 vs gold,
  false-reject 0.222 (conservative — it *rejects* "≈SGD 3,142" for 3,200 and
  "she is vegetarian"). **Ctrl/use:** 0 false-accepts ⇒ every reported leak/recovery
  rate is a **conservative lower bound**.
- **V2 — Use gpt-4o as the entailment judge.** n = 24 (12 hard near-misses):
  gpt-4o **0%** false-fire on partial operands vs gpt-4o-mini **41.7%**;
  inter-judge κ falls **0.83 (trivial) → 0.455 (hard near-miss)**. **Ctrl/use:**
  the planner (C4) uses gpt-4o so collateral k is not inflated by false entailments.

---

## B. Per-experiment ledger (exp01–exp11)

| exp | system | measures | headline | control that backs it |
|---|---|---|---|---|
| **01** | Mem0 | naive-delete residual | **75%** residual (= dup incidence) | mechanism-tracked: top-1 delete leaves a copy iff duplicated |
| **02** | Mem0 | naive vs artifact-aware | **83% → 0%** | same facts, two strategies; +1.17 extra artifacts purged |
| **05** | Mem0 | duplication factorial | row-inflation **24–42%**, dup **30–39%** | **2×2** embedder×cadence; paraphrase ≥ byte-ID in all cells; GH issues |
| **06** | Mem0 | infer=True derivation-capture | **0% — REJECTED** | infer=False control: 0 captured ⇒ it was consolidation/merging, not derivation |
| **04** | Mem0 | re-derivation (operands-only) | bin1 **100%** / bin2 **80%** → **0%**; ρ 0% | target never stored (residual=0 by construction); 2 reasoners, binned |
| **03** | Mem0 | planner end-to-end | **100% / 0 spurious / k=1.17** | spare-bystander test; robust to gpt-4o entailment judge |
| **07** | Mem0 | ρ gradient (measured) | low 0/0, **mid .033/.633**, high **.833/1.0**; **6/15 not certifiable** | world-context-only probe (co-delete can't lower ρ); tol sweep; refusal audit |
| **08** | Mem0 | membership inference | intact **.719** / naive **.613 (ns)** / aware **.514** | n=33+33 twins, bootstrap CI + perm p, continuous scores; intact = power sanity |
| **judge** | — | judge validation | recovery **0% false-accept**; entail gpt-4o **0%** false-fire | gold-labelled set; 12 hard near-miss negatives |
| **09** | Graphiti | KG residue after `remove_episode` | edge **33%**, **summary 67%** | clean hard-delete verified first → residue is *stale summaries*, not edges |
| **10** | Letta | agent-mediated deletion faithfulness | explicit **100%** vs vague **0% / 100% archival** | explicit-instruction baseline isolates phrasing/surface, not capability |
| **11** | Letta | re-derivation + co-delete (ports) | bin1 **100%**, bin2 **80%/100%** → **0%**; ρ 0% | operands-only; **direct verified-faithful `passages.delete`** (faithful=100%, bystanders intact 100%) |

---

## C. Three-family convergence (the generalization evidence)

One phenomenon — **residual survival of a "deleted" fact** — reached in **three
architecture families by three different by-design mechanisms**. **System coverage
is NOT the novelty** (ForgetEval, arXiv 2606.15903, already benchmarks all three +
~10 more). The generalization claim is that a **strictly stronger,
causally-decomposed recoverability notion** (residual / re-derivation / parametric)
holds across these families — ForgetEval's *forget-command-leaves-top-k* check is
**necessary but not sufficient** for completeness, and our decomposition exposes
exactly what its check misses. Independent corroboration: ForgetEval's own
per-system notes name the *same mechanisms* (Graphiti "sheds surface forms /
synthesised fact string" = our stale summaries; Mem0 router "link-and-keep over
delete-old" = our duplication). See § G.

| family | system (version) | residual mechanism (by design) | evidence | headline |
|---|---|---|---|---|
| **dedup pipeline** | Mem0 (mem0ai 2.0.7, OSS + Chroma) | **duplication** — naive delete leaves copies | exp01/02/05 | 75% residual; 83%→0% aware; dup 30–39% across the full factorial |
| **bi-temporal KG** | Zep/Graphiti (graphiti-core 0.29.2 + Neo4j 5.26) | **stale entity/community summaries** (not recomputed on delete) | exp09 | clean `remove_episode` still leaves **67%** summary residue |
| **LLM-paging** | Letta/MemGPT (letta 0.16.8 + Postgres + pgvector) | **surface-incomplete agent-mediated deletion** (scrubs core, misses archival) | exp10/11 | vague forget: **0% faithful / 100% archival**; re-derivation **ports & closes** |

Empirical corrections folded in (premises that turned out wrong — keep, don't
re-assume): Graphiti `remove_episode` **hard-deletes** edges (clean) and a
contradiction did **not** invalidate the old edge → the channel is *summaries*, not
bi-temporal edge-invalidation. Letta is **Postgres-only** despite
`database_engine=SQLITE`.

---

## D. Narrative emphasis to encode (competitors read 2026-06-24; positioning in § G; skeleton structure returning from web session)

- **Abstract / Intro hook:** lead with **agent-mediated surface-incompleteness**
  (C7) — most memorable, most deployment-realistic, and **genuinely new** (it is
  the agent loop ForgetEval bypassed; § G). Hook with the memorable thing.
- **Claimed contribution (the novelty vs ForgetEval/ForgetAgent):** the
  **three-way recoverability decomposition (C1)** + **co-deletion planner &
  certificate (C4)** + **measured ρ floor / limit result (C5)**. Get credited for
  the novel thing.
- **Generalization claim — reframed:** *not* "first to cover these systems"
  (ForgetEval covers all three + ~10). It is a **strictly stronger,
  causally-decomposed recoverability notion** applied to the systems ForgetEval
  covers — its *forget-leaves-top-k* check is necessary but **not sufficient** for
  completeness. Three-family convergence = external validity for the stronger
  notion, not the contribution itself.
- **Letta agent finding (C7):** the **sharpest instance** of the generalization —
  **explicitly not** the headline contribution.

---

## E. Claims we deliberately do NOT make (reviewer-defense guardrails)

1. **No "derivation-capture" by the store.** exp06 rejected it (0%); the earlier
   "born 1991 → 35" was operand-row *consolidation*, not derivation.
2. **No "naive deletion leaks" (MIA).** Borderline non-significant (p = .065, CI
   includes .5). Say "not demonstrated at this n," never "leaks."
3. **No bi-temporal edge-invalidation in Graphiti.** The premise was empirically
   wrong; the residual is stale summaries.
4. **The Letta agent finding is not *the* contribution** — though it *is* a novel
   *finding* (the agent loop ForgetEval bypassed, § G). It is the hook/sharpest
   instance; credit for the contribution comes from C1/C4/C5.
5. **The param-vs-memory split is not claimed novel** (Agentic Unlearning backflow
   already separates it; and it assumes weight access — we are memory-store-only);
   the three-way decomposition + planner is.
6. **System coverage is not novel.** ForgetEval already benchmarks Mem0 + Graphiti
   + Letta (+ ~10 more). Never write "first to audit/benchmark these systems." The
   novelty is the **stronger, decomposed completeness notion**, not the system list.
7. **Our Mem0 numbers do not contradict ForgetEval's.** Theirs = forget-command
   success in top-k; ours = post-deletion recoverability by *any* channel.
   **Complementary** — state this explicitly wherever both appear.

---

## F. Open / pre-submission items

- **MIA power:** expand members 33 → ≈ 60 (2nd matched control per fact) to test
  whether naive crosses p < .05. Only quantitative gap.
- **Related-work positioning:** DONE — both read in full (2026-06-24), positioning
  encoded in § G + `REFERENCES.md`. Skeleton structure returning from web session.
- **Citations verified** (stop listing as open): 2507.00343 = "Meaningful Data
  Erasure in the Presence of Dependencies" (VLDB'25); 2604.00326 = "Inference-Aware
  & Privacy-Preserving Deletion in Databases" (cite by title, not "SeQureDB");
  2602.17692 = "Agentic Unlearning" (its backflow already covers the
  param+memory split — see C1 scope).

---

## G. Related-work positioning (both competitors read in full, 2026-06-24)

Three distinguished neighbours + the DB lineage. Full notes in `REFERENCES.md`.

- **ForgetEval** (arXiv **2606.15903**, MIT) — closest neighbour; benchmarks **all
  three of our systems + ~10 more** (Mem0 **68.3% / 43.6%**, Graphiti **7.0%**,
  Letta **65.5%**). **Different, weaker question:** *does a forget command leave the
  value in top-k retrieval* — **necessary but not sufficient** for completeness. We
  bring a **strictly stronger, causally-decomposed** notion to the same systems.
  - **Mem0-number trap:** their % = forget-command success in top-k; ours =
    post-deletion recoverability by *any* channel. **Complementary, not
    contradictory** — say so in-text.
  - **Agent-loop gap = what makes C7 novel:** ForgetEval **deliberately bypassed
    Letta's agent loop** ("address archival-memory REST endpoints directly, keep
    the LLM out of the recall hot path"). **We tested the loop they excluded.**
  - **Independent corroboration of convergence (§ C):** their per-system notes name
    our mechanisms — Graphiti "sheds surface forms / synthesised fact string" (=
    stale summaries, exp09); Mem0 router "link-and-keep over delete-old" (=
    duplication, exp01/05). External support, not contradiction.
- **ForgetAgent** (*IJRASET*) — a **synthetic unlearning *method*** (deletion
  receipts + counterfactual-indistinguishability). We are **deployed** systems, add
  **re-derivation + parametric** channels, and emit a **diagnostic certificate**
  (audit, not a method-with-guarantees). Neighbour, not overlap.
- **Agentic Unlearning** (2602.17692) — **weight-access** dual-pathway edit; **we
  are memory-store-only** (black-box base model). Its backflow already separates
  param+memory → we do **not** claim that split as novel (§ E.5).
- **P2E2 / SeQureDB** (2507.00343, 2604.00326) — **DB-theory lineage** for deletion
  under dependencies (formal completeness + co-deletion grounding). **The bridge
  none of the three agent-memory works make** — our planner operationalizes it on
  deployed agent memory.

---

## Provenance (result files this ledger is computed from)

`exp01_baseline_…082144Z` · `exp02_artifact_purge_…085402Z` ·
`exp03_planner_…125318Z` · `exp04_parametric_…094612Z` ·
`exp05_duplication_…093949Z` · `exp06_derivation_capture_…094753Z` ·
`exp07_rho_gradient_…111343Z` · `exp08_mia_…123822Z` ·
`judge_validation_…123729Z` · `exp09_zep_kg_residual_…131150Z` ·
`exp10_letta_…141526Z` · `exp11_letta_rederivation_…025647Z`
(all under `data/results/`; 6 Letta certs `cert-F04{0..5}-*` under
`data/results/certificates/`).
