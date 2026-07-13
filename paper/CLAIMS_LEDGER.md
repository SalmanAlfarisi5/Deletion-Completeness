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
- **H:** naive single-record delete leaves the value in **97.2%** [Wilson 94.4,
  98.7] of isolated PII targets (n=253, exp01); residual **97.2%**
  [94.4, 98.7] (naive) **→ 0%** [0, 1.5] (artifact-aware), n=253 (exp02).
  Isolated facts carry globally-distinct probe values (cross-fact uniqueness gate,
  now auto-enforced by `dedup_isolated`), so exp02's naive arm is not
  self-contaminated; at the enlarged **n=253** the two naive arms **coincide at
  97.2%** (two independent stochastic-dedup draws).
- **Ctrl:** exp05 **2×2 factorial** (embedder MiniLM/OpenAI × cadence 0 s/1.5 s):
  value duplication in **all four** cells, with **both byte-identical and
  paraphrase-variant duplicates present in every cell** (mixed dominance), and
  **80–82%** duplication incidence over corpus-unique facts (row-inflation
  ×1.75–1.82) → a **semantic-dedup design limitation**, not our embedder
  and not an injection-timing race. Corroborated by Mem0 issues (#4896 hash-only
  dedup, #4573, #687).
- **Scope:** mechanism is Mem0-specific. Generalization is carried by the *other
  two families* (§ C); we do **not** claim all systems duplicate.

### C3 — At residual = 0, facts still re-derive from surviving operands; faithful co-deletion closes the channel
- **Support:** exp04 (Mem0), **exp11 (Letta)**.
- **H (Mem0):** leak **bin1 .97–1.0** (stored-alone, n=74) / **bin2 .62/.72/.68/.66**
  (stored+world, n=74) across the **4-reasoner adversary set** (gpt-4o-mini / gpt-4o /
  Sonnet 5 / GPT-5.5) → **0% after co-delete** [CI 0, .05]; ρ = 0%. **The worst
  re-deriver is gpt-4o (.72), not the frontier models** (Sonnet 5 .68, GPT-5.5 .66) —
  the certificate is built for whichever reasoner is worst per fact. **NEW multi-level set** (join depth-2 + chain
  depth-3, n=12 each): **1.0 re-derivation → 0% after co-delete**, ρ=0 — the target's
  direct entailers are themselves unstored, so co-deletion must recurse to the stored
  roots. **Ports to Letta (exp11):** bin1 100%, bin2 **.59–.65** (4 reasoners, n=40) → 0%
  after co-delete; faithful direct `passages.delete` = 100%, bystanders intact = 100%.
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

### C4 — An exact minimal co-deletion planner reaches completeness with minimal collateral, and emits a certificate
- **Support:** exp03, exp12.
- **H:** **100% completeness [Wilson .96, 1.0], 0 spurious bystander deletions,
  exact mean collateral k = 1.04** (min-hitting-set over the entailment DAG, measured
  optimality gap ≈0 vs the ground-truth optimum k*; greedy threshold k=1.10 / 0 spurious;
  depth-first k=6.18 / 1116 spurious, exp12) — on the **full n=298** multi-hop set (incl.
  the 5 hard topologies), gpt-4o entailment judge; **466 operands spared** by minimality.
- **Ctrl:** bystanders must be **spared** (0 spurious is the selectivity test); the
  method is **structurally decoupled from the entailment judge** — the exact planner
  co-deletes over the *known* entailment DAG (recursing to stored roots), so a judge's
  false-fire cannot inflate k. The judge only orders the *greedy comparators*; V2 shows
  every model has a **0% multi-hop miss-rate** (never loses a true entailer) and gpt-4o
  is the lowest-false-fire reproducible snapshot used for those comparators.
- **Scope:** the dependency graphs are small, so Opt-P2E2 (NP-hard in general) is solved
  **exactly**; "minimal" = a proven minimum hitting set (gap ≈0 vs k* per exp12), not just
  a sufficient subset.

### C5 — The parametric floor ρ is *measured* on a gradient; when ρ > τ, completeness cannot be certified even at residual = 0 *(the limit result)*
- **Support:** exp07.
- **H:** measured worst-adversary ρ (sup over **4 reasoners**: gpt-4o-mini, gpt-4o,
  Sonnet 5, GPT-5.5) on **n=250** facts: **166 certifiable (ρ≤τ) / 42 contested-middle
  (τ<ρ<0.5) / 42 hard-floor (ρ≥0.5)** → **84 of 250 NOT certified-complete** (ρ>τ) at
  τ=0.1 despite residual=0 [certifiable 166/250=.66, Wilson .60–.72]. ⚠ The floor is a
  **τ-dependent GRADIENT, not bimodal** (42 facts in the contested middle; 74/250
  authored-tier vs measured-band mismatch). NUANCE (frontier safety filters): GPT-5.5
  and Sonnet 5 **refuse sensitive high-tier ρ facts** (NSF→sex, licence→age; **29
  refusal flags, all high-tier — verified no rate-limit contamination**) → their
  measured ρ there is a refusal-based **lower bound**, so the worst-adversary
  high-tier ρ is set by gpt-4o (which refuses less).
- **Ctrl:** ρ probe sees **world-context only** (never stored facts) → co-deletion
  *cannot* lower it; **4-reasoner panel** (open + frontier); **mid-tier
  numeric-tolerance sweep** (floor persists at all tolerances, magnitude is
  tolerance-dependent); **base-rate vs context-lift** split; **high-tier refusal
  audit** (20 refusal flags; GPT-5.5/Sonnet 5 refuse sensitive attrs → ρ there is an
  adversarial *lower* bound).
- **Scope:** ρ is reasoner-dependent (mid is the contested tier — why ≥ 2
  reasoners are mandatory). A COMPLETE certificate is "complete **modulo
  recovery-judge recall ≈ 78%**"; INCOMPLETE and aggregate numbers are safe lower
  bounds.

### C6 — Artifact-aware deletion restores membership-indistinguishability; at powered n≈60 naive's residual signal IS significant
- **Support:** exp08.
- **H:** retrieval-score MIA AUC (n=253 members, 3 twins/fact = 759 controls) —
  **intact 0.66** (p=.001, CI [.637,.688], excludes .5) · **naive 0.66** (p=.001,
  CI [.637,.687], **excludes .5 → SIGNIFICANT**) · **artifact-aware 0.51**
  (p=.04, CI [.498,.523], includes .5 → indistinguishable).
- **Ctrl:** **n = 253 members + 759 matched near-twins (3/fact)**, bootstrap 95% CI +
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

- **V1 — Recovery judge makes leak rates near-lower-bounds.** exp `judge`, validated
  across **all 4 models on n=229 gold** (90 pos / 139 neg): false-accept
  **gpt-4o-mini .0072 (1/139)**, gpt-4o .0072 (1/139), **Sonnet 5 0**, GPT-5.5 0;
  recall .72 / .91 / .98 / .97; κ vs gold .75 / .92 / .98 / .97. Production judge =
  the pinned **gpt-4o-mini** backbone (Sonnet 5's 0 false-accept reported as
  corroboration, but it's a rolling alias). **Ctrl/use:** the ≤0.72% false-accept
  means every reported leak/recovery rate is a **lower bound to within that margin**
  (95% Wilson upper ≈ .04) — not literally 0, stated honestly in the paper's Limitations.
- **V2 — gpt-4o is the entailment judge (reproducible snapshot).** Validated on
  **n=1370 pairs** across all 4 models. **Safety-critical result: multi-hop miss-rate
  = 0 for ALL four models** (recall_multihop = 1.0; per-topology recall 100% on
  chain/join/or_and/diamond/threshold) — no model ever *loses* a true entailer. On
  near-miss negatives (partial operands) false-fire diverges: **gpt-4o-mini 76% /
  gpt-4o 45% / GPT-5.5 30% / Sonnet 5 3.4%**. Production judge = **gpt-4o** (lowest
  false-fire among *reproducible dated snapshots*; Sonnet 5 is best overall but a
  rolling alias). **Ctrl/use:** the exact planner co-deletes over the *known* DAG, not
  this judge, so its 45% near-miss false-fire never inflates k; the judge only orders
  the greedy comparators. Inter-model κ (entailment): .26–.63, i.e. the near-miss
  boundary is genuinely hard, which is exactly why the method does not rely on it.

---

## B. Per-experiment ledger (exp01–exp11)

| exp | system | measures | headline | control that backs it |
|---|---|---|---|---|
| **01** | Mem0 | naive-delete residual | **97.2%** [94.4,98.7] residual (n=253) | mechanism-tracked: top-1 delete leaves a copy iff duplicated |
| **02** | Mem0 | naive vs artifact-aware | **97.2% → 0%** [naive 94.4,98.7; aware 0,1.5] (n=253) | same facts, two strategies; uniqueness auto-enforced (dedup_isolated) |
| **05** | Mem0 | duplication factorial | dup **80–82%** over corpus-unique facts (row-inflation +174–182%) | **2×2** embedder×cadence; byte+paraphrase both present (mixed dominance); GH issues |
| **06** | Mem0 | infer=True derivation-capture | **0% — REJECTED** | infer=False control: 0 captured ⇒ it was consolidation/merging, not derivation |
| **04** | Mem0 | re-derivation (operands-only) | bin1 97–100% / bin2 **.62/.72/.68/.66** (4 reasoners) → **0%**; **5 topologies (join/chain/or_and/diamond/threshold) 100%→0%**; ρ 0% (n=74/flat bin; 30/topology) | residual=0 by construction; **4-reasoner sup_A**, binned; worst bin2 = gpt-4o (.72), not frontier |
| **03** | Mem0 | planner (exact / greedy / depth) | **exact 100% / 0 spurious / k=1.04** (gap≈0, n=298); threshold k=1.10 / 0 spurious; depth-first k=6.18 / 1116 spurious | min-hitting-set over the entailment DAG; **466 spared**; provably minimal (exp12) |
| **07** | Mem0 | ρ gradient (measured, 4 reasoners) | ρ_max bins (n=250): **166 cert / 42 mid / 42 hard**; **84/250 not certifiable** (τ=0.1) | world-context-only probe; **τ-dependent gradient**; frontier REFUSE sensitive high-tier (29 flags, high-tier only ✓) → their ρ is a lower bound |
| **08** | Mem0 | membership inference | intact **.66** / naive **.66 (p=.001, SIG)** / aware **.51 (p=.04)** | n=253 members + 759 twins (3/fact), bootstrap CI + perm p; intact = power sanity |
| **judge** | — | judge validation (4 models) | recovery false-accept **.0072** (gpt-4o-mini/gpt-4o 1/139; Sonnet5/GPT-5.5 0); entail **0% multi-hop miss-rate all 4 models**; near-miss false-fire mini 76% / gpt-4o 45% / GPT-5.5 30% / Sonnet5 3.4% | **n=229 recovery gold / 1370 entailment pairs**; production: recovery gpt-4o-mini, entail gpt-4o (pinned snapshots) |
| **09** | Graphiti | KG residue after `remove_episode` | edge **20%**, **KG/summary 83%** (n=30) | clean episode hard-delete verified; residue = stale summaries + shared-entity edges |
| **10** | Letta | agent-mediated deletion faithfulness | vague **0% faithful / 100% archival** / 13% core (n=30) | explicit-instruction baseline isolates phrasing/surface, not capability |
| **11** | Letta | re-derivation + co-delete (ports) | bin1 **100%**, bin2 **.59–.65** (4 reasoners) → **0%**; ρ 0% (n=40) | operands-only; 4-reasoner sup_A; **direct verified-faithful `passages.delete`** |

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
| **dedup pipeline** | Mem0 (mem0ai 2.0.7, OSS + Chroma) | **duplication** — naive delete leaves copies | exp01/02/05 | 97.2% residual; 97.2%→0% aware (n=253); dup 80–82% over corpus-unique facts |
| **bi-temporal KG** | Zep/Graphiti (graphiti-core 0.29.2 + Neo4j 5.26) | **stale entity/community summaries** (not recomputed on delete) | exp09 | clean `remove_episode` still leaves **83%** KG/summary residue (n=30) |
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

**3× expansion wave 2026-07-12/13 (CURRENT; supersedes the 2026-07-04 wave below).**
Same 4-reasoner adversary panel (gpt-4o-mini, gpt-4o, Claude Sonnet 5, GPT-5.5);
enlarged datasets **iso253 / mh298 / ctx963 / rho250**; 5 hard multi-hop topologies
(join/chain/or_and/diamond/threshold) with a boolean **entailment DAG**; exact
min-hitting-set planner (+ greedy/depth-first comparators, new `exp12`); 4-model judge
validation (229 recovery gold, 1{,}370 entailment pairs). rho/re-derivation re-run with
`probes/parametric_probe` hardened so a rate-limit is never miscounted as a refusal
(correct by construction); verified by `evaluation/verify_wave.py` (rho refusals high-tier
only, 0 measurement errors, all post-co-delete re-derivation = 0). Files under
`data/results/` with `...20260712T...` / `...20260713T...` timestamps (exp01/02/03×3/04/
05/07/08/12 + judge_validation; exp09/10/11 from the cross-system phase). exp06 unchanged
(rejected negative). See `docs/RESULTS_3X_WAVE.md`.

Prior wave, retained for history --- Frontier re-run 2026-07-04 (4-reasoner adversary
panel: gpt-4o-mini, gpt-4o,
Claude Sonnet 5, GPT-5.5; enlarged datasets iso84 / mh92 / ctx299 / rho81).
Files under `data/results/` (all `...20260704T...`): `exp01_baseline_...101314Z`,
`exp02_artifact_purge_...104137Z`, `exp03_planner_threshold_...122021Z` +
`..._depth_first_...122209Z`, `exp04_parametric_...124800Z`,
`exp05_duplication_...121335Z`, `exp07_rho_gradient_...175621Z`,
`exp08_mia_...145340Z`, `exp09_zep_kg_residual_...180151Z`,
`exp10_letta_...180332Z`, `exp11_letta_rederivation_...185726Z`,
`judge_validation_...094056Z`. Not re-run (rejected negative, unchanged):
`exp06_derivation_capture_...094753Z` (2026-06-23). Certificates under
`data/results/certificates/`. Superseded pre-2026-07-04 result files were pruned
(recoverable from git history).

Judge frontier cross-check 2026-07-05 (`judge_validation_...102620Z.json`,
`evaluation/judge.py --frontier`): adds GPT-5.5 as a corroborating THIRD judge
(recovery κ=1.0 vs gold, 17/17, 0 false-accept; entailment 25% curated false-fire,
κ(gpt-5.5,gpt-4o)=0.66) and refreshes the entailment validation stats to the
enlarged corpus (426 pairs / 242 near-miss negatives, replacing the pre-expansion
146/78). Production judges unchanged: pinned gpt-4o-mini (recovery) / gpt-4o
(entailment). GPT-5.5 stays corroboration-only (rolling alias + panel adversary).
