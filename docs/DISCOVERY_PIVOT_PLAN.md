# Project Plan — Discovering Hidden Re-Derivation Paths in Agent Memory

*Working plan for the pivoted contribution. Written in plain language; every technical term is defined the first time it appears. Audience: us + advisor.*

---

## 1. The problem, in one paragraph

When a user asks an AI agent to **forget** a fact (say, their salary), deleting the one memory that stores it is not enough. The value can still be **re-derived** — reconstructed — from *other* memories that survived, sometimes combined with the model's general world knowledge. Example: even if we delete "Alice earns S$8,500," the store may still hold "Alice is a Senior SWE at Google Singapore," and the model *knows* such roles pay ~S$8,500. So the salary comes right back. To truly forget, we must also remove enough of those *surviving* memories that the value can no longer be reconstructed. The catch: **to know which memories to remove, we must first know how the value can be re-derived — and in a real deployed system, nobody tells us.**

## 2. What was wrong with our old version (the critique we're fixing)

Our current method **assumes we are handed a map** of how each fact can be re-derived (we call it the *entailment DAG* — a diagram of which memories, in which combinations, reconstruct the target). We wrote that map ourselves when we generated the test data. In real life, **that map does not exist** — discovering it *is* the hard problem. Solving the deletion once you have the map is easy and already-solved textbook stuff. So a reviewer rightly asks: "what did you actually contribute?"

## 3. Our new goal

> **Discover the hidden re-derivation map by probing the system from the outside, then delete the smallest set of memories that closes every path — and be honest about what we might have missed.**

Three pieces:

1. **Discovery.** Figure out, by experiment, which subsets of surviving memories can re-derive the target. This is the new, hard, publishable part.
2. **Co-deletion.** Given the discovered map, compute the smallest set of memories to remove so *no* path survives. (Easy — a known optimization problem; see §7.)
3. **Honest certificate.** Because discovery is done by finite probing, we might miss a path. We attach a **certificate** that quantifies this residual risk instead of pretending we found everything.

This directly answers the critique: the contribution is now the **discovery + honesty**, not the (trivial) optimization.

## 4. What is an "oracle"? (the key idea)

In computer science, an **oracle** is a black box you can ask a question and get an answer from — *without knowing how it works inside*. You don't open it up; you just query it.

**Our oracle answers exactly one kind of question:**

> "If the agent's memory contains *exactly* this set of facts `S` (plus its normal world knowledge), can an adversary get the target value back out — yes or no?"

We **implement** this oracle by actually doing it: we set the memory to contain `S`, then run an adversary (an LLM trying hard to recover the value) and check whether it succeeds. So:

- **One oracle query = one experiment = one (or a few) LLM calls.** Queries cost money and time — this is why we can't ask infinitely many.
- The oracle is **"black-box"** because we never look inside the model's weights. We only see: *input* (which memories are present) → *output* (recovered or not). This is exactly what a real-world auditor can do — which is a strength, not a limitation.
- The oracle is **"noisy"** because the LLM sometimes answers wrong: it may fail to recover something it *should* (a false "no"), or hallucinate a value it *shouldn't* have (a false "yes"). We handle noise by asking the same question several times and using the error rates we already measured for our judge.

Everything downstream is built on top of this one oracle. The whole research question is: **how do we recover the hidden structure using as few, and as reliable, oracle queries as possible?**

## 5. The core concepts (plain definitions)

- **Recovery / re-derivation.** The adversary reconstructs the target value from whatever it's given. Our oracle measures this.
- **World knowledge (fixed background).** What the model already knows about the world, independent of the store (e.g., "Senior SWEs at Google SG earn ~S$8,500"). We hold this **constant** and only vary which *stored memories* are present. A memory "counts" toward re-derivation only if it lifts recovery **above** what world knowledge alone gives. (We already measure this — we call it *context lift*.)
- **Monotone Boolean function.** A yes/no verdict `f(S)` over a set of memories `S`, with the property that **adding memories never hurts recovery** — if `S` recovers the target, any bigger set does too. This is the clean, tractable model we start from: it's what lets us *shrink* a recovering set to find the essential memories.
- **Minimal sufficient set (a "derivation path").** A *smallest* group of surviving memories that, together with world knowledge, re-derives the target — such that dropping any one of them breaks it. These are the things we must discover. There can be several (e.g., `{job title, pay band}` for salary, but also `{payslip photo}` on its own).
- **Hitting set / co-deletion.** Once we know all the paths, we delete a set of memories that "hits" (intersects) **every** path, so none survives. The **smallest** such set = minimum co-deletion = the least collateral damage.
- **Non-monotonicity (the important complication).** Real LLMs can violate the monotone rule: adding a memory can *reduce* recovery. Example: memory A = "Alice earns S$8,500" plus memory B = "Correction: that record was an error, disregard" → with both present, the model refuses to state the salary. Deleting the "masking" memory B would make the salary reappear. So **"currently unrecoverable" is not the same as "safely forgotten."** We must measure how often this happens and account for it.
- **Certificate + miss-bound.** A machine-readable record of what we did and a statistical guarantee such as: *"with probability ≥ 95%, we did not miss any re-derivation path of size ≤ k."* This turns "we think it's deleted" into "here's exactly how confident we are, and why."

## 6. The approach, step by step

For one target value we want to forget:

1. **Shortlist candidates — cheaply, with no LLM call per memory.** A real store can hold thousands of memories, and we do **not** send them all to the LLM. First we use the memory system's built-in **similarity/retrieval search** (embedding lookup — essentially free, no LLM per memory) to pull only the handful of memories related to the target. Thousands → tens. Only this small shortlist enters the expensive discovery step below. *Caveat:* if this cheap filter misses a memory that is actually part of a re-derivation path, we can't discover that path — this is one source of the "incomplete discovery" risk our certificate reports (§10, §12).
2. **Find one path (cheap).** Start from "all shortlisted memories present" (which recovers the target). Remove memories one at a time; if recovery still succeeds, keep the memory out; if it fails, put it back. What remains is **one minimal sufficient set** — one derivation path — found in roughly (number of candidates) oracle queries.
3. **Find the other paths (the hard part).** There can be several independent paths. We block the path(s) already found and re-run the search to surface a *new* one, repeating until no new path appears. (This "find-one, block-it, find-another" loop is a known technique from logic/SAT solving; we transfer it to our noisy black-box oracle.)
4. **Co-delete.** Feed the discovered paths to the solver, which returns the smallest set of memories that breaks every path (a hitting set, solved with ILP/MaxSAT — off-the-shelf).
5. **Verify.** Actually delete that set and re-probe: is the target now unrecoverable? Record pre- and post-deletion recovery.
6. **Certify.** Emit the certificate: the paths found, the memories deleted, the verification result, the oracle's measured error rates, and the **miss-bound** (our honest estimate of residual risk from paths we might not have probed, and from any non-monotone behavior we observed).

### 6a. Retrieval: how the cheap shortlist works (do we need embeddings?)

**Question: to run similarity search, must the memories already be stored as embeddings?** **No.**

- **Our three target systems already store embeddings** — that is how *they* do retrieval (Mem0 → Chroma, Zep/Graphiti → Neo4j, Letta → pgvector). We can simply query their existing index.
- **Even for a system that doesn't**, we can build the index ourselves at audit time: embedding a few thousand short memory texts with the local `all-MiniLM-L6-v2` takes seconds on our GPU and costs nothing.
- **BM25 needs no embeddings at all** — it is pure lexical (term-frequency) ranking over raw text.

The only hard requirement is **read access to the memory texts**, which our adapter interface already provides (`list_memories`, `memory_text`) and which our threat model already assumes.

**We use BM25 *and* embeddings together (hybrid), because they fail in opposite directions:**

| Filter | Catches | Misses |
|---|---|---|
| Embedding similarity | paraphrase ("compensation" ≈ "salary") | rare exact tokens — a bare number `8500`, a name, an ID |
| BM25 (lexical) | exact / rare tokens | paraphrase |

**Recall is what matters at this stage.** A memory missed by the cheap filter is a path we can *never* discover — it feeds directly into the "incomplete discovery" risk (§12). Over-including is cheap (the expensive stage prunes it); under-including is unrecoverable. So hybrid retrieval **directly reduces one of the two risks we have to quantify** — worth stating explicitly in the paper.

### 6b. The algorithm in pseudocode

```
# ---------- the one primitive everything is built on ----------
ORACLE(S, V):
    # "If memory holds exactly S (+ fixed world knowledge),
    #  can an adversary reconstruct V?"  ->  yes / no
    votes = []
    repeat n_samples times:
        answer = adversary_LLM(context = S, ask_for = V)
        votes.append( judge(answer, V) )      # our gold-validated judge
    return majority(votes)                     # cost: n_samples LLM calls


# ---------- Stage 1: cheap shortlist  (NO LLM) ----------
SHORTLIST(store, V, subject):
    queries = surface_forms(V) + [subject, attribute_of(V)]
    C = {}
    for q in queries:
        C = C ∪ BM25_topk(store, q)       # exact/rare: names, numbers, IDs
        C = C ∪ EMBED_topk(store, q)      # paraphrase: "compensation" ~ "salary"
    return C                               # tens, not thousands. Recall first.


# ---------- Stage 2: isolate ONE minimal leaking set ----------
SHRINK(S, V):
    # precondition: ORACLE(S, V) = yes
    for m in S:
        if ORACLE(S - {m}, V) == yes:
            S = S - {m}                    # m wasn't needed -> drop it
        # else: removing m stopped the leak -> m is required -> keep
    return S            # minimal: drop any member and it stops leaking


# ---------- Stage 3: find ALL paths (the discovery loop) ----------
DISCOVER(C, V):
    P = []                                 # paths found so far
    loop:
        D = MIN_HITTING_SET(P)             # ILP/MaxSAT: fewest memories breaking all known paths
        R = C - D                          # what survives if we deleted D  (MASK, don't really delete)
        if ORACLE(R, V) == no:
            break                          # D closes every leak we can find -> done
        p = SHRINK(R, V)                   # a NEW leak survives -> isolate it
        P.append(p)
    return P, D


# ---------- Stage 4: verify + certify ----------
AUDIT(store, V, subject):
    C    = SHORTLIST(store, V, subject)
    P, D = DISCOVER(C, V)
    really_delete(D)
    post = ORACLE(C - D, V)                # verify on the live store; expect "no"
    return CERTIFICATE(
        paths_found   = P,
        deleted       = D,  k = |D|,
        post_recovery = post,
        oracle_error  = validated_judge_rates(),
        miss_bound    = "P(missed a path of size <= k) <= delta",
        monotonicity  = violations_seen
    )
```

Three things to notice:

- **The solver sits *inside* the discovery loop.** Each round it proposes the current best deletion; we mask it and ask "does it *still* leak?" If yes, the surviving leak is a brand-new path. This is the classic **hitting-set duality** loop — and it is where ILP/MaxSAT actually earns its place (rather than being bolted onto an already-solved problem).
- **We mask, we don't delete, during discovery.** Nothing destructive happens until Stage 4. This is exactly Tan's "adding, removing or **masking** memories."
- **Non-monotonicity is detected, not assumed away.** `SHRINK` assumes removing a memory cannot turn a leak *on*. So whenever we observe `ORACLE(smaller set) = yes` while `ORACLE(bigger set) = no`, we have caught a **masking memory** — we log it as a violation. Counting these is itself one of the paper's findings (§12.2).

### 6c. What it costs

Per target, roughly `(#paths + 1) × |C| × n_samples` LLM calls. With `|C| = 20` candidates, 3 paths, and `n_samples = 4`, that is **~320 calls per target** — on the order of $0.30–$3 depending on the model. So **dozens of targets fit comfortably inside our budget**, which is precisely why the algorithm's *properties* are validated on the free synthetic oracle (Phase A, §8) and the real LLM is reserved for the small demonstration (Phase B).

## 7. Why the optimization is *not* the hard part

Step 4 (choosing the smallest memory set that breaks every path) is a classic **minimum hitting set** problem. It's NP-hard in theory but trivial at our scale, and solvable exactly with standard tools (ILP or MaxSAT). We already have an exact solver for it. **We deliberately do not claim novelty here** — the novelty is Steps 1–3 and 6 (discovering the paths and certifying honestly under a noisy, possibly non-monotone oracle).

## 8. How we run the experiments

Two phases, cheap-first:

### Phase A — Synthetic oracle (validate the *algorithm*, no API, no GPU)
We **invent** hidden re-derivation structures where we already know the true answer (we generate random monotone Boolean functions / path-sets of controlled size and shape). We let our discovery algorithm probe them, and we **inject noise** at the same error rates our real judge has. Because we know the ground truth, we can measure exactly:
- **Did it recover the true paths?** (precision / recall of discovered paths)
- **How many oracle queries did it need?** (cost)
- **How gracefully does it degrade** as structures get bigger or the oracle gets noisier?
- **Does the miss-bound hold?** (when we say "95% sure no path ≤ k was missed," is that actually true across many runs?)

This is fast, free, and repeatable — it's how we prove the method *works* before spending money.

### Phase B — Real LLM oracle (demonstrate on real systems, small but honest)
We run the same algorithm with a **real** LLM adversary as the oracle, on real memories inside real deployed systems (Mem0, Zep/Graphiti, Letta). Because oracle queries cost money, this eval is **small (dozens of targets)** — and that's defensible, because each target is genuinely expensive and we grade against ground truth. We measure:
- **Discovery accuracy** vs the known structure (see §9 — we already have an answer key).
- **Probe cost** per target.
- **How often monotonicity actually holds** (the non-monotonicity rate) — itself a finding.
- **Deletion correctness** — after deleting the discovered set, does the value truly stay gone?

## 9. What data we need

**Good news: mostly things we already have.**

| Need | Do we have it? | Notes |
|---|---|---|
| **Answer key** — facts with a *known* true re-derivation structure | ✅ Yes | Our 298 multi-hop facts already carry ground-truth paths. This becomes the **grading key** for discovery — we can measure "did we recover the true structure?" with **no new labeling.** This is the big feasibility win and it repurposes our "too small" dataset as a *structure-discovery benchmark*. |
| **Synthetic generator** — random path-structures with known answers + a noise knob | ⚠️ Build (small) | A few hundred lines, no API. Powers Phase A and lets us scale to sizes/shapes our real data can't reach. |
| **Memory systems** to probe | ✅ Yes | Existing Mem0 / Zep / Letta adapters (add / delete / control-what's-present). |
| **The oracle** — adversary + validated judge | ✅ Yes | Our four-model adversary panel + the gold-validated judge give the oracle *and* its measured error rates (the noise model). |
| **World-knowledge background** | ✅ Yes | Our ρ / context-lift machinery already separates "recoverable from the world alone" from "recoverable because of a stored memory." |
| **Cost/weight per memory** (for *weighted* hitting set) | ❌ No | We have no utility-loss data, so we start with uniform cost (every memory equal). Weighting stays optional/future work. |

**Bottom line on data:** the synthetic generator is the only real build; everything for the real-world demo already exists, and our existing dataset conveniently doubles as the ground-truth answer key.

## 10. What makes this a real contribution (positioning)

- **We must cite the closest prior art head-on** — "axiom pinpointing / justification finding" in formal logic already discovers minimal entailing sets and deletes via hitting sets *with a clean, exact reasoner*. We are **not** claiming that mechanism is new.
- **Our novelty is the transfer to a hard new setting:** a **noisy LLM oracle** over **natural-language memory** in **deployed agent systems**, with (a) a **certified miss-bound** for incomplete discovery and (b) a **characterization of non-monotone LLM behavior** — something formal-logic methods cannot have addressed, because formal entailment is always monotone.
- **The closest applied works assume the map; we recover it.** Recent agent-memory unlearning methods record or assume the dependency graph up front. We are the first (in this niche) to *discover* it from the outside.

*(Two prior-art areas are still being double-checked before we lock this in — see §12.)*

## 11. Timeline (abstract due 2026-07-21)

Because **07-21 is only the abstract deadline**, we lock the *framing* now and build the *method* in the week that follows:

- **Now → 07-21:** finalize this framing; write the abstract + title around discovery; run the remaining novelty check (§12).
- **Week after 07-21:** build the synthetic generator + discovery loop (Phase A), get the algorithm-works results.
- **Following days:** small real-LLM demo (Phase B) on the existing systems; write the certificate + miss-bound; assemble results.

## 12. Open risks we still need to close

1. **Two un-cleared prior-art areas** (next task, before committing the rewrite): (a) has anyone already learned a noisy Boolean recovery function via membership queries + an LLM oracle? (b) does the privacy literature ("can a deleted value still be inferred from remaining data?") already formalize our core question? If either is occupied, we adjust the framing.
2. **Non-monotonicity might be common.** If LLM recovery is frequently non-monotone, the clean shrink-based discovery needs guarding. Mitigation: measure the rate, scope the core guarantee to the monotone regime, and report non-monotone cases as a characterized limitation.
3. **Probe budget.** Real-LLM discovery is expensive; we keep the real eval small and lean on synthetic validation for scale.

---

### Quick glossary

- **Oracle** — black box we query "does memory set `S` re-derive the target? yes/no"; implemented as an adversary LLM probe; noisy and costly.
- **Path / minimal sufficient set** — a smallest group of memories that (with world knowledge) re-derives the target.
- **Co-deletion / hitting set** — smallest set of memories that breaks every path.
- **Monotone** — adding memories never reduces recovery (our starting assumption).
- **Non-monotone** — a memory can *suppress* recovery; deleting it can re-expose the value.
- **Miss-bound** — statistical guarantee on paths we might have failed to discover.
- **Context lift / world recall (ρ)** — how much a stored memory adds *beyond* what the model already infers from world knowledge.
