# The Whole Project, Explained Simply

*A plain-language walkthrough of the Deletion-Completeness project — written for
someone who knows nothing about it. Read this once and you will understand the
entire project: the problem, the idea, what we built, every experiment, and every
number. Everything here is grounded in the actual code and the current results.*

> **How to use this document.** Read it top to bottom — each section assumes the one
> before it, and nothing here needs outside knowledge. Sections 1–5 are the story (the
> "why" and the "big idea"). Sections 6–8 are the machinery and a full worked example
> (what we built, shown running on one fact). Sections 9–10 are the hard limit and the
> three systems we tested on. Section 11 is every experiment and its result. Sections
> 12–14 are reference material: a numbers cheat-sheet, a plain-English glossary, and a
> map of the code. Section 15 answers the questions people always ask. Sections 16–17
> are for when you sit down to (re-)write the paper: its argument in order, and the
> claims we deliberately avoid. If you only have five minutes, read Sections 1, 4, and
> 8.

---

## Table of Contents

1. [The one-paragraph summary](#1-the-one-paragraph-summary)
2. [The problem, told as a story](#2-the-problem-told-as-a-story)
3. [The core insight: deleting a record is not erasing a fact](#3-the-core-insight-deleting-a-record-is-not-erasing-a-fact)
4. [The three ways a deleted fact survives](#4-the-three-ways-a-deleted-fact-survives)
5. [What we built to fix it (the two tools)](#5-what-we-built-to-fix-it-the-two-tools)
6. [Tool 1 — the planner (minimal co-deletion)](#6-tool-1--the-planner-minimal-co-deletion)
7. [Tool 2 — the certificate](#7-tool-2--the-certificate)
8. [A full walkthrough: one fact, from stored to certified](#8-a-full-walkthrough-one-fact-from-stored-to-certified)
9. [The parametric floor: the hard limit of deletion](#9-the-parametric-floor-the-hard-limit-of-deletion)
10. [The three memory systems we tested](#10-the-three-memory-systems-we-tested)
11. [Every experiment, in plain words](#11-every-experiment-in-plain-words)
12. [The numbers cheat-sheet](#12-the-numbers-cheat-sheet)
13. [Glossary — every term and symbol](#13-glossary--every-term-and-symbol)
14. [How the code is organized](#14-how-the-code-is-organized)
15. [Common confusions, answered](#15-common-confusions-answered)
16. [The paper's argument, in order (for your rewrite)](#16-the-papers-argument-in-order-for-your-rewrite)
17. [Things we deliberately do NOT claim](#17-things-we-deliberately-do-not-claim)

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

If you remember only one sentence, make it this: **the word "delete" hides at least
three different failures, and telling them apart is the whole game.**

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
systems we test (Letta/MemGPT). The assistant is not lying — it genuinely cleared the
memory it was reasoning over. It just never checked the *other* place the fact lived.

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

And there's a third, meaner one lurking underneath both — some facts the AI model can
guess **from general world knowledge alone**, with your memory store completely empty.
More on that in Section 4.

This project is about naming these failures precisely, measuring them, and fixing the
fixable ones. Naming them precisely turns out to matter enormously: each failure has a
*different cause* and a *different fix* (or, for the third one, *no* fix), and the
biggest mistake in this area is treating them as one thing.

---

## 3. The core insight: deleting a record is not erasing a fact

This is the single most important idea in the whole project. Say it out loud:

> **Deleting a record ≠ erasing a fact.**

A **record** is one row of stored text ("User's address is 12 Orchard Road").
A **fact** is the underlying information ("this person lives at 12 Orchard Road").

The difference sounds pedantic until you realize a single fact can leave *many*
traces. You can delete the record and still fail to erase the fact, because the fact
can:
- live on in a **copy or a summary** the system made,
- be **re-derivable** from other records, or
- be something the AI model **already knows from general world knowledge**.

The paper's word for "the fact is truly gone" is **deletion-completeness**. A
deletion is *complete* when the fact is no longer **recoverable** by *any* route.

The key measurable quantity is **recoverability**: *can an adversary get the value
back?* To make this a fair, worst-case test, we give the "adversary" the most generous
position possible — they can read **everything still in the store**, they can freely
query the AI model, and they know **general facts about the world**. If, under those
conditions, they can still produce the deleted value, the deletion was **incomplete**.
Choosing the *worst-case* adversary on purpose is what makes a "complete" verdict
meaningful: we are certifying that *even the strongest attacker we can model* comes up
empty.

Why is this framing stronger than what others do? Prior work (a benchmark called
**ForgetEval**) checks a *weaker* thing: "after a forget command, does the value
still show up in the top search results?" That's a fine and useful check, but it is
**necessary, not sufficient**. Passing it does *not* prove the fact is gone — it can
still hide in a summary, or be rebuilt from surviving facts. Our notion catches all of
those. Think of ForgetEval as checking the front door is locked; we also check the
windows, the back door, and whether a neighbor already has a spare key. (This
distinction matters a lot for the paper — see Section 17.)

---

## 4. The three ways a deleted fact survives

This is the heart of the project. We break "recoverability" into **three separate
channels**. They fail for different reasons and need different fixes. Keeping them
separate is the main conceptual contribution — most people lump them together and then
can't explain why "delete" keeps failing.

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

A quick way to keep them straight: Channel 1 is a **librarian problem** (you missed a
copy on another shelf), Channel 2 is a **detective problem** (the clues that remain
still give it away), and Channel 3 is a **common-knowledge problem** (everybody already
knows). Let's walk each door slowly.

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
  that is purely mechanical, which also makes it the one we can close with 100%
  certainty.
- **The fix:** delete *every* record that carries the value ("artifact-aware
  deletion"), not just the first one that pops up.

### Channel 2 — Re-derivation ("rebuild it from surviving clues")

Harder. **No surviving record contains the value anymore** (residual is zero), but
the value can be **reconstructed by reasoning** over facts that *are* still there.

- **Example:** salary is gone, but "Senior SWE at Google SG" (still stored) plus the
  public pay band (world knowledge) lets you re-compute it.
- **How we detect it:** the re-derivation probe hands the AI model the *entire
  surviving store* as notes and asks it to produce the value. If it can, the channel
  is open. (We don't ask it to "hack" anything — we just let it read what's left and
  reason, exactly like a curious attacker would.)
- **Does it depend on the AI model?** Yes. A smarter reasoner rebuilds more. So we
  test with **four different AI models** (see Section 10) and take the **worst case**.
- **The fix:** **co-deletion** — also delete the surviving facts that make the
  rebuild possible (the "operands"). That's what the planner does, and the trick is
  doing it *without* deleting a pile of innocent facts too.

### Channel 3 — Parametric floor, written **ρ** (rho) ("the model already knew it")

The deepest, and the one you **cannot fix**. Even with the store **completely
empty**, the AI model can sometimes produce the value from **general world
knowledge alone**. ("Parametric" = baked into the model's parameters/weights during
training, as opposed to sitting in the memory store.)

- **Example:** you delete "holds a Class-3 driving licence." But *anyone* knows a
  licence holder must be **at least 18**. So "at least 18" is recoverable from world
  knowledge — no store needed. Deleting things from the store can never lower this.
- **How we measure it:** the parametric probe gives the model **nothing from the
  store**, only the subject's world-knowable context, and asks for the value. We run
  this many times and measure the **fraction of times** it succeeds. That fraction is
  **ρ**, a number between 0 and 1.
- **Why it's a "floor":** it's the lowest recoverability can ever go. No amount of
  deletion pushes below it. You have already deleted everything; ρ is what's left.
- **The fix:** *there isn't one.* The only real defense is **never storing the fact
  in the first place**, or **honestly disclosing** that it can't be fully erased.

### Putting the three together

The overall recoverability of a fact is the **worst (highest) of the three
channels**:

```
recoverability = max( residual, re-derivation, ρ )
```

Why `max`? Because a smart adversary uses **whichever door is open**. If any one
channel leaks, the fact is recoverable — it doesn't matter that the other two are
sealed. So a fact is only truly erased when **all three** are below our tolerance. This
"weakest-link" logic is exactly why decomposing into channels pays off: to certify
erasure you have to beat *every* channel, and to know which one is failing you have to
measure them *separately*.

---

## 5. What we built to fix it (the two tools)

Once you see the three channels, two tools follow naturally:

1. **A planner** that *closes the two fixable channels* (residual + re-derivation)
   with the **fewest extra deletions possible**. (Section 6.)
2. **A certificate** — a machine-readable receipt that records **what deletion
   achieved, what it cost, and when erasure is impossible** (because of the ρ floor).
   (Section 7.)

Section 8 then runs both tools on a single fact, start to finish, so you can see the
whole machine turn over once.

Everything is **black-box**: we never retrain or edit the AI model's internal
weights. We only add and delete records in the memory store, and we query the model
from the outside. This is realistic — it's what a real deployed system can actually
do. (It also means our results don't depend on having special access to any model; the
same approach works against a model you can only send prompts to.)

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
**collateral k**. Lower k is better. (k = 0 would mean "we didn't have to touch
anything else"; k = 5 would mean "erasing this one fact cost five bystanders.")

### Why this is genuinely hard (and the theory bit)

Finding the truly minimal set is **NP-hard** — a known "computationally hard"
problem. Here's the intuition without the jargon. Each distinct way to rebuild the
fact is a **recipe**, and a recipe is a set of ingredient facts. To spoil one recipe,
you delete at least one of its ingredients. To spoil **every** recipe using the fewest
deletions, you want the smallest set of facts that "touches" all the recipes. That is
a classic hard problem called **Minimum Hitting Set** (equivalently, minimum set
cover), and the paper proves our problem is exactly that. Because it's hard *in
general*, textbook advice is to approximate it. But there's a saving grace: the
dependency graphs in real memory are **small** (a fact usually has a handful of
ingredients, not thousands), so we can afford to compute the **true minimum exactly**
on each one.

### How the entailment detector works (finding the rebuild ingredients)

Before the planner can co-delete, it needs to know *which* surviving facts can
rebuild the target — i.e., what the recipes are. That's the **entailment detector**:
an "LLM-as-judge" that looks at a candidate surviving fact (or set of facts) and the
deleted target and answers:

- **YES** — this fact (or set of facts) lets you infer the target (high confidence).
- **PARTIAL** — right category, but not enough to pin the value.
- **NO** — no meaningful help.

It returns a confidence score. **Important finding:** the small model
(`gpt-4o-mini`) is trigger-happy — it wrongly shouts "YES!" on **75.7%** of *partial*
clue-sets (e.g. "Bob has a home loan" → it claims you can compute the exact monthly
payment, which you can't). The bigger pinned model (`gpt-4o`) cuts this to **45.5%**, and
frontier Claude Sonnet 5 to just **3.4%**. But here is the property that actually
matters: *all four models never miss a true entailer* — a **0% multi-hop miss-rate**.
For a safety tool that's the right trade: over-firing wastes effort, but *missing* an
entailer would leave a rebuild path open. So a judge that never misses (even if it
sometimes over-fires) is exactly what we want. The planner uses **Claude Sonnet 5**
for entailment — the lowest false-fire of all and validated on the gold set — with the
pinned **gpt-4o** retained as the *reproducibility anchor* (Sonnet 5 has no dated
snapshot).

And here's the subtle safety move: because the planner co-deletes by the **known
entailment DAG** (see below) rather than by the judge's live verdicts, the judge's
false-fires can **never** inflate k. The judge validates the design; it doesn't drive
the deletions. (This is a recurring theme: *the choice of judge model is validated,
not assumed.*)

### The entailment DAG — the planner's single source of truth

Each structured fact carries a little map of how it can be rebuilt, called its
**entailment DAG** (directed acyclic graph). In plain terms it's a small boolean
formula over the surviving facts — for example "target is recoverable if
(job title AND pay band)" or "if ((A OR B) AND C)". The formula records every recipe
at once. Deleting a **minimum hitting set** of that formula is, by construction, the
smallest set of facts whose removal makes *every* recipe fail. This lives in
`planner/entailment_dag.py`, and it's what makes "provably minimal" a real claim rather
than a hope.

### The exact planner — the method we recommend

The recommended planner is `heuristic_exact` (in `planner/optimizer.py`). It reads the
target's entailment DAG and deletes a **provably minimal hitting set** of it. Two
properties make it the right default:

1. **Minimal with respect to the entailment DAG** — no smaller set of deletions closes
   the modeled rebuild paths. On the real datasets it reaches **100% completeness** with
   mean **k = 1.03** (about one extra fact per target) and **0 spurious bystander
   deletions**, sparing **467** operands it never needed to touch. (The one caveat: when
   an operand *also* carries a surface form of the target value, the DAG under-models
   reality and a safety fallback can add one deletion — see Section 17. exp12 measures
   the residual gap and finds it ≈ 0.)
2. **Never misses a multi-hop entailer** — because it works off the full DAG formula,
   it can't be fooled by a rebuild path that only appears two or three hops deep. This
   was the single worry that motivated the exact planner in the first place.

It also runs a quick pre-pass. Before touching anything it **probes** the three
channels; if the fact is already safe it deletes nothing. Then it **purges the
target's own leftover copies** (residual cleanup) and re-probes. Only if re-derivation
is still open does it compute and delete the minimal hitting set. So in easy cases it
does almost nothing, and in hard cases it does the least it can.

### The two comparators (why we know the exact planner is worth it)

To prove the exact planner earns its keep, we run two deliberately different
strategies side by side:

- **Threshold (greedy).** This one doesn't assume it knows the exact DAG. It sorts the
  entailing facts by the judge's confidence (highest first), deletes them **one at a
  time, re-probing after each**, and **stops the instant** the channel closes. The
  "re-probe and stop early" is the clever part: as soon as enough ingredients are gone
  to break the rebuild, it halts. It reaches the *same* 100% completeness at **k = 1.14**
  with **0 spurious** — remarkably close to optimal, using only probes and no DAG.
- **Depth-first (the dumb baseline).** It deletes *every* candidate above the threshold
  in **one shot**, with **no re-probing and no stopping**. It also hits 100%
  completeness — but at **k = 6.60** (about **6× more** deletions) and **1192 spurious
  bystander deletions**.

The lesson in one line: **re-probing (threshold) and knowing the recipe graph (exact)
each buy you minimality; brute force buys you the same completeness at 6× the damage.**

### How we *prove* "minimal" isn't just a nice word (exp12)

It's easy to claim a planner is minimal; we measured it. For the templated topologies
we know the **ground-truth optimum k\*** (the provably smallest possible co-deletion)
for each fact, so we can compute the **gap** = (what the planner deleted) − (the true
optimum):

- **Exact**: gap ≈ 0 (technically −0.067 — it sometimes even dips *below* k\* when the
  residual purge closes re-derivation early, so no ingredient deletion is needed), and
  the per-topology gap is now **≤ 0 on every single topology** — provably minimal,
  airtight. It is optimal.
- **Threshold**: gap ≈ 0 (+0.037) — essentially optimal in practice.
- **Depth-first**: gap **+5.50** — it over-deletes by about five facts per target.

One honest wrinkle worth knowing: the exact planner's average k rose from an earlier
project's **0.90** to **1.03**. That's not a regression — it's because the new, harder
**threshold topology** genuinely *requires* two deletions (its k\* = 2, "delete at
least 2 of 3 supporting facts"). The exact planner correctly pays exactly what's
required and not a fact more.

### The three deletion "modes" (in `pipeline/deleter.py`)

- **Naive** (`delete_top_match`) — delete only the single record the system surfaces
  first. This simulates a lazy, real-world RTBF implementation. It's the **baseline**,
  and it fails (leaves residual copies).
- **Artifact-aware** (`delete_value_rows`) — delete **every** record containing the
  value. This fixes **residual survival** (Channel 1).
- **Direct** (`delete_records`) — delete specific records by ID. The planner uses this
  for precise co-deletion (Channel 2).

---

## 7. Tool 2 — the certificate

The certificate is the project's "honest receipt." For each deleted fact it records
what really happened. It's a structured object (`certificate/schema.py`,
`DeletionCertificate`) with both a JSON form and a human-readable printout. The point
of a certificate is accountability: instead of a green "✓ Deleted" that means nothing,
you get a signed statement of exactly how erased the fact is and what it cost.

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
  and re-derivation = 0). This is **always achievable** — just keep co-deleting until
  both are down.
- **`completeness_certified`** = floor-reaching **AND** the parametric floor is also
  low (`ρ < τ`). This is *not* always achievable, because you can't delete ρ.

The gap between them — **`floor_reaching = true` but `completeness_certified =
false`** — is the paper's **limit result**. It means: *"This fact is as deleted as it
can possibly be, and it's STILL recoverable from world knowledge alone."* That's not a
bug in our tool; it's a true statement about the fact, and the certificate's job is to
say it out loud instead of hiding it behind a misleading "complete."

### A real example of each (from `paper/`)

**A COMPLETE certificate — fact F040 (a salary):**
- Residual = 0, and before co-deletion it *was* rebuildable
  (`rederiv_with_operands = 1.0`).
- The salary is pinned by two stored facts: the **job title** (C001, "Senior SWE at
  Google SG") and the **pay band** (C002, "that band is SGD 8,000–9,000"). The pay
  band C002 already *states* the figure, so removing **C002 alone** is the single
  necessary-and-sufficient deletion — the true minimal is **k = 1**, and the
  confidence-ordered (threshold) planner hits it exactly (deletes C002, reaches
  COMPLETE). Two other paths land on **k = 2**: the *operands-only control*
  deliberately deletes **both** (C001 + C002) for an unambiguous demo, and the *exact*
  planner (our default) models F040 as "needs both," happens to remove C001 first —
  which doesn't close it, because C002 still spells out the figure — then removes C002
  via its safety net. All three reach COMPLETE; the difference is only in how many
  deletions it took. (This C002 quirk — an operand that *also* carries the answer value
  — is the same value-coupling described in Section 17.)
- After co-deletion, re-derivation = 0, and ρ = 0 (the subject is fictional, so world
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

## 8. A full walkthrough: one fact, from stored to certified

Reading about the parts is one thing; watching the machine run once makes it click.
Let's follow a single sensitive fact — a person's **salary** — through the entire
pipeline, and then contrast it with a fact that *can't* be fully erased. (This mirrors
the two certificates above, told as a sequence of steps.)

**The setup.** We invent a fictional person and feed the system an ordinary
conversation. Along the way it stores several facts:
- **The target:** "Wei Jie earns S$X per year." (this is the salary we'll later delete)
- **Ingredient 1:** "Wei Jie is a Senior Software Engineer at [fictional company]." (a job title)
- **Ingredient 2:** "[fictional company]'s Senior SWE pay band is roughly S$X." (a pay band)
- **Bystanders:** "Wei Jie's coffee order is a flat white," "Wei Jie goes to the gym on Tuesdays." (innocent facts, nobody asked to delete these)

**Step 1 — the user asks to forget the salary.** A naive system does the lazy thing:
it finds the one salary record it surfaces first and deletes it. Feels done.

**Step 2 — Channel 1 probe (residual).** We scan every surviving record for the
salary value. Uh-oh: the system had quietly stored a **paraphrase** of the salary too
("Wei Jie's annual pay is about S$X"), and the naive delete missed it. Residual = 1.
**Fix:** switch to *artifact-aware* deletion, which removes **every** record carrying
the value. Re-scan → residual = **0**. Channel 1 closed.

**Step 3 — Channel 2 probe (re-derivation).** Now we hand the AI model the *entire
surviving store* (which still contains the job title and the pay band) and ask it for
the salary. It reconstructs it easily: title + pay band → salary. Re-derivation =
**1.0**. Channel 2 is wide open, even though no copy of the salary survives.

**Step 4 — the planner runs.** It reads the salary's **entailment DAG** — the recipe
map for rebuilding it — and computes the **minimal** set of ingredients to remove. Here
the pay-band fact ("that band is SGD 8,000–9,000") already *states* the salary figure,
so removing that **one** fact is necessary and sufficient — the true minimum is a single
deletion. A minimizing planner co-deletes just the pay band and stops. Crucially, it does
**not** touch the coffee order or the gym day — those are bystanders and were never part
of the recipe. That's the difference between the planner (**k = 1** here) and the
brute-force baseline (which would have deleted five or six facts). Re-probe Channel 2 →
re-derivation = **0**. Channel 2 closed. (Two honest wrinkles: the *operands-only
control* deletes **both** stored facts on purpose, for an unambiguous demo; and the
*exact* default planner, which models the fact as "needs both," can also land on two
deletions when — as here — one operand happens to spell out the answer value. Both still
reach COMPLETE. See Section 17.)

**Step 5 — Channel 3 (the floor).** We empty the store entirely and ask the model for
Wei Jie's salary from world knowledge alone. Wei Jie is fictional, so there's nothing
to know: ρ = **0**.

**Step 6 — the certificate.** All three channels are at 0. The certificate reports:
residual 0, re-derivation 0, ρ 0, collateral **k = 1**, `floor_reaching = true`,
`completeness_certified = true`, status **COMPLETE**. This is a genuinely,
provably-as-far-as-possible erased fact — and the receipt proves it.

**Now the contrast — a fact that can't be finished.** Repeat the exact same steps for
"Ms Chua is at least 18," which we stored alongside "Ms Chua holds a Class-3 driving
licence." Steps 1–4 go the same way: we clear every copy (residual = 0) and co-delete
so nothing in the store rebuilds it (re-derivation = 0). But Step 5 is different: with
the store empty, the model *still* answers "at least 18," every single time, because a
licence-holder is obviously an adult. ρ = **1.0**. So the certificate reads
`floor_reaching = true` (we did everything deletion can do) but
`completeness_certified = false` (the world already knows) → status **INCOMPLETE**.
Same machine, same effort, honest and different verdict. That contrast *is* the paper's
limit result.

---

## 9. The parametric floor: the hard limit of deletion

This deserves its own section because it's the paper's most important scientific
result — its "limit result."

**The claim:** some facts can be recovered from **general world knowledge alone**, so
**no deletion from the store can ever certify them as erased.** We don't just assert
this — we **measure** it, across a spread of facts chosen to range from "impossible to
guess" to "obvious from context."

### How we measure ρ (experiment exp07)

We wrote **250 facts** spread across a difficulty gradient:

- **Low tier** — arbitrary secrets: locker PINs, Wi-Fi passwords. Expect **ρ ≈ 0**
  (no one can guess a random PIN).
- **Mid tier** — loosely implied: occupation → rough income range. Expect ρ somewhere
  in the middle.
- **High tier** — nearly forced by context: "Class-3 licence" → "at least 18",
  "national service" → "male". Expect **ρ ≈ 1** (the world basically tells you).

For each fact, we withhold the store entirely, ask the model for the value **8
times**, and record how often it gets it. That fraction is ρ. We do this with **four
adversary models** and keep the **worst (highest)** ρ for each fact — because in
security you certify against the strongest attacker, not the average one.

### The headline result

Sorting all 250 facts by their worst-case ρ (Table `tab:rho` in the paper):

| Worst-case ρ | Meaning | # of facts | Certifiable? |
|---|---|---|---|
| ρ ≤ 0.1 (= τ) | certifiable floor | **164** | ✅ yes |
| 0.1 < ρ < 0.5 | intermediate band | **41** | ❌ no |
| ρ ≥ 0.5 | hard floor | **45** | ❌ no |
| **total** | | **250** | **164 certifiable** |

So **86 of 250 facts cannot be certified as erased** (41 + 45) — *even though their
residual is 0 and every rebuild path was closed*. That's the limit result: **once a
value is inferable from world knowledge no one can delete, no co-deletion can certify
its erasure.**

### Two important nuances (don't miss these for the paper)

1. **The floor is a gradient, not a clean on/off.** There's a **41-fact intermediate
   band** (0.1 < ρ < 0.5) sitting between "certifiable" and "hopeless." That means the
   count of uncertifiable facts **moves with τ**. So **τ is a policy dial**: choosing
   τ = 0.1 is literally choosing "how much residual world-guessability am I willing to
   tolerate?" (An earlier, smaller version of the data happened to look perfectly
   bimodal / all-or-nothing; the larger data shows it's actually a smooth gradient. Use
   the gradient framing — it's both more honest and more defensible.)

2. **Stronger AI models are not uniformly stronger adversaries.** On *benign* facts,
   the frontier models (GPT-5.5, Sonnet 5) rebuild more — they're the worst case. But
   on *sensitive* facts (national service → sex, licence → age), the frontier models
   often **refuse** to answer for safety reasons. A refusal makes their measured ρ an
   **underestimate**. So on sensitive facts the older `gpt-4o` (which refuses less)
   ends up being the worst adversary. This is exactly why we use a **panel of four
   models and take the worst per fact** — no single model is worst everywhere. (There
   were **30 refusal flags** in the data, all landing on the sensitive high-tier
   facts by authored tier, which is the clean pattern you'd expect from genuine safety
   refusals rather than hidden rate-limit errors.)

### A note on trusting the refusal count

A quiet danger in an experiment like this: a network timeout or rate-limit could look
like a "refusal" and silently deflate ρ (making a fact look *more* erasable than it is).
We hardened the probe (`probes/parametric_probe.py`) so that **only a genuine
content-policy refusal counts**; a timeout or rate-limit **re-raises** the error
instead of being miscounted. The verifier then confirmed the refusals land only where
sensitive-content refusals should — so the ρ numbers aren't a concurrency artifact.

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
(irreducible)* — is the spine that ties the framework together. If you can delete the
thing the world-knowledge attaches to, it's Channel 2; if the world-knowledge attaches
to something you can't delete (the person's own obvious attributes), it's Channel 3.

---

## 10. The three memory systems we tested

We tested the whole idea on **three real, popular AI-memory systems**, each built on
a **completely different architecture**. The point: residual survival shows up in
**all three**, but through a **different by-design mechanism** each time. That's the
"generalization" evidence — the problem isn't one system's bug, it's a property of
how agent memory works. If three systems that share almost no design choices all leak,
the leak is about the *idea* of agent memory, not one team's implementation.

All three sit behind one common interface (`MemorySystemAdapter` in `systems/base.py`),
so the exact same probes/planner/certificate run on all of them — you only swap the
adapter. (This is a real engineering payoff: adding a fourth system would mean writing
one adapter and changing nothing else.)

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
  summaries. (A good example of an empirically-corrected assumption, and worth telling
  honestly: our first hypothesis was reasonable and still wrong.)

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
  path. We tested exactly the path they skipped, which is also the path a real
  deployment actually uses.

### The four adversary "reasoner" models

Wherever recovery depends on reasoning (channels 2 and 3), we test against a **panel
of four models** and take the **worst-case**:

1. `gpt-4o-mini` — small, older (also the *primary* reasoner and the pinned
   *reproducibility anchor* for the recovery judge).
2. `gpt-4o` — bigger, older (also the pinned *reproducibility anchor* for the
   entailment judge).
3. **Claude Sonnet 5** — frontier (also the **production recovery *and* entailment
   judge** — our smartest model, validated on the gold set).
4. **GPT-5.5** — frontier.

Sonnet 5 is deliberately **both an adversary and the production judge** — an accepted
overlap. What makes that sound is *not* keeping the judge on separate API calls (a
model's errors are correlated even across calls) but **gold-validation**: the judge is
validated against a ground-truth-by-construction gold set to ~0% false-accept, so it
scores reliably no matter which adversary produced the answer. Because Sonnet 5 is a
rolling alias with no dated snapshot, we retain the pinned `gpt-4o-mini`/`gpt-4o` judge
numbers as a **reproducibility anchor** (and record the access date). Fact-authoring is
still kept off the frontier models to avoid a model grading its own written facts.

### One-glance summary of the three-family convergence

| Family | System | The leak mechanism (by design) | Headline |
|---|---|---|---|
| Dedup pipeline | **Mem0** | silent **duplication** (paraphrase copies) | 97.2% residual → 0% when artifact-aware |
| Bi-temporal KG | **Graphiti** | **stale summaries** (not recomputed on delete) | edge 20% residue, but **83%** summary residue |
| LLM-paging agent | **Letta** | agent scrubs core, **misses archival** | **0% faithful / 100% archival** on vague request |

---

## 11. Every experiment, in plain words

There are **12 experiments** (exp01–exp12) plus a judge-validation run. Here's each
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
**Result: 97.2% → 0%.** Cleaning up all copies fully closes Channel 1. (Both the
duplication and extraction counts land on ~97–98% independently — a small built-in
replication.)

### exp03 — Can the planner close re-derivation with minimal collateral? *(Mem0)*
Run the full exact planner on all 298 multi-hop targets.
**Result: 100% completeness, 0 spurious bystander deletions, mean k = 1.03** (467
operands spared by only deleting what's needed). The dumb comparator (depth-first) also
reaches 100% but at k = 6.60 with 1192 spurious deletions. **Knowing the recipe graph
is what keeps it minimal and selective.**

### exp04 — Is re-derivation real, and does co-deletion close it? *(Mem0)*
The clean "operands-only control": inject the *ingredients* but **never store the
target value**, so residual is 0 by construction. Whatever the model recovers, it
recovered by *reasoning*. Bin the targets into **bin1 (stored-alone: ingredients
suffice)** and **bin2 (stored+world: need world knowledge too)**.
**Result:** bin1 re-derives at **97–100%**, bin2 at **62 / 69 / 69 / 66%** (mini /
gpt-4o / Sonnet 5 / GPT-5.5). After co-deleting the operands, bin1 drops to **0%** and
bin2 to **~2.7%** — essentially zero, but not a perfect zero: one stubborn fact (F043)
that all four reasoners still occasionally guess even after its modeled ingredients are
gone. It's an honest near-zero, and a small reminder that the planner can only close
the rebuild paths it actually knows about (see Section 17). ρ throughout = 0. Note the
worst re-derivers are **gpt-4o / Sonnet 5 (69%)** — the certificate is built against
whichever reasoner is strongest per fact. A special **multi-level set**
(where the target's direct ingredients are *themselves* unstored and must be traced to
deeper roots) re-derives at **100% → 0%**, proving the planner recurses to the real
roots, not just one hop.

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
keep to stay defensible — see Section 17.)

### exp07 — What is the parametric floor ρ, across difficulty tiers? *(base model)*
Withhold the store, ask the model for each of 250 facts 8 times, four adversaries, keep
the worst ρ per fact. (Full detail in Section 9.)
**Result: 164 certifiable / 41 intermediate / 45 hard-floor → 86 of 250 cannot be
certified erased at τ = 0.1.** The floor is a **gradient**, so τ is a policy dial.
The measured band disagrees with the *authored* difficulty tier on 77/250 facts (we
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
request, with the fact present in both core and archival. (n = 30 sensitive-PII
targets.)
**Result: explicit → 100% faithful; vague → 0% faithful, 100% archival residue, 10%
core residue.** The agent almost always clears the surface it reasons over (core) and
*always* misses the other (archival); in a minority of cases it doesn't even fully
clear core. The **explicit baseline (100%) proves it's a phrasing/surface-coverage
problem, not a missing capability.** This is the paper's hook.

### exp11 — Does the re-derivation channel and planner port to Letta? *(Letta/MemGPT)*
Repeat exp04's operands-only control on a totally different system — now at **full 298
scale across every topology**, up from an earlier n = 40.
**Result: bin1 99–100%, bin2 62/65/65/68% (mini/4o/Sonnet 5/GPT-5.5) → 0% after
co-delete; all 5 structured topologies 100% → 0%; ρ = 0; faithful direct co-delete
100%; bystanders intact 100%.** The framework ports unchanged, and running the full 298
(all topologies) fixes the earlier "cross-system n is modest" limitation. (Co-deletion
here uses the *direct, verified* `passages.delete`, not the agent — so "re-derivation
closed" can't be confused with "the delete didn't run," keeping this cleanly separate
from exp10.)

### exp12 — Is the planner *provably* minimal, or just small? *(Mem0)*
Measure each strategy's collateral k against the **ground-truth optimum k\*** (the
smallest possible correct co-deletion) for every topology, and report the **gap**.
**Result: exact gap ≈ 0** (−0.067: optimal, **≤ 0 on every topology** — provably
minimal — and occasionally below k\* when the residual purge closes the channel with no
ingredient deletion needed); **threshold gap ≈ 0** (+0.037: essentially optimal);
**depth-first gap +5.50** (k = 6.60, 1192 spurious — it over-deletes ~6×). This is the experiment that turns "minimal" from a claim into a
measurement: the exact planner really does spend the fewest deletions possible, and the
brute-force baseline really does pay 6× for the same result.

### Judge validation — are our two AI judges trustworthy?
Two judges do load-bearing work: the **recovery judge** (did this answer recover the
value?) and the **entailment judge** (do these facts entail the target?).
**Result:**
- **Recovery judge (n = 351 gold, 22 curated hard cases — up from 6): the production
  judge false-accepts 0%** — the production judge **Claude Sonnet 5** and GPT-5.5 each
  false-accept **0** on this larger, harder gold; the pinned anchors are gpt-4o **0.52%**
  and gpt-4o-mini **2.06%** (gpt-4o-mini slipped upward on the harder cases). The
  production judge essentially never says "recovered" when it wasn't → **every leak rate
  we report is a lower bound**, with the pinned anchors bounding the residual slack at
  ~0.5–2%. The load-bearing defense is **gold-validation** — the judge is validated to
  ~0% false-accept against a ground-truth gold set — not model separation; the pinned
  **gpt-4o-mini/gpt-4o** are retained as the **reproducibility anchor** (Sonnet 5 has no
  dated snapshot).
- **Entailment judge (n = 1370 pairs): multi-hop miss-rate = 0 for all four models** —
  the safety-critical result the whole method depends on: no model ever *loses* a true
  entailer. On curated near-misses (the over-detection axis) false-fire is Sonnet 5
  **3.4%**, GPT-5.5 **30.5%**, gpt-4o **45.5%**, gpt-4o-mini **75.7%**. The production
  judge is **Claude Sonnet 5** — the lowest false-fire of all and validated on the gold
  set; the pinned **gpt-4o** is retained as the reproducibility anchor.
  Crucially, the planner co-deletes by the **known entailment DAG**, not this judge, so a
  judge's false-fire never inflates the planner's k.

### A note on exp08's history (a credibility asset, not a weakness)
An early version reported a membership signal at only **n = 6** — badly underpowered.
We **retracted it**, re-ran properly at **n = 253**, and reported the nuanced result
above. Showing "we caught our own mistake and fixed it" is used in the paper's
Limitations as a sign of rigor. (Reviewers trust a paper that visibly polices itself.)

---

## 12. The numbers cheat-sheet

Everything you might want to cite, in one place. (Ground truth = the large-scale run;
τ = 0.10; four adversaries = gpt-4o-mini, gpt-4o, Claude Sonnet 5, GPT-5.5.)

**Datasets**
- Isolated PII facts: **253**
- Multi-hop facts: **298** (6 topologies: flat/join/chain/or_and/diamond/threshold)
- Context facts: **963** (775 entailing operands + 188 bystanders)
- ρ-gradient facts: **250** (low/mid/high tiers, 116 distinct subjects)

**Residual survival (Channel 1) — exp01/02, Mem0**
- Naive single-record delete: **97.2%** residual (246/253) [Wilson 94.4–98.7]
- Artifact-aware delete: **0%** [0–1.5]
- Duplication incidence (exp05): **80–82%**, row-inflation **×1.75–1.82**, in all 4 cells

**Re-derivation (Channel 2) — exp04 (Mem0) / exp11 (Letta)**
- bin1 stored-alone: **97–100%** → **0%** after co-delete
- bin2 stored+world (Mem0): **62 / 69 / 69 / 66%** (4 adversaries) → **~2.7%** (F043 near-zero)
- bin2 stored+world (Letta, full 298): **62 / 65 / 65 / 68%** → **0%**
- 5 hard topologies (join/chain/or_and/diamond/threshold): **100%** → **0%**
- ρ throughout: **0** (fictional subjects)

**The planner (Tool 1) — exp03 / exp12, Mem0**
- Completeness: **100%** [Wilson 0.96–1.0]
- Spurious bystander deletions: **0**
- Mean collateral: **exact k = 1.03** [0.98–1.08]; **467** operands spared
- Comparators: threshold **k = 1.14** (0 spurious); depth-first **k = 6.60**, **1192** spurious
- Minimality vs optimum k\* (exp12): exact gap **≈0** (−0.067, optimal, ≤0 every topology); threshold **+0.037**; depth-first **+5.50**

**Parametric floor (Channel 3) — exp07, base model**
- **86 of 250** facts uncertifiable at τ = 0.1 (41 intermediate + 45 hard-floor)
- 164 certifiable
- 77/250 measured band ≠ authored tier; 30 refusal flags (all high-tier by authored tier); 0 errors

**Membership inference — exp08, Mem0 (n = 253 members + 759 twins)**
- Intact AUC **0.66** (p = .001) — power sanity
- Naive AUC **0.66** (p = .001) — significant leak
- Artifact-aware AUC **0.51** (CI [0.498, 0.523] incl. 0.5; p = .04) — attenuated

**Cross-system — exp09/10**
- Graphiti: edge **20%**, summary **83%** residue (n = 30)
- Letta: faithful vague-delete **0%**; core residue **10%** / archival **100%** (n = 30)

**Judges** (production = **Claude Sonnet 5**; pinned gpt-4o-mini/gpt-4o = reproducibility anchor)
- Recovery false-accept on gold (n = 351, 22 curated): gpt-4o-mini **.0206**, gpt-4o **.0052**,
  Sonnet 5 **0**, GPT-5.5 **0**
- Entailment multi-hop miss-rate: **0** (all 4 models, n = 1370 pairs); near-miss false-fire
  Sonnet 5 **3.4%**, GPT-5.5 **30.5%**, gpt-4o **45.5%**, gpt-4o-mini **75.7%**

---

## 13. Glossary — every term and symbol

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
| **Parametric** | Stored in the model's trained weights (parameters), as opposed to in the memory store. |
| **Operands** | The surviving "ingredient" facts that make re-derivation possible. |
| **Bystanders** | Innocent facts the planner must NOT delete. Deleting one = a "spurious" deletion. |
| **Co-deletion** | Deleting operands (extra facts) to close the re-derivation channel. |
| **Collateral k** | How many extra facts were co-deleted. The "price" of erasure. Lower is better. |
| **Optimum k\*** | The provably smallest correct co-deletion for a fact. The planner's k is measured against it. |
| **Gap** | k − k\*: how far a strategy is from optimal. Exact ≈ 0; depth-first ≈ +5. |
| **τ ("tau")** | The tolerance threshold, 0.10. Below it = "channel closed." Also a policy dial. |
| **Entailment** | "These facts logically imply the target." Detected by an LLM judge, recorded in the DAG. |
| **Entailment DAG** | The little boolean formula (recipe map) for how a fact can be rebuilt. The planner's source of truth. |
| **Minimum Hitting Set** | The smallest set of facts that "hits" (breaks) every rebuild recipe. Our co-deletion problem is exactly this. |
| **Exact / Threshold / Depth-first** | The three planners: exact (min hitting set, the method), threshold (greedy re-probe, comparator), depth-first (brute force, comparator). |
| **floor_reaching** | Certificate flag: both deletable channels closed (residual = re-derivation = 0). Always achievable. |
| **completeness_certified** | Certificate flag: floor-reaching AND ρ < τ. Not always achievable. |
| **The limit result** | floor_reaching = true but certified = false: as erased as possible, yet still world-inferable. |
| **Opt-P2E2** | The optimization problem: minimize k while closing re-derivation. NP-hard. |
| **NP-hard** | Computationally hard in general → but our DAGs are small, so we solve the exact minimum on each. |
| **infer=True / infer=False** | Mem0 mode: True = extract & merge facts (realistic); False = store verbatim (controlled experiments). |
| **bin1 / bin2** | Re-derivation bins: stored-alone (operands suffice) vs stored+world (need world knowledge too). |
| **Operands-only control** | The clean test: inject ingredients but never the target value, so residual = 0 by construction. |
| **AUC** | Attack accuracy for membership inference. 0.5 = random guessing (good/safe), 1.0 = perfectly leaky. |
| **MIA** | Membership Inference Attack — can you tell if a fact was ever stored? |
| **REDACT** | The framework name: Recoverability Decomposition and Auditable Co-Deletion. |

---

## 14. How the code is organized

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
    parametric_probe.py    (Channel 2 re-derivation AND Channel 3 ρ; refusal-hardened)
    paraphrase_probe.py    (residual-by-implication, auxiliary)
    membership_inference.py(the MIA / AUC probe)
    kg_node_residue.py     (Graphiti summaries + edges)

planner/         — entailment_detector.py (LLM judge: does X entail the target?)
                   entailment_dag.py     (the boolean rebuild-recipe DAG — source of truth)
                   optimizer.py          (heuristic_exact = min hitting set [the method];
                                          threshold + depth_first = comparators)

certificate/     — schema.py (the DeletionCertificate object) + emitter.py (build/save)

evaluation/      — judge.py (validate the two judges across all 4 models; production
                   judge = Claude Sonnet 5, pinned gpt-4o-mini/gpt-4o = anchor),
                   metrics.py (recoverability=max, Cohen's kappa),
                   recovery.py (parse numbers, detect refusals), stats.py
                   (Wilson CI, bootstrap), verify_wave.py (corruption/sanity checker)

experiments/     — exp01_baseline.py ... exp12_planner_minimality.py

paper/           — the AAAI paper (deletion_completeness_aaai.tex), the separate
                   supplementary.tex, the claims ledger (CLAIMS_LEDGER.md), sample
                   certificates, and the AAAI author kit

docs/            — this document, RESULTS_3X_WAVE.md (the authoritative results file),
                   and the other explainers
```

**One design principle to remember:** the probes, planner, and certificate are
**system-agnostic**. To test a new memory system you write *one* adapter and change
nothing else. That's why the same stack runs on Mem0, Graphiti, and Letta unchanged.

---

## 15. Common confusions, answered

The questions newcomers (and reviewers) ask most, with short answers.

**"Isn't 'delete the copies' obvious? Why is this a research project?"**
Closing Channel 1 (copies) *is* mechanical — the interesting part is Channels 2 and 3.
Channel 2 needs a planner that deletes the *minimal* extra facts (delete too much and
you wreck the store; too little and the fact rebuilds). Channel 3 is a *proof of
impossibility* — showing some facts can never be certified erased. Neither is obvious,
and prior audits check none of it.

**"If ρ can't be fixed, why measure it?"**
Because honesty needs a number. Without ρ, a system would keep claiming "deleted" for
facts that are trivially re-guessable, and nobody could tell the difference. Measuring
ρ is what lets the certificate say "we did everything deletion can do, and it still
isn't enough" — which is exactly the information a privacy officer needs to decide
*not to store the fact in the first place*.

**"Why four models instead of just the best one?"**
Because no single model is the worst-case adversary everywhere. Frontier models rebuild
more on benign facts but *refuse* on sensitive ones (which understates their ρ). Older
`gpt-4o` refuses less, so it's the worst adversary on sensitive facts. Taking the worst
of four *per fact* gives a genuine worst-case rather than an accidental one.

**"Why use the newest, smartest model (Sonnet 5) as the judge — isn't that circular,
since it's also an adversary?"**
We now *do* use our smartest model as the judge, and the circularity is defused not by
model separation but by validation. (1) An LLM-as-judge should be as capable as
possible, and on the gold set Sonnet 5 is the best judge (0% recovery false-accept,
3.4% entailment false-fire, 0 multi-hop miss). (2) The guarantee is **gold-validation**:
the judge is validated against a ground-truth-by-construction gold set to ~0%
false-accept, so it scores reliably regardless of which adversary produced the answer —
"separate API calls are independent" was never the real defense (a model's errors are
correlated even across calls). (3) The one genuine cost is reproducibility —
"sonnet-5"/"gpt-5.5"-style names are rolling aliases with no dated snapshot — so we
retain the pinned `gpt-4o-mini`/`gpt-4o` judge numbers as a **reproducibility anchor**
and record the access date.

**"Does k = 1.03 mean the planner sometimes deletes nothing?"**
Yes — and that's good. k is an average. Many facts need one co-deletion, some need
none (the residual purge already closed them), and the hardest topology needs two. The
planner pays exactly what each fact requires.

**"Are these real users' data?"**
No. Every subject is a fictional, Singapore-plausible persona, generated on purpose so
that (a) there's no real PII, and (b) for the salary-style facts the world-knowledge
channel is inert (ρ = 0 by construction), which cleanly isolates the *deletable*
channel from the *irreducible* one.

**"Is a 'complete' certificate a guarantee the fact is gone forever?"**
It's a guarantee against the adversary we model: reads the whole surviving store,
queries the model, knows world facts. It is *not* a guarantee against an entailment
path we never modeled (see Section 17, point 8) or against future models that know more.
That's why the certificate states its assumptions rather than promising the impossible.

---

## 16. The paper's argument, in order (for your rewrite)

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
2. A **minimal co-deletion planner** for the resulting NP-hard problem — an **exact
   minimum-hitting-set solver** over the entailment DAG that reaches 100% completeness
   at mean **k = 1.03** with **0 spurious** deletions (verified minimal against the
   ground-truth optimum in exp12, gap ≈ 0) — plus an **auditable certificate** separating
   what deletion achieved from what it cannot.
3. A **measured** parametric floor and its **limit result**: under the strongest
   adversary, **86/250 facts cannot be certified erased** even at zero residual.
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
- **§4 Method** — the concrete components: probe battery, entailment detector, boolean
  entailment DAG, exact planner (+ threshold/depth-first comparators), certificate
  emitter.
- **§5 Experiments** — results in *decreasing order of confidence*: planner (5.1), ρ
  floor (5.2), re-derivation (5.3), three-family convergence (5.4), residual +
  duplication (5.5), judge validation (5.6).
- **§6 Limitations** — leads with the MIA "retracted → re-ran" story (a credibility
  move), then: judges are imperfect, ρ is a lower bound (refusals), the planner needs
  a known entailment graph, and cross-system evidence is still partly modest (the
  KG-residue and Letta-faithfulness checks are n = 30, though the Letta re-derivation
  port is now full-298).
- **§7 Conclusion** — the broad implication: when ρ ≥ τ, *no* store deletion can
  erase the fact; RTBF compliance then means **not storing it** or **disclosing the
  floor**.

**Style notes (from prior guidance):** the paper deliberately uses **plain language**,
motivation-first prose (like the LLM2CLIP paper you like), few inline numbers in the
main text (granular per-model numbers live in the separate `supplementary.tex`), and
no "Remark" blocks. The main §5 carries only headline numbers. When rewriting, keep
that: **lead with the idea and the example, push the granular tables to the
supplement.** And never change a number — every figure here is load-bearing and tied
to a specific result file. (The authoritative numbers live in `docs/RESULTS_3X_WAVE.md`;
this document is kept in sync with it.)

---

## 17. Things we deliberately do NOT claim

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
   At n = 253 the AUC is 0.51 with the CI just including 0.5 and a marginal p = .04. The
   honest claim is "sharply reduces, does not provably eliminate."

7. **We do NOT claim the ρ floor is bimodal / all-or-nothing.** The large data shows a
   **gradient** with a 41-fact intermediate band. τ is a policy dial. (An earlier
   smaller run looked bimodal — that framing is retired.)

8. **The planner assumes the entailment graph is known.** In our controlled setup we
   injected the operands ourselves, so we know them. In a real deployed store you'd
   have to *discover* the graph, which is hard and unsolved. An unmodeled entailer
   stays open — which is exactly the residue we see on fact F043 in exp04. State this
   as a limitation, not a solved problem.

9. **Residual matching is value-based and subject-agnostic (deliberately conservative).**
   The residual probe and artifact-aware deletion match on the *value's surface forms*,
   not on the subject. So if two genuinely different facts share a value — "Alice's
   salary is $x" and "Alice's *parent's* salary is $x" — the probe flags **both** as
   residual and artifact-aware deletion removes **both**. This is intentional: the
   residual channel is the model-free, never-miss-a-copy guarantee, and over-flagging is
   the safe direction. The cost is possible over-deletion on a value *collision*; the
   datasets avoid it by giving each target a unique probe value. The same value-coupling
   also explains the exact planner's occasional +1: when an operand *itself* carries a
   surface form of the target value (F040's pay-band fact literally states "8,000–9,000"),
   deleting the *other* operand doesn't close the channel, and the planner's safety
   fallback removes the value-carrying operand too. Completeness is never at risk; the
   effect is a small minimality gap, which exp12 quantifies as ≈ 0. Frame "provably
   minimal" as **minimal with respect to the modeled entailment DAG**, not an absolute.

---

*That's the whole project. If you've read this far, you now know: the problem
(deleting a record ≠ erasing a fact), the three channels (residual, re-derivation,
parametric floor), the two tools (planner + certificate), a full run on one fact, the
hard limit (ρ), the three systems (Mem0, Graphiti, Letta), every experiment and number,
and exactly what to claim and not claim. You're ready to re-write the paper in your own
words.*
