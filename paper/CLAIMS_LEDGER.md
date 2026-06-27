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
- **H:** naive single-record delete leaves the value in **97.9%** [Wilson 89.1,
  99.6] of isolated PII targets (n=48, exp01 = duplication incidence); residual
  **68.75%** [54.7, 80.1] (naive) **→ 0%** [0, 7.4] (artifact-aware), n=48 (exp02).
  ⚠ FRAMING MOVED: at n=48 the exp01 (97.9%) and exp02-naive (68.75%) rates
  **diverge and invert** vs the old 75% < 83% — separate Mem0 dedup draws, so the
  old "nested 9/12 ⊂ 10/12 same-targets" gloss no longer holds.
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
- **H (Mem0):** leak **bin1 100% / 94%** (stored-alone, n=17) / **bin2 59% / 65%**
  (stored+world, n=17), gpt-4o-mini / gpt-4o → **0% after co-delete** [CI 0, .18];
  ρ = 0%. (Now 17/17 per bin at n=34; was 1/5 at n=6, and leak no longer identical
  across reasoners — bin2 dropped from 80%.) **Ports to Letta (exp11, unchanged):**
  bin1 100%, bin2 80% (gpt-4o-mini) / 100% (gpt-4o) → **0% after co-delete**; ρ = 0%.
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
- **H:** **100% completeness [Wilson .90, 1.0], 0 spurious bystander deletions,
  mean collateral k = 0.912 [bootstrap .74, 1.09]** (operands spared by minimality
  = 36) — on the **full n=34** multi-hop set, gpt-4o entailment judge. (Was k=1.17,
  4 spared, at n=6.)
- **Ctrl:** bystanders must be **spared** (0 spurious is the selectivity test);
  result is **robust to entailment-judge choice** — re-run with gpt-4o entailment
  judge leaves k / spurious / completeness unchanged; backed by entailment
  near-miss validation (§ V2: gpt-4o **0%** vs gpt-4o-mini **41.7%** false-fire on
  partial operands → using gpt-4o is what keeps k from inflating).
- **Scope:** greedy heuristic for the NP-hard Opt-P2E2; "minimal" = co-deletes a
  *sufficient subset*, not a proven optimum.

### C5 — The parametric floor ρ is *measured* on a gradient; when ρ > τ, completeness cannot be certified even at residual = 0 *(the limit result)*
- **Support:** exp07.
- **H:** measured worst-adversary ρ on **n=49** facts: **27 certifiable (ρ≤τ) /
  8 contested-middle (τ<ρ<0.5) / 14 hard-floor (ρ≥0.5)** → **22 of 49 NOT
  certified-complete** (ρ>τ) at τ=0.1 despite residual=0 [certifiable 27/49=.551,
  Wilson .41–.68]; primary reasoner alone flags only 14/49. Authored-tier ρ means
  (mini/gpt-4o): low 0.00/0.00, mid 0.069/0.275, high 0.367/0.656. ⚠ LIMIT-RESULT
  MOVED: at n=49 the floor is **NOT cleanly bimodal** (8 facts in the middle), so
  the count is **τ-dependent** (22 at τ=0.1 → 14 at τ→0.5) — the old "sharply
  bimodal, τ-invariant 9/15" claim no longer holds; report as a gradient.
- **Ctrl:** ρ probe sees **world-context only** (never stored facts) → co-deletion
  *cannot* lower it; **2 reasoners**; **mid-tier numeric-tolerance sweep** (floor
  persists at all tolerances, magnitude is tolerance-dependent); **base-rate vs
  context-lift** split; **high-tier refusal audit** (7 high-tier facts drew refusals
  → ρ for sensitive attrs is an adversarial *lower* bound).
- **Scope:** ρ is reasoner-dependent (mid is the contested tier — why ≥ 2
  reasoners are mandatory). A COMPLETE certificate is "complete **modulo
  recovery-judge recall ≈ 78%**"; INCOMPLETE and aggregate numbers are safe lower
  bounds.

### C6 — Artifact-aware deletion restores membership-indistinguishability; at powered n≈60 naive's residual signal IS significant
- **Support:** exp08.
- **H:** retrieval-score MIA AUC (n=48 members, 2 twins/fact = 96 controls) —
  **intact 0.69** (p=.001, CI [.60,.78], excludes .5) · **naive 0.68** (p=.001,
  CI [.59,.77], **excludes .5 → NOW SIGNIFICANT**) · **artifact-aware 0.52**
  (p=.36, CI [.41,.62], includes .5).
- **Ctrl:** **n = 48 members + 96 matched near-twins (2/fact)**, bootstrap 95% CI +
  label-permutation p, **continuous** retrieval scores (no thresholding). The
  **intact arm is the power sanity** (p=.001 shows the test can detect a real
  signal); the **aware-arm CI includes .5** → indistinguishability restored.
- **Scope:** the earlier n = 6 "consolidation-trace survives artifact-aware" claim
  was an underpowered artifact and is **retracted**. ⚠ REVERSED at powered n≈60:
  naive deletion **now leaks a significant membership signal** (p=.001, was p=.065
  at n=33) — the old "not demonstrated to leak" guardrail no longer applies; only
  artifact-aware deletion restores indistinguishability.

### C7 — *(HOOK — sharpest instance, NOT the headline contribution)* Agent-mediated deletion is surface-incomplete
- **Support:** exp10 (Letta).
- **H:** explicit dual-surface "delete from core **and** archival" → **100%
  faithful**; a **vague but realistic** RTBF request ("I'm not comfortable with
  you keeping X") with the fact also in archival → agent calls `memory_replace`,
  scrubs **core**, never clears **archival** → **0% faithful / 100% archival
  residue / 0% core residue**.
- **Ctrl:** the **explicit-instruction baseline (100% faithful)** isolates the
  failure to *phrasing/surface coverage*, not to a missing capability; **n = 10**
  sensitive-PII targets (scaled from 3; the 0% / 100% / 0% result holds at n=10).
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
| **01** | Mem0 | naive-delete residual | **97.9%** [89,99.6] residual = dup incidence (n=48) | mechanism-tracked: top-1 delete leaves a copy iff duplicated |
| **02** | Mem0 | naive vs artifact-aware | **68.75% → 0%** [naive 55,80; aware 0,7.4] (n=48) | same facts, two strategies; +3.29 extra artifacts purged |
| **05** | Mem0 | duplication factorial | row-inflation **24–42%**, dup **30–39%** | **2×2** embedder×cadence; paraphrase ≥ byte-ID in all cells; GH issues |
| **06** | Mem0 | infer=True derivation-capture | **0% — REJECTED** | infer=False control: 0 captured ⇒ it was consolidation/merging, not derivation |
| **04** | Mem0 | re-derivation (operands-only) | bin1 **100%/94%** / bin2 **59%/65%** → **0%**; ρ 0% (n=17/bin) | target never stored (residual=0 by construction); 2 reasoners, binned |
| **03** | Mem0 | planner end-to-end | **100% / 0 spurious / k=0.912** [.74,1.09] (n=34) | spare-bystander test; robust to gpt-4o entailment judge |
| **07** | Mem0 | ρ gradient (measured) | ρ_max bins (n=49): **27 cert / 8 mid / 14 hard**; **22/49 not certifiable** (τ=0.1; 14/49 primary-only) | world-context-only probe; **NOT bimodal at n=49 → τ-dependent count** |
| **08** | Mem0 | membership inference | intact **.69** / naive **.68 (p=.001, SIG)** / aware **.52 (ns)** | n=48 members + 96 twins (2/fact), bootstrap CI + perm p; intact = power sanity |
| **judge** | — | judge validation | recovery **0% false-accept**; entail gpt-4o **0%** false-fire | gold-labelled set; 12 hard near-miss negatives |
| **09** | Graphiti | KG residue after `remove_episode` | edge **40%**, **KG/summary 80%** (n=10) | clean episode hard-delete verified; residue = stale summaries + shared-entity edges |
| **10** | Letta | agent-mediated deletion faithfulness | explicit **100%** vs vague **0% / 100% archival** (n=10) | explicit-instruction baseline isolates phrasing/surface, not capability |
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
| **dedup pipeline** | Mem0 (mem0ai 2.0.7, OSS + Chroma) | **duplication** — naive delete leaves copies | exp01/02/05 | 97.9% residual; 68.75%→0% aware (n=48); dup 30–39% across the full factorial |
| **bi-temporal KG** | Zep/Graphiti (graphiti-core 0.29.2 + Neo4j 5.26) | **stale entity/community summaries** (not recomputed on delete) | exp09 | clean `remove_episode` still leaves **80%** KG/summary residue (n=10) |
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
2. **Naive deletion DOES leak (MIA), at powered n≈60.** ⚠ UPDATED (was a
   guardrail): at n=48 members + 96 twins, naive AUC=.68, p=.001, CI excludes .5
   → significant (was borderline p=.065 at n=33). Naive deletion leaves a
   detectable membership signal; only artifact-aware deletion restores
   indistinguishability. *Web-planner: ratify reframing "not demonstrated" →
   "demonstrated leak."*
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

- **MIA power: DONE.** Expanded to n=48 members + 96 twins (2/fact); naive now
  crosses p<.05 (AUC .68, p=.001). The only quantitative gap is closed.
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

Re-run 2026-06-27 (Wave 2, enlarged data): `exp01_baseline_…055540Z` ·
`exp02_artifact_purge_…063355Z` · `exp03_planner_threshold_…064049Z` ·
`exp04_parametric_…064429Z` · `exp07_rho_gradient_…070725Z` · `exp08_mia_…071616Z` ·
`exp09_zep_kg_residual_…065448Z` · `exp10_letta_…064949Z`.
Not re-run (unchanged): `exp05_duplication_…093949Z` ·
`exp06_derivation_capture_…094753Z` · `judge_validation_…123729Z` ·
`exp11_letta_rederivation_…025647Z`
(all under `data/results/`; 6 Letta certs `cert-F04{0..5}-*` under
`data/results/certificates/`).
