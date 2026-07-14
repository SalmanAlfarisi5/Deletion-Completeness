# Comparative analysis: how model strength changes deletion outcomes

**Status:** content scaffolding for Muhammad to rewrite in his own voice (do NOT paste
verbatim — it will read as AI). All numbers are exact from the frontier-judge wave; see
`docs/reviews/STATS_AUDIT.md`. Answers Tan's "strong vs weak / GPT vs Claude as a key
finding" and the external reviewer's "effects of stronger models" point.

## The one-sentence finding (rewrite in your voice)

A model plays **three different roles** in this pipeline, and its strength pulls each in a
different direction. The uncomfortable one: **the world recall is not a fixed property
of a fact — it is whatever the strongest available adversary can reconstruct**, so "certified
erased" is inherently relative to model capability, and a stronger future model is a standing
risk. That reframes world recall as a *boundary condition*, not a tautology.

## The three roles (the spine of the section)

| Role | What model strength does | Direction |
|---|---|---|
| **Adversary** (re-derives the deleted fact) | stronger → recovers *more* from surviving facts and from world knowledge | raises the erasure bar |
| **Entailment judge** (finds the co-deletion targets) | stronger → fewer false-fires, so a judge-driven planner over-deletes less | sharpens the planner |
| **Recovery judge** (scores whether a leak happened) | stronger → higher recall + zero false-accept, so the reported leak rates are tighter, more honest lower bounds | sharpens the measurement |

## Axis 1 — model as adversary (world recall moves with capability)

Re-derivation of bin-2 (stored+world) facts *before* co-deletion, and the world recall ρ
on the hardest tier — both measured per reasoner:

| Reasoner | bin-2 re-derivation | ρ (mid tier) | ρ (high tier) |
|---|---|---|---|
| gpt-4o-mini | 62.2% | 0.072 | 0.482 |
| gpt-4o | 68.9% | 0.118 | **0.661** |
| Claude Sonnet 5 | 68.9% | 0.077 | 0.577 |
| GPT-5.5 | 66.2% | 0.125 | 0.333 |

**Honest reading (do not overclaim monotonicity):** world recall is *model-specific*, not a clean
"bigger = higher" line — gpt-4o has the highest high-tier world recall, GPT-5.5 the lowest. Different
frontier models reconstruct *different* facts. That variance is exactly the argument for
certifying against the **worst of a panel** (the sup in your threat model), and for treating
world recall as capability-relative rather than fixed. **This is the non-tautological core:** the
question is not "can a model infer public facts" (of course it can) — it is "how much
recoverability did *storing the fact* add, and does that survive the strongest adversary."

**Use the context-lift you already measure.** Every logged answer records
`context_lift = ρ_context − ρ_baserate` (recovery *with* the store minus recovery from base
rate alone). Feature this: it isolates the recoverability that storage *created*, which is the
only part deletion can be blamed for. This directly answers the reviewer's "tautology" worry.

## Axis 2 — model as entailment judge (near-monotone; motivates Sonnet 5)

| Judge | near-miss false-fire (lower better) | multi-hop miss (safety) |
|---|---|---|
| gpt-4o-mini | 75.7% | 0% |
| gpt-4o | 45.5% | 0% |
| GPT-5.5 | 30.5% | 0% |
| **Claude Sonnet 5** | **3.4%** | 0% |

All four **never miss a true entailer (0%)** — the safety property. They differ only in
over-firing on partial operands. In a *judge-driven* planner, over-firing inflates collateral k
and causes spurious bystander deletions. Concretely, the aggressive comparator's cost is judge-
sensitive; the **exact planner is immune** because it co-deletes over the known DAG, not the
judge (k=1.03, 0 spurious, judge-independent). So: **model strength matters for the deployable
planner, but structure-awareness removes the dependency** — a clean "here's why our design is
robust" point.

## Axis 3 — model as recovery judge (near-monotone; measurement honesty)

| Judge | false-accept (lower better) | recall (higher better) |
|---|---|---|
| gpt-4o-mini | 2.06% | 75.2% |
| gpt-4o | 0.52% | 93.0% |
| Claude Sonnet 5 | **0%** | **98.1%** |
| GPT-5.5 | 0% | 98.1% |

A weak recovery judge **misses leaks** (recall 75%) — it would make deletion look *better* than
it is. The strong judge (0% false-accept on 194 negatives, 98% recall) is why every reported
leak rate is a conservative **lower bound**. This is the measurement-validity leg the reviewer
demanded.

## Where it goes in the paper

- New short subsection in Results (or fold into the judge section), titled around "model
  strength cuts three ways," with the three tables condensed to one.
- Cross-reference from the Limitations: world recall's capability-relativity *is* the honest
  statement of "we can't certify against models we haven't run."
- Cite it in the intro contributions as an operational finding, not a theorem.
