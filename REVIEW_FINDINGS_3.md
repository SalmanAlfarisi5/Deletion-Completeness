# REVIEW_FINDINGS_3 — H-02: entailment "NO"-clamp fix (investigated & rejected)

**Reviewer:** Claude (fix-enabled with the number guardrail)
**Date:** 2026-07-02
**Mode:** applied the proposed one-line change, re-ran exp03 (both heuristics) live, isolated the cause with a control run, then **reverted the code to original**. Paid: 3 small exp03 runs (entailment verdicts served from `llm_cache.json`; injection + recoverability probing live). No paper number changed.

---

## 0. Lead verdict

**The proposed fix is sound in principle but empirically UNSAFE — do NOT apply.** Zeroing the confidence of a "NO" entailment verdict drops the planner's completeness from **100% → 79% (27/34) for _both_ heuristics**, because the `0.2` clamp is **load-bearing**, not noise: it keeps individually-non-entailing multi-hop _operands_ (which correctly score "NO" in isolation) in the co-deletion pool. The code is back at original (`conf = min(conf, 0.2)`); neither paper was touched.

---

## H-02 — REJECTED (do not apply): entailment "NO" clamp `0.2 → 0.0`

**Proposed change** (`planner/entailment_detector.py:50-51`):
```python
if ans == "NO":
    conf = min(conf, 0.2)      # proposed ->  conf = 0.0
```
**Rationale given:** `config.TAU = 0.10` is what `planner/optimizer.py` compares entailment confidence against (`> self.tau`, lines 101/122; `threshold_tau=config.TAU` in exp03). The clamp ceiling `0.2` sits _above_ τ, so a correctly-judged "NO" numerically passes `> τ`; the raw cache shows many `"answer":"NO"` verdicts with self-reported confidence 0.95–1.0. Hypothesized as a major contributor to `depth_first`'s spurious-bystander count.

**Blast radius (re-verified).** `EntailmentDetector` has 4 call sites; only one is affected:
- `planner/optimizer.py` (exp03): compares `entail.check() > self.tau` (= `config.TAU` = 0.10). **AFFECTED** — the intended target.
- `evaluation/judge.py:116-117`: compares `> config.ENTAILMENT_THRESHOLD` (0.50). Both 0.2 and 0.0 are `< 0.50` → **invisible, NOT affected.**
- `data/validate_facts.py:233,239-241`: compares `>= config.ENTAILMENT_THRESHOLD` (0.50) and gates on answer `YES`/`PARTIAL` (NO is excluded regardless) → **NOT affected** (also a one-time dataset gate; dataset already frozen).
- `pipeline/graph_builder.py:44`: imported by no experiment → **dead code, NOT affected.**

So re-running **only exp03** is the correct isolation — confirmed empirically below.

**Before → after (isolated; current env, H-01 judge lock in place):**

| heuristic | clamp = 0.2 (original) | clamp = 0.0 (proposed fix) |
|---|---|---|
| `threshold`   | 100% complete, k≈0.91, **0** spurious | **79%** complete, k=0.765, 0 spurious |
| `depth_first` | 100% complete, k=5.647, **126** spurious | **79%** complete, k=1.059, **0** spurious |

The `depth_first` spurious drop (126 → 0) is exactly as hypothesized — but **completeness collapses to 27/34 for _both_ heuristics**, including `threshold`, which was expected to be unaffected.

**Control (clean isolation).** Reverting _only_ the clamp back to `0.2`, same environment, H-01 lock intact, re-running `threshold`: **completeness 100%, 0 spurious, k=0.971, all 7 failed targets recovered.** So the clamp change is the _sole_ cause of the regression — not the H-01 judge lock, not Mem0/cache drift.

**Why it breaks — the clamp is load-bearing (mechanism).** The 7 failing targets — **F050, F051, F052, F053, F055, F068, F070** — are multi-hop facts whose completion requires co-deleting a **ground-truth operand** (`operands_required_set` e.g. `[C031, C032]`; the planner deletes just `C031` by minimality). The entailment judge _correctly_ scores a **single** operand as **"NO"** — one operand of a two-operand chain genuinely does not entail the target on its own. The `0.2` clamp floats that "NO" to `0.2 > τ=0.10`, keeping the operand in the co-deletion pool; deleting it breaks the re-derivation chain (→ recoverability 0). Zeroing "NO" removes these necessary operands → the planner co-deletes **nothing** for those targets → `final_recoverability = 1.0`, incomplete. (Confirmed: for 6/7 targets the committed run co-deleted `[Cxxx]` and was complete; the fixed run co-deletes `[]` and is incomplete.)

**The premise was half-right, but the fix over-corrects.** The `0.2` clamp _does_ inflate `depth_first`'s 126 spurious: `depth_first` co-deletes _every_ candidate `> τ`, so it also sweeps in true bystanders sitting at 0.2. But `threshold` already avoids that (0 spurious) via descending-confidence ranking + a recoverability early-exit — genuine operands resolve completeness first and the loop stops before reaching noisy candidates. That `threshold` (0.91/0) vs `depth_first` (5.65/126) contrast _is_ the planner section's result. Confidence alone cannot separate "spurious bystander" from "necessary operand" — **both are judged "NO"** — so zeroing "NO" deletes both from the pool, sacrificing completeness to remove the bystanders.

**Recommendation.**
- **Keep the original `0.2` clamp.** The 126 spurious is an intended property of `depth_first` as the deliberately-aggressive comparator; `threshold` already delivers the selective, 0-spurious, 100%-complete result. The clamp underpins multi-hop completeness for both.
- **Principled alternative (redesign, not a one-liner):** rank co-deletion candidates by _marginal recoverability reduction_ (an ablation/leave-one-out test on the store) rather than per-candidate solo-entailment confidence, so operands that individually score "NO" but break the chain are handled explicitly. Out of scope for a clamp tweak.

**Disposition:** code reverted to original; **`paper/deletion_completeness_aaai.tex` and `paper/supervisor_draft.tex` unchanged** (the k=5.65 / 126-spurious / k=0.91 planner numbers stand). Transient exp03 run artifacts removed so the committed 2026-06-27 logs remain the canonical result.
