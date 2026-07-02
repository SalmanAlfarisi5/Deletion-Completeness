# Deletion-Completeness Codebase — Full Explanation

## 1. What This Project Is

This is a **research system** targeting AAAI 2027, studying **Right to Be Forgotten (RTBF)** in LLM-powered memory systems. The core question: *when a user asks a memory system to delete a fact, is it truly gone?*

The project discovers and proves that it often isn't — and builds a **planner + certificate** to close the gap.

---

## 2. The Problem: Three Ways a Deleted Fact Survives

After a memory system "deletes" a fact, the value may still be recoverable via three orthogonal channels:

```
                 DELETE fact F
                      │
        ┌─────────────┼──────────────┐
        ▼             ▼              ▼
  [1] Residual    [2] Re-derivation  [3] Parametric ρ
      Survival        Channel           Floor
        │                │                │
 Artifact still    Surviving facts    Base model
 physically holds  entail F (even     knows F from
 F's value         with residual=0)   world knowledge
        │                │                │
   Fix: purge       Fix: co-delete   No fix possible;
   all rows with    entailing facts   irreducible floor
   the value        (the planner)
```

The key insight: **naive deletion (remove the single surfaced record) only addresses the surface — not the derived artifacts or the re-derivation channel.**

---

## 3. Directory Layout and Component Roles

```
config.py            ← Global settings: API keys, models, thresholds
llm.py               ← Provider-agnostic LLM helper (OpenAI|Anthropic), cached

data/facts/
  isolated_facts.json      ← 12 PII facts with no entailment links (F001–F012)
  multi_hop_facts.json     ← 6 facts re-derivable from context facts (F040–F045)
  context_facts.json       ← Operand facts (entailing) + bystanders (must not be deleted)
  rho_gradient_facts.json  ← Facts tiered by world-knowability for rho measurement

systems/
  base.py            ← Abstract adapter ABC
  mem0_adapter.py    ← Mem0 (primary: local Chroma + LLM extraction)
  zep_adapter.py     ← Zep/Graphiti (secondary: local Neo4j, bi-temporal KG)
  letta_adapter.py   ← MemGPT/Letta (tertiary: agent-mediated, core blocks + archival)

pipeline/
  injector.py        ← Feed facts into a memory system as conversation turns
  deleter.py         ← Delete by ID, delete all rows with a value, naive top-1 delete

probes/
  exact_match.py       ← Scan all rows for the value's surface form (residual probe)
  paraphrase_probe.py  ← Generate N paraphrases, query system, check retrieval
  parametric_probe.py  ← Re-derivation AND parametric floor (rho) probe
  membership_inference.py ← AUC-based MIA via top-1 retrieval scores
  kg_node_residue.py   ← Graphiti: scan entity/community summaries for residue

planner/
  entailment_detector.py ← LLM-as-judge: does surviving_fact entail deleted_fact?
  optimizer.py           ← GreedyPlanner: 3-stage heuristic co-deletion

certificate/
  schema.py    ← Pydantic DeletionCertificate model
  emitter.py   ← make_certificate() + save_certificate()

evaluation/
  judge.py     ← Validate the recovery judge and entailment judge
  metrics.py   ← cohens_kappa, recoverability(), rate(), mean()
  recovery.py  ← Numeric parsing + refusal detection for answer scoring

experiments/
  exp01 → exp11  ← Progressive experiments (see §6)
```

---

## 4. The Three Target Memory Systems

All three expose the same abstract interface (`MemorySystemAdapter`), so the probe/planner/certificate stack is system-agnostic.

### Mem0 (Primary)
- OSS mode: local Chroma vector store + LLM extraction (Claude Haiku or GPT-4o-mini)
- **Key discovery:** Mem0 silently **duplicates facts** — semantic dedup by hashing misses paraphrase variants, so the same fact gets stored as 2–4 rows. Naive deletion of the top-1 surfaced record leaves behind duplicates.
- Deletion is content/search-based (not by `add()` IDs which lag).

### Zep/Graphiti (Secondary)
- Local Neo4j graph database, async + bi-temporal
- Stores facts as **episodes** → extracts **Entity nodes** + **RELATES_TO edges**
- **Key discovery:** `remove_episode` deletes the episode and its edges cleanly, but **entity and community summaries** generated during ingestion are NOT recomputed on deletion — the deleted fact persists in those summaries (stale KG residual by design).

### MemGPT/Letta (Tertiary)
- Local Postgres + pgvector, agent-mediated
- Two memory surfaces: **core memory blocks** (in-context, agent rewrites) + **archival vector store** (passages)
- **Key discovery:** A vague RTBF instruction makes the agent scrub the *core block* it's actively reasoning about but **silently misses archival passages** — surface-incomplete deletion.

---

## 5. The Probe Battery

Each probe answers: *"Can an adversary recover fact F from the current system state?"* — returning a score in [0, 1].

| Probe | What it checks | When it fires |
|---|---|---|
| `ExactMatchProbe` | Substring scan of all memory rows | Value's surface form physically present in any row |
| `ParaphraseProbe` | Retrieval with N paraphrased queries | Value appears in retrieval hits for semantically varied queries |
| `ParametricProbe.run_rederivation()` | Model given full surviving store, asked to reconstruct value | Surviving context facts entail the target |
| `ParametricProbe.run_parametric()` | Model given NO store, only subject's world-knowable context | Base model alone can infer the value |
| `ParametricProbe.estimate_rho()` | Stochastic sampling (n=8, temp=0.7) over world-context only | Measures empirical parametric floor ρ |
| `MembershipInferenceProbe` | AUC of top-1 retrieval score (member vs never-stored near-twin) | Signal leaks through retrieval similarity |
| `KGNodeResidueProbe` | Scan KG entity/community summaries + edges | Value in stale summaries or surviving edges |

**Scoring design:** answers use `Value: <answer>` format so reasoning text can't false-match. Numeric targets use relative tolerance (≤10%); categorical targets fall back to the LLM recovery judge. The judge is validated with 0% false-accept rate.

---

## 6. The Fact Datasets

### `isolated_facts.json` (F001–F012)
12 PII facts with **no entailment links** to any other stored fact. Examples:
- Alice Chen's emergency contact: `+65-9123-4567`
- Bob Tan's allergy: `penicillin`
- Carol Lim's wifi password: `RainbowTiger88`

Used to measure **residual survival** (the only recovery channel for isolated facts). Synthetic, so parametric ρ ≈ 0.

### `multi_hop_facts.json` (F040–F045)
6 facts that can be **reconstructed from combinations of context facts**, optionally plus world knowledge. Examples:
- F040: Alice's salary SGD 8,500 ← C001 (Senior SWE at Google SG) + C002 (Google SG SWE salary band 8k–9k). Basis: `stored` (co-deletion closes the channel completely).
- F041: Bob's age 35 ← C003 (born 1991) + world knowledge (current year). Basis: `stored+world` (parametric residual ρ remains after co-deletion).
- F042: Carol's elevated CVD risk ← C005 (LDL 195 mg/dL) + C006 (1-pack/day smoker) + medical world knowledge.

### `context_facts.json`
Two roles:
- **Entailing facts** (C001–C015): the operands that let multi-hop targets be re-derived. The planner must co-delete these.
- **Bystander facts**: innocent context that the planner must **never** touch (measures collateral damage).

### `rho_gradient_facts.json` (R01–R15)
Facts tiered by how recoverable they are from world knowledge alone:
- **Low tier**: arbitrary codes/secrets (locker PINs, wifi passwords) — expect ρ ≈ 0
- **Mid tier**: loosely constrained by occupation priors (occupation → income range) — expect ρ ≈ 0.3–0.6
- **High tier**: near-deterministic from context (driving licence → minimum age 18) — expect ρ ≈ 0.7–1.0

---

## 7. The Pipeline (Injection → Probing → Deletion)

### Injection (`pipeline/injector.py`)
Facts are fed as conversation turns:
```
User:      "By the way, please remember my emergency contact is +65-9123-4567."
Assistant: "Got it — I've noted that for you."
```
- `infer=True`: Mem0 extracts/consolidates facts (realistic, rewrites text)
- `infer=False`: store verbatim (controlled experiments with reliable fact→row maps)
- A 1.5s settle pause prevents Mem0's dedup race from creating measurement artifacts

### Deletion (`pipeline/deleter.py`)
Three deletion modes:
1. **Naive** (`delete_top_match`): delete the single record the system surfaces for the query — simulates a naive RTBF implementation
2. **Artifact-aware** (`delete_value_rows`): delete *every* row containing any surface form of the target value — fixes residual survival
3. **Direct** (`delete_records`): delete specific IDs — used by the planner for co-deletion

---

## 8. The Planner (Co-Deletion)

The planner solves **Opt-P2E2**: given that residual survival is zero, close the re-derivation channel with **minimal collateral** (fewest extra facts deleted). This is NP-hard in general; the codebase implements greedy heuristics.

### Entailment Detector (`planner/entailment_detector.py`)
LLM-as-judge: given surviving fact(s) and a deleted target, asks:
- **YES**: inferable with >80% confidence
- **PARTIAL**: right category but not exact value
- **NO**: no meaningful information

Returns a confidence score; cached by (surviving_text, target_text).

**Critical validation finding:** GPT-4o-mini false-fires on 42% of *partial* operand sets (e.g., just "Bob has a home loan" entailing the monthly payment). GPT-4o reduces this to 0%. The planner uses GPT-4o for entailment to avoid over-deleting bystanders.

### GreedyPlanner (`planner/optimizer.py`)
Three-stage `heuristic_threshold`:

```
Stage 1: Probe current recoverability
         if max(residual, rederiv) < τ (=0.10): done

Stage 2: Purge the target's own artifacts
         delete every row with the target's OWN value surface form
         re-probe; if complete: done

Stage 3: Co-delete entailing facts (greedy, confidence-descending)
         for each candidate sorted by entailment confidence (desc):
             if conf ≤ τ: stop
             delete that candidate's memory rows
             re-probe; if complete: stop
```

The planner distinguishes `delete_value` (narrow: the target's own surface forms, used in Stage 2) from `probe_value` (broad: includes approximations, used for re-derivation scoring). This prevents Stage 2 from accidentally deleting entailing operands whose text contains the target value only incidentally.

---

## 9. The Certificate

`certificate/schema.py` defines a Pydantic `DeletionCertificate` with:

| Field | Meaning |
|---|---|
| `residual_survival_score` | 0 = none survived, 1 = fully survived |
| `re_derivation_score` | 0 = not entailed, 1 = fully recoverable from store |
| `parametric_risk_rho` | Base model floor — irreducible |
| `final_recoverability` | `max(residual, rederiv, rho)` |
| `floor_reaching` | `max(residual, rederiv) < τ` — deletable channels closed |
| `completeness_certified` | `final < τ` — also passes the parametric floor |
| `status` | `COMPLETE` / `PARTIAL` / `INCOMPLETE` |
| `facts_co_deleted` | Which context facts the planner co-deleted |
| `collateral_k` | Number of co-deleted facts |

**The limit result:** `floor_reaching=True AND completeness_certified=False` means: the system is as erased as deletion can make it, but the base model can still recover the value from world knowledge alone. 6 of 15 rho-gradient facts hit this case.

---

## 10. The Experiments (exp01–exp11)

| Exp | Question | Key Result |
|---|---|---|
| **exp01** | How bad is naive (single-record) deletion? | **75% residual survival** — Mem0 duplicates facts silently |
| **exp02** | Does artifact-aware deletion fix residual survival? | **83% → 0%** residual |
| **exp03** | Can the planner close re-derivation with minimal collateral? | **100% completeness, 0 spurious bystanders, mean k=1.17** |
| **exp04** | Is re-derivation real? Does co-deletion close it? | bin1 (stored-only): 100% → 0%; bin2 (stored+world): 80% → 0%; ρ=0% |
| **exp05** | Is Mem0 duplication an embedder artifact or cadence artifact? | 2×2 factorial: 24–42% row-inflation in ALL cells → Mem0 design limitation |
| **exp06** | Does `infer=True` capture derivations? | 0% — `infer` does *consolidation* (merge rows), not derivation capture |
| **exp07** | What is the parametric floor ρ across fact tiers? | low=0.0, mid=0.03–0.63, high=0.83–1.0; 6/15 facts cannot be certified |
| **exp08** | Does deletion restore membership indistinguishability? | Artifact-aware: AUC 0.51, CI includes 0.5 → indistinguishable; Naive: AUC 0.61, p=0.07 (ns) |
| **exp09** | Does Zep/Graphiti have KG-residual after `remove_episode`? | Edge 33% clean, but **summary 67%** survives in stale entity/community summaries |
| **exp10** | Is Letta's agent-mediated deletion faithful? | Explicit dual-surface: 100% faithful; Vague RTBF: 0% faithful, 100% archival residue |
| **exp11** | Does the re-derivation channel / planner port to Letta? | Yes: same probe/certificate stack, same results as Mem0 |

---

## 11. The LLM Layer (`llm.py`)

All LLM calls go through a unified `chat()` function:
- Supports both OpenAI and Anthropic (routed by `LLM_PROVIDER`)
- **On-disk cache** keyed by `sha256(model + messages + params)` — makes re-runs free and deterministic
- `paraphrase(text, n)` generates N meaning-preserving rewrites for the paraphrase probe
- `value_twin(text)` generates a matched near-twin for membership inference (same template, different value)
- `embed(texts)` runs local SentenceTransformer (all-MiniLM-L6-v2) for similarity/retrieval

---

## 12. Evaluation Infrastructure

### Recovery Judge Validation (`evaluation/judge.py`)
- **Recovery judge** validated on 17 hand-labelled (fact, answer, gold) pairs — 0% false-accept rate (never says "recovered" when it wasn't)
- **Entailment judge** validated against hard near-miss negatives (insufficient operand sets): GPT-4o-mini 42% false-fire, GPT-4o 0%
- Cohen's kappa computed for inter-judge agreement

### Metrics (`evaluation/metrics.py`)
- `recoverability(residual, rederiv, rho)` = `max(...)` — worst-case across channels
- `cohens_kappa(a, b)` — returns `nan` when a rater is constant (correctly undefined, not 1.0)

### Numeric Recovery Scoring (`evaluation/recovery.py`)
- Parses numbers from answers (handles commas, SGD prefix, "k" suffix)
- Tolerance sweep: exact / 5% / 10% / 20% — lets rho be re-scored post-hoc without new LLM calls
- `looks_like_refusal()` — detects hedging answers ("I cannot", "UNKNOWN") that shouldn't count as recovery

---

## 13. Configuration (`config.py`)

Key knobs:

| Variable | Default | Role |
|---|---|---|
| `MEM0_MODE` | `oss` | `oss` (local) or `hosted` |
| `LLM_PROVIDER` | `anthropic` | `anthropic` or `openai` |
| `JUDGE_MODEL` | `claude-haiku-4-5-20251001` / `gpt-4o-mini-2024-07-18` | Recovery judge + primary reasoner |
| `SECOND_MODEL` | `gpt-4o-2024-08-06` | Second reasoner for agreement checks |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Local embeddings (GPU, free) |
| `TAU` | `0.10` | Recoverability threshold; below = "complete" |
| `ENTAILMENT_THRESHOLD` | `0.50` | Min confidence to draw an ENTAILS edge |
| `INJECT_SETTLE_SECONDS` | `1.5` | Pause between injections to prevent Mem0 dedup race |

---

## 14. The Paper Narrative (in plain English)

The paper argues the following chain:

1. **Three systems, one phenomenon.** Residual survival appears in all three LLM memory architectures by *different mechanisms*:
   - Mem0: **dedup failure** (paraphrase variants of the same fact get separate rows)
   - Graphiti: **stale summaries** (bi-temporal KG regenerates summaries on add, not on delete)
   - Letta: **surface-incomplete agent-mediated deletion** (agent scrubs core, misses archival)

2. **Artifact-aware deletion fixes residual survival** (83% → 0%) but opens the re-derivation question.

3. **Re-derivation is real, binned, and two-reasoner.** With residual=0, multi-hop facts remain recoverable. It's binned by mechanism (stored-alone vs. stored+world) and verified on ≥2 reasoner models so the result isn't model-specific.

4. **The planner closes re-derivation with minimal collateral.** Greedy threshold heuristic achieves 100% completeness, 0 spurious deletions, average 1.17 extra facts deleted per target.

5. **The parametric floor is the hard limit.** Some facts (high-tier: driving licence → must be ≥18) can never be certified complete because the base model infers them from world knowledge alone. 6/15 rho-gradient facts hit this limit, producing `floor_reaching=True, completeness_certified=False` certificates.

6. **Membership inference confirms artifact-aware deletion restores privacy.** After artifact-aware deletion, AUC=0.51 with CI including 0.5 — the system can no longer distinguish whether the fact was ever stored.

---

## 15. How Everything Connects (Data Flow)

```
Facts (JSON)
    │
    ▼ Injector
Memory System (Mem0 / Zep / Letta)
    │                          │
    ▼ list_memories            ▼ list_graph()
Derived rows                KG nodes/edges
    │
    ▼ Probes
ProbeResults (residual / rederiv / parametric / MIA / KG)
    │
    ▼ GreedyPlanner (EntailmentDetector)
PlanResult (artifacts_purged, facts_co_deleted, collateral_k)
    │
    ▼ Certificate Emitter
DeletionCertificate (JSON + human-readable text)
    {status: COMPLETE|PARTIAL|INCOMPLETE,
     floor_reaching, completeness_certified,
     residual/rederiv/rho scores}
```

Every experiment follows this pipeline. The adapter swap is the only change needed to test a new system — the rest of the stack is system-agnostic.
