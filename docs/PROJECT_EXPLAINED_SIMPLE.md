# The Whole Project, Explained Simply

*A plain-language walkthrough of the Deletion-Completeness project — written for
someone who knows nothing about it. Read this once and you will understand the
entire project: the problem, the idea, what we built, every experiment, and every
number. Everything here is grounded in the actual code and the paper.*

> **⚠ Updated for the 3× wave (2026-07-13).** Since this was first written, the project
> was expanded ~3×: datasets are now **253 isolated / 298 multi-hop / 963 context / 250
> rho**; the multi-hop set adds **5 harder entailment topologies** (join, chain,
> *disjunctive* `((A∨B)∧C)`, diamond, *threshold* "≥k of n"); the planner is now an
> **exact minimum-hitting-set solver over a boolean entailment DAG** (provably minimal,
> never misses a multi-hop entailer), with the old greedy + a depth-first pass kept as
> comparators (new experiment **exp12**); and the LLM judges are validated across **all 4
> models**. **For the current, verified headline numbers see `docs/RESULTS_3X_WAVE.md`**
> (authoritative). The numbers throughout the body below are the earlier wave and are
> superseded by `RESULTS_3X_WAVE.md` — the *ideas* and *structure* (the three channels,
> the two tools, the limit result) are unchanged. Key current numbers: residual
> **97.2%→0%**, planner **exact k=1.04 / 0
> spurious** (depth-first over-deletes 6× / 1116 spurious), rho **84/250 uncertifiable**,
> MIA intact/naive/aware **.66/.66/.51**, judge **0 multi-hop miss-rate across all 4
> models**, cross-system Graphiti **83%** summary residue / Letta **0% faithful / 100%
> archival**.

> **How to use this document.** Read it top to bottom. Sections 1–5 are the story
> (the "why" and the "big idea"). Sections 6–9 are the machinery (what we built).
> Section 10 is every experiment and its result. Sections 11–13 are reference
> material: a numbers cheat-sheet, a plain-English glossary, and a map of the code.
> Section 14 is the paper's argument in order — use that when you sit down to
> re-write the paper.

---

## Table of Contents

1. [The one-paragraph summary](#1-the-one-paragraph-summary)
2. [The problem, told as a story](#2-the-problem-told-as-a-story)
3. [The core insight: deleting a record is not erasing a fact](#3-the-core-insight-deleting-a-record-is-not-erasing-a-fact)
4. [The three ways a deleted fact survives](#4-the-three-ways-a-deleted-fact-survives)
5. [What we built to fix it (the two tools)](#5-what-we-built-to-fix-it-the-two-tools)
6. [Tool 1 — the planner (minimal co-deletion)](#6-tool-1--the-planner-minimal-co-deletion)
7. [Tool 2 — the certificate](#7-tool-2--the-certificate)
8. [The parametric floor: the hard limit of deletion](#8-the-parametric-floor-the-hard-limit-of-deletion)
9. [The three memory systems we tested](#9-the-three-memory-systems-we-tested)
10. [Every experiment, in plain words](#10-every-experiment-in-plain-words)
11. [The numbers cheat-sheet](#11-the-numbers-cheat-sheet)
12. [Glossary — every term and symbol](#12-glossary--every-term-and-symbol)
13. [How the code is organized](#13-how-the-code-is-organized)
14. [The paper's argument, in order (for your rewrite)](#14-the-papers-argument-in-order-for-your-rewrite)
15. [Things we deliberately do NOT claim](#15-things-we-deliberately-do-not-claim)

---

## 1. The one-paragraph summary

Modern AI assistants have a **memory**: they remember facts about you across
conversations (your address, your allergies, your salary). Privacy law (the "right
to be forgotten") says you can ask them to **delete** a fact. This project asks a
simple, uncomfortable question: **when the system says "deleted," is the fact
actually gone?** We find that very often it is *not* — the fact quietly survives, or
can be rebuilt from other things the system still remembers. We (a) explain the
**three different ways** a deleted fact can come back, (b) build a **planner** that
figures out the *minimal extra deletions* needed to truly close those gaps, and (c)
issue a **certificate** — an honest receipt that says exactly how erased a fact is,
what it cost to get there, and when true erasure is *impossible*. We show all of this
on three real, popular AI-memory systems.

The framework has a name in the paper: **REDACT** = **R**ecoverability
**D**ecomposition **a**nd **A**uditable **C**o-Dele**t**ion.

---

## 2. The problem, told as a story

Imagine you tell your AI assistant: *"Please forget my home address."*

The assistant says: *"Done — I've deleted it."*

But here is what really happened under the hood:

- The address was stored in the assistant's **main working notes**, and the
  assistant *did* erase it there. That is the part it was "looking at," so it feels
  done.
- But weeks ago, the same address also got copied into a **long-term archive** (a
  separate storage the assistant wasn't looking at right now). Nobody touched that.
- So a month later, an ordinary search pulls the address right back up.

The deletion was **confirmed**, **looked complete**, and **was not**. That exact
scenario is the opening story of the paper, and it really happens in one of the
systems we test (Letta/MemGPT).

And it gets subtler. Even if the assistant *perfectly* deleted every copy of your
address, some facts can be **rebuilt from other facts it still remembers**. Example:

- You ask it to forget your **salary**.
- It still remembers your **job title** ("Senior Software Engineer at Google
  Singapore") and it knows (or can look up) the **public pay band** for that role.
- From those two surviving facts, anyone can *re-compute* a very good estimate of
  your salary. The salary was never "stored" anymore — but it's not gone.

So there are really two failures hiding inside one word ("delete"):

1. The fact physically **survives somewhere** you didn't clean up.
2. The fact can be **reconstructed** from things you didn't (or couldn't) delete.

This project is about naming these failures precisely, measuring them, and fixing the
fixable ones.

---

## 3. The core insight: deleting a record is not erasing a fact

This is the single most important idea in the whole project. Say it out loud:

> **Deleting a record ≠ erasing a fact.**

A **record** is one row of stored text ("User's address is 12 Orchard Road").
A **fact** is the underlying information ("this person lives at 12 Orchard Road").

You can delete the record and still fail to erase the fact, because the fact can:
- live on in a **copy or a summary** the system made, or
- be **re-derivable** from other records, or
- be something the AI model **already knows from general world knowledge**.

The paper's word for "the fact is truly gone" is **deletion-completeness**. A
deletion is *complete* when the fact is no longer **recoverable** by *any* route.

The key measurable quantity is **recoverability**: *can an adversary get the value
back?* We give the "adversary" the most generous position possible — they can read
**everything still in the store**, they can freely query the AI model, and they know
**general facts about the world**. If, under those conditions, they can still produce
the deleted value, the deletion was **incomplete**.

Why is this framing stronger than what others do? Prior work (a benchmark called
**ForgetEval**) checks a *weaker* thing: "after a forget command, does the value
still show up in the top search results?" That's a fine check, but it is
**necessary, not sufficient**. Passing it does *not* prove the fact is gone — it can
still hide in a summary, or be rebuilt from surviving facts. Our notion catches all
of those. (This distinction matters a lot for the paper — see Section 15.)

---

## 4. The three ways a deleted fact survives

This is the heart of the project. We break "recoverability" into **three separate
channels**. They fail for different reasons and need different fixes. Keeping them
separate is the main conceptual contribution.

Picture deleting a fact, and three doors it can escape through:

```
                        You "delete" fact F
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
  CHANNEL 1              CHANNEL 2              CHANNEL 3
  Residual survival      Re-derivation          Parametric floor (ρ)
        │                      │                      │
  A leftover copy /      All copies gone, but   The AI model already
  summary still          surviving facts let    knows the value from
  literally contains     you REBUILD F          general world knowledge,
  the value              (F = job + pay band)   with NOTHING from the store
        │                      │                      │
  FIX: delete every      FIX: also delete the   NO FIX. You cannot delete
  copy that holds it     facts F is built from  the world's knowledge.
                         (the "planner" does    This is a hard floor.
                          this)
```

Let's walk each door slowly.

### Channel 1 — Residual survival ("a copy is still lying around")

The simplest failure. Somewhere in the store, a **surviving record still literally
contains the value**. Maybe a duplicate row, maybe a summary note, maybe a profile
field. You deleted the "main" copy but missed the others.

- **Example:** you delete your Wi-Fi password, but the system had quietly stored it
  in **three near-identical rows** (paraphrases of the same fact). Deleting one
  leaves two.
- **How we detect it:** the `ExactMatchProbe` — literally scan every remaining record
  for the value's text.
- **Does it depend on the AI model?** No. A copy is a copy. This is the one channel
  that is purely mechanical.
- **The fix:** delete *every* record that carries the value ("artifact-aware
  deletion"), not just the first one that pops up.

### Channel 2 — Re-derivation ("rebuild it from surviving clues")

Harder. **No surviving record contains the value anymore** (residual is zero), but
the value can be **reconstructed by reasoning** over facts that *are* still there.

- **Example:** salary is gone, but "Senior SWE at Google SG" (still stored) plus the
  public pay band (world knowledge) lets you re-compute it.
- **How we detect it:** the re-derivation probe hands the AI model the *entire
  surviving store* as notes and asks it to produce the value. If it can, the channel
  is open.
- **Does it depend on the AI model?** Yes. A smarter reasoner rebuilds more. So we
  test with **four different AI models** (see Section 9) and take the **worst case**.
- **The fix:** **co-deletion** — also delete the surviving facts that make the
  rebuild possible (the "operands"). That's what the planner does.

### Channel 3 — Parametric floor, written **ρ** (rho) ("the model already knew it")

The deepest, and the one you **cannot fix**. Even with the store **completely
empty**, the AI model can sometimes produce the value from **general world
knowledge alone**.

- **Example:** you delete "holds a Class-3 driving licence." But *anyone* knows a
  licence holder must be **at least 18**. So "at least 18" is recoverable from world
  knowledge — no store needed. Deleting things from the store can never lower this.
- **How we measure it:** the parametric probe gives the model **nothing from the
  store**, only the subject's world-knowable context, and asks for the value. We run
  this many times and measure the **fraction of times** it succeeds. That fraction is
  **ρ**, a number between 0 and 1.
- **Why it's a "floor":** it's the lowest recoverability can ever go. No amount of
  deletion pushes below it.
- **The fix:** *there isn't one.* The only real defense is **never storing the fact
  in the first place**, or **honestly disclosing** that it can't be fully erased.

### Putting the three together

The overall recoverability of a fact is the **worst (highest) of the three
channels**:

```
recoverability = max( residual, re-derivation, ρ )
```

Why `max`? Because a smart adversary uses **whichever door is open**. If any one
channel leaks, the fact is recoverable. So a fact is only truly erased when **all
three** are below our tolerance.

---

## 5. What we built to fix it (the two tools)

Once you see the three channels, two tools follow naturally:

1. **A planner** that *closes the two fixable channels* (residual + re-derivation)
   with the **fewest extra deletions possible**. (Section 6.)
2. **A certificate** — a machine-readable receipt that records **what deletion
   achieved, what it cost, and when erasure is impossible** (because of the ρ floor).
   (Section 7.)

Everything is **black-box**: we never retrain or edit the AI model's internal
weights. We only add and delete records in the memory store, and we query the model
from the outside. This is realistic — it's what a real deployed system can actually
do.

---

## 6. Tool 1 — the planner (minimal co-deletion)

The planner's job: given a fact whose residual is already handled, **close the
re-derivation channel by deleting as few extra facts as possible.**

### Why "as few as possible" is the whole challenge

To kill re-derivation, you could just delete *everything related*. But that's
reckless — you'd delete tons of innocent facts the user never asked you to remove.
So there's a tension:

- Delete **too little** → the fact can still be rebuilt (deletion incomplete).
- Delete **too much** → you destroy innocent "bystander" facts (collateral damage).

The planner walks the tightrope: delete the **minimal set** of surviving facts that
closes the rebuild path. We call the number of extra facts deleted the
**collateral k**. Lower k is better.

### Why this is genuinely hard (and the theory bit)

Finding the truly minimal set is **NP-hard** — a known "computationally hard"
problem. The paper proves this by showing our problem is equivalent to a classic hard
problem called **Minimum Hitting Set** (each way to rebuild the fact is a "set" you
must "hit" by deleting at least one of its ingredients). Because it's hard in
general, we use a **greedy heuristic** — a smart, practical shortcut that works
excellently on the small dependency graphs seen in practice.

### How the entailment detector works (finding the rebuild ingredients)

Before the planner can co-delete, it needs to know *which* surviving facts can
rebuild the target. That's the **entailment detector**: an "LLM-as-judge" that looks
at a candidate surviving fact and the deleted target and answers:

- **YES** — this fact (or set of facts) lets you infer the target (high confidence).
- **PARTIAL** — right category, but not enough to pin the value.
- **NO** — no meaningful help.

It returns a confidence score. **Important finding:** the small model
(`gpt-4o-mini`) is trigger-happy — it wrongly shouts "YES!" on **76%** of *partial*
clue-sets (e.g. "Bob has a home loan" → it claims you can compute the exact monthly
payment, which you can't). The bigger pinned model (`gpt-4o`) cuts this to **45%**, and
frontier Sonnet 5 to just **3.4%** — but critically, *all four models never miss a true
entailer* (0% multi-hop miss-rate), which is the safety property that matters. The
planner uses **gpt-4o** for entailment (the lowest-false-fire *reproducible dated
snapshot*). And because the planner co-deletes by the known entailment DAG rather than
the judge, the judge's false-fire never inflates k. (This is a recurring theme: *the
choice of judge model is validated, not assumed.*)

### The threshold planner, step by step

The recommended planner (`heuristic_threshold` in `planner/optimizer.py`) works like
this. **τ (tau) = 0.10** is our tolerance — anything below it counts as "closed."

```
Step 1 — Probe.
  Measure the three channels right now.
  If max(residual, re-derivation) is already below τ → done, delete nothing extra.

Step 2 — Purge the target's own leftovers.
  Delete every remaining copy of the target's OWN value (residual cleanup).
  Re-probe. If closed → done.

Step 3 — Co-delete the ingredients, one at a time, smartest-first.
  Sort the entailing facts by confidence (highest first).
  For each one:
      if its confidence is below τ → stop (the rest can't matter).
      delete that fact's records.
      re-probe.
      if the channel is now closed → STOP immediately.
```

The magic is **Step 3's "re-probe and stop early."** As soon as enough ingredients
are gone to break the rebuild, it halts — so it usually deletes only a fact or two.
That's why the average collateral is **k = 1.04** (about one extra fact per
target, on average).

### The comparison that proves the point (depth-first)

To show the re-probing matters, we built a deliberately dumb comparator called
**depth-first**: it deletes *every* candidate above the threshold in **one shot**,
with **no re-probing and no stopping**. It also reaches 100% completeness — but at
**k = 6.18** (about **6× more** deletions) and **1116 spurious bystander deletions**.
The lesson: **re-probing buys you both minimality and selectivity.** The threshold
planner reaches the *same* completeness at a fraction of the damage.

### The three deletion "modes" (in `pipeline/deleter.py`)

- **Naive** (`delete_top_match`) — delete only the single record the system surfaces
  first. This simulates a lazy, real-world RTBF implementation. It's the **baseline**,
  and it fails (leaves residual copies).
- **Artifact-aware** (`delete_value_rows`) — delete **every** record containing the
  value. This fixes **residual survival**.
- **Direct** (`delete_records`) — delete specific records by ID. The planner uses this
  for precise co-deletion.

---

## 7. Tool 2 — the certificate

The certificate is the project's "honest receipt." For each deleted fact it records
what really happened. It's a structured object (`certificate/schema.py`,
`DeletionCertificate`) with both a JSON form and a human-readable printout.

### What's on the certificate

| Field | Plain meaning |
|---|---|
| `residual_survival_score` | Channel 1 score. 0 = no copy survived, 1 = a copy survived. |
| `re_derivation_score` | Channel 2 score, **after** co-deletion. 0 = can't rebuild it anymore. |
| `parametric_risk_rho` | Channel 3, **ρ**. The irreducible floor from world knowledge. |
| `final_recoverability` | `max` of the three above — the bottom line. |
| `facts_co_deleted` | Which extra facts the planner had to delete. |
| `collateral_k` | How many extra facts that was (the price of erasure). |
| `status` | `COMPLETE`, `PARTIAL`, or `INCOMPLETE`. |
| `floor_reaching` | **True** = the two deletable channels are closed. "As erased as deletion can get." |
| `completeness_certified` | **True** = also `ρ < τ`, i.e. even world knowledge can't rebuild it. |

### The two key checkmarks — and why there are two, not one

This is subtle but important. There are **two** yes/no verdicts, and they can
disagree:

- **`floor_reaching`** = we closed everything **deletion can close** (residual = 0
  and re-derivation = 0). This is **always achievable** — just keep co-deleting.
- **`completeness_certified`** = floor-reaching **AND** the parametric floor is also
  low (`ρ < τ`). This is *not* always achievable, because you can't delete ρ.

The gap between them — **`floor_reaching = true` but `completeness_certified =
false`** — is the paper's **limit result**. It means: *"This fact is as deleted as it
can possibly be, and it's STILL recoverable from world knowledge alone."*

### A real example of each (from `paper/`)

**A COMPLETE certificate — fact F040 (a salary), on Letta:**
- Residual = 0, and before co-deletion it *was* rebuildable
  (`rederiv_with_operands = 1.0`).
- The planner co-deleted 2 facts (C001, C002 — the job title and pay band).
- After that, re-derivation = 0, and ρ = 0 (the subject is fictional, so world
  knowledge gives nothing).
- Result: `floor_reaching = true`, `completeness_certified = true`, status
  **COMPLETE**. Truly erased.

**An INCOMPLETE certificate — fact R11 ("Ms Chua is at least 18"), on Mem0:**
- Residual = 0, re-derivation = 0 — both deletable channels are closed.
- But ρ = **1.0** — the model *always* infers "at least 18" from "has a Class-3
  licence," using nothing but world knowledge.
- Result: `floor_reaching = true`, `completeness_certified = **false**`, status
  **INCOMPLETE**. This is the limit result made concrete: forgotten from the store,
  still knowable from the world.

The certificate's honesty is the point. Instead of a misleading "complete but
recoverable," it reports **two separate, exact predicates** — what deletion achieved,
and whether that's enough.

---

## 8. The parametric floor: the hard limit of deletion

This deserves its own section because it's the paper's most important scientific
result — its "limit result."

**The claim:** some facts can be recovered from **general world knowledge alone**, so
**no deletion from the store can ever certify them as erased.** We don't just assert
this — we **measure** it.

### How we measure ρ (experiment exp07)

We wrote **250 facts** spread across a difficulty gradient — from "impossible to
guess" to "obvious from context":

- **Low tier** — arbitrary secrets: locker PINs, Wi-Fi passwords. Expect **ρ ≈ 0**
  (no one can guess a random PIN).
- **Mid tier** — loosely implied: occupation → rough income range. Expect ρ somewhere
  in the middle.
- **High tier** — nearly forced by context: "Class-3 licence" → "at least 18",
  "national service" → "male". Expect **ρ ≈ 1** (the world basically tells you).

For each fact, we withhold the store entirely, ask the model for the value **8
times**, and record how often it gets it. That fraction is ρ. We do this with **four
adversary models** and keep the **worst (highest)** ρ for each fact.

### The headline result

Sorting all 250 facts by their worst-case ρ (Table `tab:rho` in the paper):

| Worst-case ρ | Meaning | # of facts | Certifiable? |
|---|---|---|---|
| ρ ≤ 0.1 (= τ) | certifiable floor | **166** | ✅ yes |
| 0.1 < ρ < 0.5 | intermediate band | **42** | ❌ no |
| ρ ≥ 0.5 | hard floor | **42** | ❌ no |
| **total** | | **250** | **166 certifiable** |

So **84 of 250 facts cannot be certified as erased** (42 + 42) — *even though their
residual is 0 and every rebuild path was closed*. That's the limit result: **once a
value is inferable from world knowledge no one can delete, no co-deletion can certify
its erasure.**

### Two important nuances (don't miss these for the paper)

1. **The floor is a gradient, not a clean on/off.** There's a 12-fact "middle band"
   between certifiable and hopeless. That means the count of uncertifiable facts
   **moves with τ**. So **τ is a policy dial**: choosing τ = 0.1 is literally
   choosing "how much residual world-guessability am I willing to tolerate?" (An
   earlier, smaller version of the data looked perfectly bimodal / all-or-nothing;
   the larger data shows it's actually a smooth gradient. Use the gradient framing.)

2. **Stronger AI models are not uniformly stronger adversaries.** On *benign* facts,
   the frontier models (GPT-5.5, Sonnet 5) rebuild more — they're the worst case. But
   on *sensitive* facts (national service → sex, licence → age), the frontier models
   often **refuse** to answer for safety reasons. A refusal makes their measured ρ an
   **underestimate**. So on sensitive facts the older `gpt-4o` (which refuses less)
   ends up being the worst adversary. This is exactly why we use a **panel of four
   models and take the worst per fact** — no single model is worst everywhere. (There
   were **20 refusal flags** in the data.)

### Why this doesn't contradict "ρ = 0" for the salary facts

In the re-derivation experiments (exp04/exp11) we report **ρ = 0**. Here we report ρ
up to 1. No contradiction:
- The salary facts use **fictional people**. Their world-knowable part is inert —
  useless without the fictional stored operand. Delete the operand and ρ collapses to
  0. That's the *deletable* channel.
- The ρ-gradient facts use **contexts that are themselves world-knowable** and pin
  down the target (a licence really does imply age ≥ 18). That recovery lives in the
  **irreducible floor**, not the deletable channel.

This distinction — *inert world-context (deletable) vs. binding world-context
(irreducible)* — is the spine that ties the framework together.

---

## 9. The three memory systems we tested

We tested the whole idea on **three real, popular AI-memory systems**, each built on
a **completely different architecture**. The point: residual survival shows up in
**all three**, but through a **different by-design mechanism** each time. That's the
"generalization" evidence — the problem isn't one system's bug, it's a property of
how agent memory works.

All three sit behind one common interface (`MemorySystemAdapter` in `systems/base.py`),
so the exact same probes/planner/certificate run on all of them — you only swap the
adapter.

### System 1 — Mem0 (the primary system: a "dedup pipeline")

- **How it stores:** extracts facts from conversation and saves them into a local
  vector database (Chroma). It's supposed to avoid duplicates.
- **How it leaks (the mechanism):** **silent duplication.** Its de-duplication only
  catches near-identical text; **paraphrased versions of the same fact get saved as
  separate rows.** So one fact becomes 2–4 rows. Delete the top one → copies remain.
- This is a *documented* Mem0 limitation (their own issue tracker: #4896, #4573,
  #687), **not a quirk of our setup or our embedder** — we proved that with a
  2×2 factorial experiment (exp05).

### System 2 — Zep / Graphiti (secondary: a "bi-temporal knowledge graph")

- **How it stores:** facts become **episodes**, which get turned into a **graph** of
  entity nodes and relationship edges (stored in Neo4j). It also writes **summaries**
  for entities and "communities."
- **How it leaks (the mechanism):** **stale summaries.** The explicit delete
  (`remove_episode`) is actually *clean* — it hard-deletes the episode, its edges, and
  orphaned entities (we verified this). **But the summaries written during ingestion
  are never recomputed on deletion.** The deleted value lives on inside those stale
  summaries.
- Note: we originally *guessed* the leak would come from "bi-temporal edge
  invalidation." We checked — that guess was **wrong**. The real channel is stale
  summaries. (Good example of an empirically-corrected assumption.)

### System 3 — Letta / MemGPT (tertiary: an "LLM-paging agent")

- **How it stores:** two surfaces. **Core memory blocks** (small, in-context, the
  agent actively reasons over them) and an **archival** vector store (large,
  out-of-context passages). Crucially, deletion here is **agent-mediated** — the agent
  itself decides how to carry out a delete request, via tool calls.
- **How it leaks (the mechanism):** **surface-incomplete, agent-mediated deletion.**
  Give the agent an **explicit** instruction ("delete X from core **and** archival")
  and it clears both → **100% faithful.** But give it a **vague, realistic** request
  ("I'm not comfortable with you keeping X"), and the agent scrubs the **core block**
  it's reasoning over and **silently misses the archival copy** → **0% faithful, 100%
  archival residue.** The agent even *confirms* the deletion succeeded while the fact
  quietly survives.
- This is the **opening story** of the paper, and the most memorable finding. It's
  genuinely new because the prior benchmark (ForgetEval) **deliberately skipped the
  agent loop** — it wrote to the archive directly, keeping the AI out of the delete
  path. We tested exactly the path they skipped.

### The four adversary "reasoner" models

Wherever recovery depends on reasoning (channels 2 and 3), we test against a **panel
of four models** and take the **worst-case**:

1. `gpt-4o-mini` — small, older (also the *primary* reasoner).
2. `gpt-4o` — bigger, older (also the *entailment judge*).
3. **Claude Sonnet 5** — frontier.
4. **GPT-5.5** — frontier.

Frontier models are added **as adversaries only** — never as judges or fact-authors —
to keep the pipeline reproducible and avoid a model grading its own work.

### One-glance summary of the three-family convergence

| Family | System | The leak mechanism (by design) | Headline |
|---|---|---|---|
| Dedup pipeline | **Mem0** | silent **duplication** (paraphrase copies) | 97.2% residual → 0% when artifact-aware |
| Bi-temporal KG | **Graphiti** | **stale summaries** (not recomputed on delete) | edge 20% residue, but **83%** summary residue |
| LLM-paging agent | **Letta** | agent scrubs core, **misses archival** | **0% faithful / 100% archival** on vague request |

---

## 10. Every experiment, in plain words

There are **11 experiments** (exp01–exp11) plus a judge-validation run. Here's each
one: the question it asks, what it did, and the number it produced. All numbers are
from the current large-scale run (datasets: **253** isolated facts, **298** multi-hop
facts, **963** context facts, **250** ρ-gradient facts). The tolerance is **τ = 0.10**
throughout.

### exp01 — How bad is naive (single-record) deletion? *(Mem0)*
Delete just the one record the system surfaces, then check if the value survives
elsewhere.
**Result: 97.2% residual survival** (246 of 253 facts). Naive deletion almost always
leaves a copy — because Mem0 duplicated the fact.

### exp02 — Does artifact-aware deletion fix residual survival? *(Mem0)*
Same facts, but now delete *every* record carrying the value.
**Result: 97.2% → 0%.** Cleaning up all copies fully closes Channel 1. (Both runs
land on the same 97.2% independently — a small built-in replication.)

### exp03 — Can the planner close re-derivation with minimal collateral? *(Mem0)*
Run the full exact planner on all 298 multi-hop targets.
**Result: 100% completeness, 0 spurious bystander deletions, mean k = 1.04** (466
operands spared by stopping early). The dumb comparator (depth-first) also reaches
100% but at k = 6.18 with 1116 spurious deletions. **Re-probing is what keeps it
minimal and selective.**

### exp04 — Is re-derivation real, and does co-deletion close it? *(Mem0)*
The clean "operands-only control": inject the *ingredients* but **never store the
target value**, so residual is 0 by construction. Whatever the model recovers, it
recovered by *reasoning*. Bin the targets into **bin1 (stored-alone: ingredients
suffice)** and **bin2 (stored+world: need world knowledge too)**.
**Result:** bin1 re-derives at **97–100%**, bin2 at **62 / 72 / 68 / 66%** (mini / gpt-4o /
Sonnet 5 / GPT-5.5) — and **both drop to 0% after co-deleting the operands**, with ρ = 0.
Note the worst re-deriver is **gpt-4o (72%)**, not the frontier models — the worst case the
certificate is built for (it certifies against whichever reasoner is strongest per fact). A special **multi-level set** (where the target's direct
ingredients are *themselves* unstored and must be traced to deeper roots) re-derives
at **100% → 0%**, proving the planner recurses to the real roots, not just one hop.

### exp05 — Is Mem0's duplication our fault (embedder/timing) or Mem0's design? *(Mem0)*
A **2×2 factorial**: two embedders (local MiniLM vs OpenAI) × two injection speeds
(0s vs 1.5s pause).
**Result: duplication in ALL FOUR cells (80–82%), with both byte-identical and
paraphrase copies in every cell (row-inflation ×1.75–1.82).** So it's a **semantic-dedup
design limitation of Mem0**, not our embedder and not a timing race. (Corroborated by
Mem0's own bug reports.)

### exp06 — Does Mem0's "infer=True" mode capture derivations? *(Mem0)*
Check whether Mem0, when consolidating, actually *computes* a target from its
operands.
**Result: 0% — REJECTED.** What looked like derivation (e.g. "born 1991, making him
35") was just **consolidation/merging** of an already-present fact into another row,
not real derivation. So **we do NOT claim Mem0 derives facts.** (An honest negative we
keep to stay defensible.)

### exp07 — What is the parametric floor ρ, across difficulty tiers? *(base model)*
Withhold the store, ask the model for each of 250 facts 8 times, four adversaries, keep
the worst ρ per fact. (Full detail in Section 8.)
**Result: 166 certifiable / 42 intermediate / 42 hard-floor → 84 of 250 cannot be
certified erased at τ = 0.1.** The floor is a **gradient**, so τ is a policy dial.
The measured band disagrees with the *authored* difficulty tier on 74/250 facts (we
always trust the measurement, not the guess).

### exp08 — Does deletion restore "membership indistinguishability"? *(Mem0)*
A membership-inference attack (MIA): can an attacker tell whether a fact was **ever
stored**, just from the system's retrieval-similarity scores? Test three states:
intact (never deleted), naive-deleted, artifact-aware-deleted. Uses **253 members +
759 matched near-twins**, with confidence intervals and a permutation test.
**Result:**
- **Intact: AUC 0.66, p = .001** — a real signal (this is the sanity check: the test
  *has* power to detect leakage).
- **Naive: AUC 0.66, p = .001** — **still leaks** significantly. Naive deletion
  barely dents the signal.
- **Artifact-aware: AUC 0.51**, CI [0.498, 0.523] just includes 0.5, permutation p =
  .04 — **attenuated toward chance, but not provably eliminated.**
So the honest statement: artifact-aware deletion *sharply reduces* the membership
signal but we can't prove it's fully gone at this sample size. (This experiment has a
history — see the note below.)

### exp09 — Does Graphiti leak after a clean delete? *(Zep/Graphiti)*
Delete an episode with `remove_episode`, verify the graph is clean, then scan the
summaries.
**Result: edges 20% residue, but summary residue 83%** (n = 30). The value survives in
**stale entity/community summaries** — a KG-residual channel, different from Mem0's
duplication.

### exp10 — Is Letta's agent-mediated deletion faithful? *(Letta/MemGPT)*
Compare an **explicit** dual-surface delete instruction vs a **vague, realistic**
request, with the fact present in both core and archival. (n = 10 sensitive-PII
targets.)
**Result: explicit → 100% faithful; vague → 0% faithful, 100% archival residue, 0%
core residue.** The agent clears the surface it reasons over and silently misses the
other. The **explicit baseline (100%) proves it's a phrasing/surface-coverage
problem, not a missing capability.** This is the paper's hook.

### exp11 — Does the re-derivation channel and planner port to Letta? *(Letta/MemGPT)*
Repeat exp04's operands-only control on a totally different system.
**Result: bin1 96–100%, bin2 59/65/59/65% (four adversaries) → 0% after co-delete; ρ = 0;
faithful direct co-delete 100%; bystanders intact 100%.** The framework ports
unchanged. (Co-deletion here uses the *direct, verified* `passages.delete`, not the
agent — so "re-derivation closed" can't be confused with "the delete didn't run,"
keeping this cleanly separate from exp10.)

### Judge validation — are our two AI judges trustworthy?
Two judges do load-bearing work: the **recovery judge** (did this answer recover the
value?) and the **entailment judge** (do these facts entail the target?).
**Result:**
- **Recovery judge (n = 229 gold): near-zero false accepts** — gpt-4o-mini and gpt-4o
  each false-accept only **0.72%** (Sonnet 5 and GPT-5.5: **0**). It essentially never
  says "recovered" when it wasn't → **every leak rate we report is a conservative lower
  bound.** All four models were validated; the pinned production judge is **gpt-4o-mini**
  (lowest false-accept among reproducible dated snapshots).
- **Entailment judge (n = 1370 pairs): multi-hop miss-rate = 0 for all four models** —
  the safety-critical result the whole method depends on: no model ever *loses* a true
  entailer. On curated near-misses (the over-detection axis) false-fire is Sonnet 5
  **3.4%**, GPT-5.5 **30%**, gpt-4o **45%**, gpt-4o-mini **76%**. The pinned production
  judge is **gpt-4o**: it's the lowest-false-fire among *reproducible dated snapshots*
  (Sonnet 5 is best overall but a rolling alias, so it's reported as corroboration only).
  Crucially, the planner co-deletes by the **known entailment DAG**, not this judge, so a
  judge's false-fire never inflates the planner's k.

### A note on exp08's history (a credibility asset, not a weakness)
An early version reported a membership signal at only **n = 6** — badly underpowered.
We **retracted it**, re-ran properly at **n = 253**, and reported the nuanced result
above. Showing "we caught our own mistake and fixed it" is used in the paper's
Limitations as a sign of rigor.

---

## 11. The numbers cheat-sheet

Everything you might want to cite, in one place. (Ground truth = the large-scale run;
τ = 0.10; four adversaries = gpt-4o-mini, gpt-4o, Claude Sonnet 5, GPT-5.5.)

**Datasets**
- Isolated PII facts: **253**
- Multi-hop facts: **298** (6 topologies: flat/join/chain/or_and/diamond/threshold)
- Context facts: **963** (775 entailing operands + 188 bystanders)
- ρ-gradient facts: **250** (low/mid/high tiers)

**Residual survival (Channel 1) — exp01/02, Mem0**
- Naive single-record delete: **97.2%** residual (246/253) [Wilson 94.4–98.7]
- Artifact-aware delete: **0%** [0–1.5]
- Duplication incidence (exp05): **80–82%**, row-inflation **×1.75–1.82**, in all 4 cells

**Re-derivation (Channel 2) — exp04 (Mem0) / exp11 (Letta)**
- bin1 stored-alone: **97–100%** → **0%** after co-delete
- bin2 stored+world (Mem0): **62 / 72 / 68 / 66%** (4 adversaries) → **0%**
- bin2 stored+world (Letta): **59 / 65 / 59 / 65%** → **0%**
- 5 hard topologies (join/chain/or_and/diamond/threshold): **100%** → **0%**
- ρ throughout: **0** (fictional subjects)

**The planner (Tool 1) — exp03, Mem0**
- Completeness: **100%** [Wilson 0.96–1.0]
- Spurious bystander deletions: **0**
- Mean collateral: **k = 1.04** [0.99–1.09]; **466** operands spared
- Depth-first comparator: **k = 6.18**, **1116** spurious (exp12: exact is provably minimal, gap≈0)

**Parametric floor (Channel 3) — exp07, base model**
- **84 of 250** facts uncertifiable at τ = 0.1 (42 intermediate + 42 hard-floor)
- 166 certifiable
- 74/250 measured band ≠ authored tier; 29 refusal flags (high-tier only)

**Membership inference — exp08, Mem0 (n = 253 members + 759 twins)**
- Intact AUC **0.66** (p = .001) — power sanity
- Naive AUC **0.66** (p = .001) — significant leak
- Artifact-aware AUC **0.51** (CI [0.498, 0.523] incl. 0.5; p = .04) — attenuated

**Cross-system — exp09/10**
- Graphiti: edge **20%**, summary **83%** residue (n = 30)
- Letta: faithful-delete **0%**; core residue **13%** / archival **100%** (n = 30)

**Judges**
- Recovery false-accept on gold (n = 229): gpt-4o-mini **.0072**, gpt-4o **.0072**,
  Sonnet 5 **0**, GPT-5.5 **0**
- Entailment multi-hop miss-rate: **0** (all 4 models, n = 1370 pairs); near-miss false-fire
  Sonnet 5 **3.4%**, GPT-5.5 **30%**, gpt-4o **45%**, gpt-4o-mini **76%**

---

## 12. Glossary — every term and symbol

Read this before the paper; it will make the notation painless.

| Term / symbol | Plain meaning |
|---|---|
| **RTBF** | Right To Be Forgotten — the legal right to have your data deleted. |
| **Record** | One stored row of text in the memory. |
| **Fact (F, f)** | The underlying information a record carries. |
| **Value (v)** | The specific answer being protected (the salary, the address). |
| **Deletion-completeness** | The property that a deleted fact is truly gone — not recoverable by any channel. |
| **Recoverability (R)** | Can an adversary get the value back? The thing we measure. |
| **Adversary (𝒜)** | The worst-case attacker: reads the whole surviving store, queries the model, knows world facts. |
| **Surviving store (S′)** | What's left in memory after deletion. |
| **Residual survival (σ_res)** | Channel 1: a surviving record still literally contains the value. |
| **Re-derivation (σ_red)** | Channel 2: surviving facts let you *rebuild* the value by reasoning. |
| **Parametric floor (ρ, "rho")** | Channel 3: the model recovers the value from world knowledge, store empty. Irreducible. |
| **Operands** | The surviving "ingredient" facts that make re-derivation possible. |
| **Bystanders** | Innocent facts the planner must NOT delete. Deleting one = a "spurious" deletion. |
| **Co-deletion** | Deleting operands (extra facts) to close the re-derivation channel. |
| **Collateral k** | How many extra facts were co-deleted. The "price" of erasure. Lower is better. |
| **τ ("tau")** | The tolerance threshold, 0.10. Below it = "channel closed." Also a policy dial. |
| **Entailment** | "These facts logically imply the target." Detected by an LLM judge. |
| **floor_reaching** | Certificate flag: both deletable channels closed (residual = re-derivation = 0). Always achievable. |
| **completeness_certified** | Certificate flag: floor-reaching AND ρ < τ. Not always achievable. |
| **The limit result** | floor_reaching = true but certified = false: as erased as possible, yet still world-inferable. |
| **Opt-P2E2** | The optimization problem: minimize k while closing re-derivation. NP-hard. |
| **NP-hard** | Computationally hard; no known efficient exact algorithm → we use a greedy heuristic. |
| **infer=True / infer=False** | Mem0 mode: True = extract & merge facts (realistic); False = store verbatim (controlled experiments). |
| **bin1 / bin2** | Re-derivation bins: stored-alone (operands suffice) vs stored+world (need world knowledge too). |
| **Operands-only control** | The clean test: inject ingredients but never the target value, so residual = 0 by construction. |
| **AUC** | Attack accuracy for membership inference. 0.5 = random guessing (good/safe), 1.0 = perfectly leaky. |
| **MIA** | Membership Inference Attack — can you tell if a fact was ever stored? |
| **REDACT** | The framework name: Recoverability Decomposition and Auditable Co-Deletion. |

---

## 13. How the code is organized

A quick map so you can find anything. (Directories under the project root.)

```
config.py        — all settings: API keys, model names, τ, file paths
llm.py           — one function for all AI calls (OpenAI + Anthropic), with an
                   on-disk cache so re-runs are free and deterministic

data/facts/      — the controlled datasets (JSON):
    isolated_facts.json      (253 standalone PII facts — for residual)
    multi_hop_facts.json     (298 rebuildable facts — for re-derivation)
    context_facts.json       (963: 775 entailing operands + 188 bystanders)
    rho_gradient_facts.json  (250 facts tiered by world-knowability — for ρ)

systems/         — one adapter per memory system, all behind base.py:
    mem0_adapter.py, zep_adapter.py, letta_adapter.py

pipeline/        — injector.py (feed facts in as conversation),
                   deleter.py (naive / artifact-aware / direct deletion)

probes/          — the detectors (each returns a 0–1 recoverability score):
    exact_match.py         (Channel 1: scan for the literal value)
    parametric_probe.py    (Channel 2 re-derivation AND Channel 3 ρ)
    paraphrase_probe.py    (residual-by-implication, auxiliary)
    membership_inference.py(the MIA / AUC probe)
    kg_node_residue.py     (Graphiti summaries + edges)

planner/         — entailment_detector.py (LLM judge: does X entail the target?)
                   optimizer.py (GreedyPlanner: the threshold + depth-first heuristics)

certificate/     — schema.py (the DeletionCertificate object) + emitter.py (build/save)

evaluation/      — judge.py (validate the two judges), metrics.py (recoverability=max,
                   Cohen's kappa), recovery.py (parse numbers, detect refusals), stats.py
                   (Wilson CI, bootstrap)

experiments/     — exp01_baseline.py ... exp11_letta_rederivation.py

paper/           — the AAAI paper (deletion_completeness_aaai.tex), the separate
                   supplementary.tex, the claims ledger (CLAIMS_LEDGER.md), sample
                   certificates, and the AAAI author kit

docs/            — this document and the other explainers
```

**One design principle to remember:** the probes, planner, and certificate are
**system-agnostic**. To test a new memory system you write *one* adapter and change
nothing else. That's why the same stack runs on Mem0, Graphiti, and Letta unchanged.

---

## 14. The paper's argument, in order (for your rewrite)

When you re-write the paper, this is the logical spine. The paper leads with the
**memorable hook**, then delivers the **actual contribution**.

**The hook (Abstract + Intro):** Start with the concrete, scary story — you ask a
paging agent to forget your address, it scrubs its working memory and confirms
success, but the address survives in archival and resurfaces weeks later. Generalize:
*deleting a fact from agent memory does not mean the agent forgot it.* Prior audits
only check "is it gone from search results," which is **necessary but not
sufficient** — the value can hide in an artifact or be rebuilt from surviving facts.

**The claimed contributions (what to get credit for):**
1. A formal, **adversary-relative deletion-completeness** criterion that
   **decomposes recoverability into three channels** (residual / re-derivation /
   parametric floor). This is stronger than existing database "deletion under
   dependencies" theory.
2. A **minimal co-deletion planner** for the resulting NP-hard problem — reaches 100%
   completeness at mean **k = 1.04** with **0 spurious** deletions — plus an
   **auditable certificate** separating what deletion achieved from what it cannot.
3. A **measured** parametric floor and its **limit result**: under the strongest
   adversary, **30/250 facts cannot be certified erased** even at zero residual.
4. **Evidence of generality**: the same stack on three architectures finds residual
   survival in all three via different by-design mechanisms — including the agent-loop
   failure prior audits skipped.

**The section order in the current draft:**
- **§1 Intro** — hook + the two questions ("why do deleted facts return?" and "what
  minimal further deletion closes the leak?") + the 4 contributions.
- **§2 Related Work** — credit ForgetEval first (closest neighbor), then distinguish:
  ours is a *stronger, decomposed* question, not broader system coverage. Also:
  unlearning methods, and the database deletion-under-dependencies lineage (P2E2).
- **§3 Problem Formulation** — the definitions: residual (Def 1), re-derivation (Def
  2), parametric floor (Def 3), recoverability = max (Def 4, adversary-relative),
  floor-reaching vs certified (Def 5). Then the optimization problem and the
  NP-hardness proof.
- **§4 Method** — the concrete components: probe battery, entailment detector,
  planner (threshold + depth-first), certificate emitter.
- **§5 Experiments** — results in *decreasing order of confidence*: planner (5.1), ρ
  floor (5.2), re-derivation (5.3), three-family convergence (5.4), residual +
  duplication (5.5), judge validation (5.6).
- **§6 Limitations** — leads with the MIA "retracted → re-ran" story (a credibility
  move), then: judges are imperfect, ρ is a lower bound (refusals), the planner needs
  a known entailment graph, cross-system evidence is small (n=10).
- **§7 Conclusion** — the broad implication: when ρ ≥ τ, *no* store deletion can
  erase the fact; RTBF compliance then means **not storing it** or **disclosing the
  floor**.

**Style notes (from prior guidance):** the paper deliberately uses **plain language**,
motivation-first prose (like the LLM2CLIP paper you like), few inline numbers in the
main text (granular per-model numbers live in the separate `supplementary.tex`), and
no "Remark" blocks. The main §5 carries only headline numbers. When rewriting, keep
that: **lead with the idea and the example, push the granular tables to the
supplement.** And never change a number — every figure here is load-bearing and tied
to a specific result file.

---

## 15. Things we deliberately do NOT claim

These are guardrails. Getting one of these wrong would hand a reviewer an easy
rejection. Keep them straight in the rewrite.

1. **We do NOT claim to be "first to audit/benchmark these systems."** ForgetEval
   already benchmarks all three (plus ~10 more). Our novelty is the **stronger,
   decomposed completeness notion**, *not* the system list. Never write "first to
   evaluate."

2. **Our Mem0 numbers do NOT contradict ForgetEval's.** Theirs = "did the forget
   command clear the top-k search results." Ours = "recoverable by *any* channel."
   These are **complementary** (necessary vs sufficient). Say so explicitly wherever
   both appear.

3. **We do NOT claim the parametric-vs-memory split is novel.** Prior work (Agentic
   Unlearning) already separates those. Our novelty is the **three-way** decomposition
   plus the planner and certificate.

4. **We do NOT claim Mem0 "derives" facts.** exp06 rejected that (0%). What looked
   like derivation was consolidation/merging.

5. **The Letta agent finding is the hook, NOT the headline contribution.** It's the
   sharpest *instance* of the generalization, but credit comes from the framework
   (decomposition + planner + measured ρ). A reviewer could say "ForgetEval already
   showed deployed systems leak" — so we frame it as *a new finding* (the agent loop
   they skipped), not as *the* contribution.

6. **We do NOT claim artifact-aware deletion fully erases the membership signal.**
   At n=253 the AUC is 0.51 with the CI just including 0.5 and a marginal p=.04. The
   honest claim is "sharply reduces, does not provably eliminate."

7. **We do NOT claim the ρ floor is bimodal / all-or-nothing.** The large data shows a
   **gradient** with a 12-fact middle band. τ is a policy dial. (An earlier smaller
   run looked bimodal — that framing is retired.)

8. **The planner assumes the entailment graph is known.** In our controlled setup we
   injected the operands ourselves, so we know them. In a real deployed store you'd
   have to *discover* the graph, which is hard and unsolved. An unmodeled entailer
   stays open. State this as a limitation, not a solved problem.

---

*That's the whole project. If you've read this far, you now know: the problem
(deleting a record ≠ erasing a fact), the three channels (residual, re-derivation,
parametric floor), the two tools (planner + certificate), the hard limit (ρ), the
three systems (Mem0, Graphiti, Letta), every experiment and number, and exactly what
to claim and not claim. You're ready to re-write the paper in your own words.*
