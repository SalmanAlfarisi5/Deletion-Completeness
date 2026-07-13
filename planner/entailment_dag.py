"""planner/entailment_dag.py -- boolean entailment structure over stored operands.

THE SINGLE SOURCE OF TRUTH for "which surviving facts let a deleted target be
re-derived, and what is the minimal co-deletion that closes that channel."

Every STRUCTURED multi-hop fact (the flat 2-operand cases and the harder join /
chain / or_and / diamond / threshold topologies) carries an ``entailment_dag``::

    {
      "leaves":   {"A": "C301", "B": "C302", "C": "C303"},  # label -> stored context id
      "formula":  {"op": "AND", "args": [{"op": "OR", "args": ["A", "B"]}, "C"]},
      "topology": "or_and",
      ...
    }

``formula`` is a boolean tree over LEAF LABELS describing when the target is still
RE-DERIVABLE: the target can be recovered iff ``formula`` evaluates ``True`` over the
set of surviving leaf labels. Deleting a set ``D`` of leaves closes the re-derivation
channel iff the formula is ``False`` once those leaves are gone. The MINIMAL
co-deletion is therefore a **minimum hitting set** of the formula -- exactly the
NP-hard Opt-P2E2 objective (see the paper's Prop. 1). The DAGs used here are tiny
(<=6 leaves), so we solve it exactly by brute force.

Node grammar (a node is one of):
  * a leaf label ......................... ``"A"``            (survives iff in the set)
  * conjunction .......................... ``{"op": "AND", "args": [n, ...]}``
  * disjunction .......................... ``{"op": "OR",  "args": [n, ...]}``
  * threshold (>= k of the args survive) . ``{"op": "ATLEAST", "k": 2, "args": [n, ...]}``

Because this structure is KNOWN by construction, the planner co-deletes by the true
recursion to the stored roots and can never silently miss a multi-hop entailer just
because an LLM judge failed to rediscover the path. The LLM entailment judge is
validated *against* this ground truth (evaluation/judge.py), not trusted blindly.
"""
from __future__ import annotations

from itertools import combinations

Node = "str | dict"


def leaf_labels(node: Node) -> set[str]:
    """All leaf labels appearing in a formula."""
    if isinstance(node, str):
        return {node}
    out: set[str] = set()
    for a in node["args"]:
        out |= leaf_labels(a)
    return out


def evaluate(node: Node, surviving: set[str]) -> bool:
    """Is the target still re-derivable given the set of surviving leaf labels?"""
    if isinstance(node, str):
        return node in surviving
    op = node["op"].upper()
    args = node["args"]
    if op == "AND":
        return all(evaluate(a, surviving) for a in args)
    if op == "OR":
        return any(evaluate(a, surviving) for a in args)
    if op == "ATLEAST":
        k = int(node["k"])
        return sum(1 for a in args if evaluate(a, surviving)) >= k
    raise ValueError(f"unknown op {op!r} in entailment formula")


def is_hitting_set(formula: Node, deleted: set[str]) -> bool:
    """True if deleting ``deleted`` (a set of leaf labels) makes the target
    un-re-derivable, i.e. closes the re-derivation channel."""
    return not evaluate(formula, leaf_labels(formula) - deleted)


def min_hitting_sets(formula: Node) -> list[frozenset[str]]:
    """Every MINIMUM-size co-deletion that closes the re-derivation channel.

    Brute force by increasing size (leaves are few). Returns all sets tied for the
    minimum size, so the gates/experiments can check greedy against the true optimum
    and report ties. If the formula is already False on the full store (not a valid
    entailer) the minimum is the empty set.
    """
    leaves = sorted(leaf_labels(formula))
    full = set(leaves)
    for size in range(0, len(leaves) + 1):
        hits = [frozenset(combo) for combo in combinations(leaves, size)
                if not evaluate(formula, full - set(combo))]
        if hits:
            return hits
    return [frozenset(leaves)]


def min_codelete_size(formula: Node) -> int:
    """The minimal collateral k* = size of a minimum hitting set."""
    return len(next(iter(min_hitting_sets(formula))))


def min_hitting_set_covering(formula: Node, forced: "set[str]") -> "frozenset[str]":
    """Smallest hitting set of ``formula`` that INCLUDES every leaf in ``forced``.

    Use when some operands must be deleted regardless of the boolean structure --
    e.g. an operand whose own text carries a surface form of the target value is
    itself a residual copy, so deleting the *other* branch of an AND would leave the
    value exposed and fail to close the channel. Forcing those leaves in makes the
    exact planner pick the minimum co-deletion that is *also* residual-clean, instead
    of an equal-size hitting set that leaves a value-carrying operand behind.

    With ``forced`` empty this is exactly the plain minimum hitting set (no behaviour
    change for well-formed facts). Leaves are few, so brute force by increasing size.
    """
    forced = set(forced) & leaf_labels(formula)
    if not forced:
        return min(min_hitting_sets(formula), key=len)
    leaves = sorted(leaf_labels(formula))
    for size in range(len(forced), len(leaves) + 1):
        for combo in combinations(leaves, size):
            d = set(combo)
            if forced <= d and is_hitting_set(formula, d):
                return frozenset(d)
    return frozenset(leaves)


def single_sufficient_leaves(formula: Node) -> list[str]:
    """Leaves that ALONE re-derive the target (i.e. the formula is True when only
    that one leaf survives). These are the operands a near-miss gate expects NOT to
    exist for a well-formed multi-operand fact -- a single-sufficient leaf means one
    stored fact already gives the target away."""
    leaves = sorted(leaf_labels(formula))
    return [lf for lf in leaves if evaluate(formula, {lf})]


def formula_to_ids(formula: Node, leaves: dict[str, str]) -> "dict":
    """Return the min hitting sets expressed as context ids (not labels), using the
    dag's leaf->id map -- convenient for the planner and for logging."""
    return {
        "min_codelete_size": min_codelete_size(formula),
        "min_hitting_sets_ids": [sorted(leaves[l] for l in hs)
                                 for hs in min_hitting_sets(formula)],
    }


# --------------------------------------------------------------------------- #
# Constructors for the standard topologies (labels only; callers attach the
# leaf->id map). Keeping them here means the generator and the validator build the
# SAME formula, so ground truth is defined in exactly one place.
# --------------------------------------------------------------------------- #
def formula_flat(labels: list[str]) -> dict:
    """A ∧ B (∧ ...): every operand needed; delete any one to close (k*=1)."""
    return {"op": "AND", "args": list(labels)}


def formula_or_and(or_labels: list[str], and_label: str) -> dict:
    """((A ∨ B ∨ ...) ∧ C): delete C (k*=1) OR delete every OR-branch (|or_labels|).
    A confidence-ordered greedy that deletes the OR-branches first pays more than the
    optimum {C}, which is exactly the minimality gap this topology exposes."""
    return {"op": "AND", "args": [{"op": "OR", "args": list(or_labels)}, and_label]}


def formula_threshold(labels: list[str], k: int) -> dict:
    """(>= k of n) ⊢ T: to leave < k surviving you must delete n-k+1 (k* = n-k+1 >= 2
    for k < n). A genuine minimum hitting set larger than one."""
    return {"op": "ATLEAST", "k": k, "args": list(labels)}


def formula_chain(root_labels: list[str]) -> dict:
    """A→B→C→T via stored roots A,r1,r2,...: the net condition over the stored leaves
    is their conjunction (every root needed; delete any one to break the chain, k*=1).
    The DEPTH is what stresses transitive closure -- T's direct entailer is unstored."""
    return {"op": "AND", "args": list(root_labels)}


def formula_join(pairs: list[tuple[str, str]]) -> dict:
    """(A∧Ar)⊢B, (C∧Cr)⊢D, (B∧D)⊢T over stored leaves: conjunction of all leaves
    (delete any single leaf breaks its intermediate, hence T; k*=1)."""
    flat = [lbl for pair in pairs for lbl in pair]
    return {"op": "AND", "args": flat}


def formula_diamond(a_label: str, b_label: str) -> dict:
    """A⊢C, B⊢D, (C∧D)⊢T over stored leaves A,B: both needed, delete either (k*=1).
    Direct entailers C,D are unstored, so a one-hop planner would miss them."""
    return {"op": "AND", "args": [a_label, b_label]}


# --------------------------------------------------------------------------- #
# Packaging + a uniform accessor so EVERY multi-hop fact (structured or flat)
# exposes the same (leaves, formula). The planner, gates, and experiments call
# dag_of() and never branch on topology, so a flat canonical fact (F040) and a
# threshold fact are handled by one code path.
# --------------------------------------------------------------------------- #
def build_dag(leaves: dict[str, str], formula: Node, topology: str) -> dict:
    """Package the stored entailment_dag written onto a structured fact, including
    the ground-truth minimum hitting sets (as context ids) for validation/planning."""
    return {
        "leaves": dict(leaves),
        "formula": formula,
        "topology": topology,
        "min_codelete_size": min_codelete_size(formula),
        "min_hitting_sets_ids": sorted(
            (sorted(leaves[l] for l in hs) for hs in min_hitting_sets(formula)),
            key=lambda ids: (len(ids), ids)),
    }


def dag_of(fact: dict) -> dict:
    """Uniform (leaves, formula) for ANY multi-hop fact.

    Structured facts carry an explicit ``entailment_dag.formula``. Flat/canonical
    facts (e.g. F040 with ``entailed_by=[C001,C002]`` and no explicit dag) fall back
    to a conjunction over their operands, with the context ids doubling as leaf
    labels. Either way the caller gets ``{"leaves": {label: cid}, "formula": node}``,
    so a multi-hop entailer is never missed for lack of an explicit dag.
    """
    dag = fact.get("entailment_dag")
    if dag and "formula" in dag:
        return {"leaves": dag["leaves"], "formula": dag["formula"]}
    ops = list(fact.get("co_delete_required") or fact.get("entailed_by") or [])
    return {"leaves": {cid: cid for cid in ops}, "formula": formula_flat(ops)}


# --------------------------------------------------------------------------- #
# Self-test (run: python planner/entailment_dag.py) -- ground-truth by hand.
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    def check(name, formula, exp_size, exp_hits=None, exp_single=None):
        hs = min_hitting_sets(formula)
        size = min_codelete_size(formula)
        ok = size == exp_size
        msg = f"{name:12s} k*={size} (exp {exp_size})"
        if exp_hits is not None:
            got = {tuple(sorted(h)) for h in hs}
            want = {tuple(sorted(h)) for h in exp_hits}
            ok = ok and got == want
            msg += f"  hits={sorted(got)}"
        if exp_single is not None:
            ss = single_sufficient_leaves(formula)
            ok = ok and set(ss) == set(exp_single)
            msg += f"  single_sufficient={ss}"
        print(("  OK  " if ok else " FAIL ") + msg)
        return ok

    print("entailment_dag self-test")
    allok = True
    # flat AND(A,B): delete either; neither single suffices
    allok &= check("flat", formula_flat(["A", "B"]), 1,
                   [{"A"}, {"B"}], exp_single=[])
    # or_and ((A|B)&C): minimum is {C}, NOT {A,B}; no single leaf suffices
    allok &= check("or_and", formula_or_and(["A", "B"], "C"), 1,
                   [{"C"}], exp_single=[])
    # threshold >=2 of {A,B,C}: delete any 2; each single leaf alone is NOT sufficient
    allok &= check("threshold", formula_threshold(["A", "B", "C"], 2), 2,
                   [{"A", "B"}, {"A", "C"}, {"B", "C"}], exp_single=[])
    # threshold >=2 of {A,B,C,D}: delete any 3
    allok &= check("thresh4", formula_threshold(["A", "B", "C", "D"], 2), 3)
    # chain A,r1,r2,r3: delete any one root
    allok &= check("chain", formula_chain(["A", "r1", "r2", "r3"]), 1)
    # join (A,Ar),(C,Cr): delete any one leaf
    allok &= check("join", formula_join([("A", "Ar"), ("C", "Cr")]), 1)
    # diamond A,B: delete either
    allok &= check("diamond", formula_diamond("A", "B"), 1, [{"A"}, {"B"}])
    # value-carrier covering: flat AND(A,B) where B carries the target value -> the
    # exact planner must delete {B} (not {A}), still k*=1; and OR needs both anyway.
    _cov_and = min_hitting_set_covering(formula_flat(["A", "B"]), {"B"})
    _cov_none = min_hitting_set_covering(formula_flat(["A", "B"]), set())
    _cov_or = min_hitting_set_covering({"op": "OR", "args": ["A", "B"]}, {"B"})
    _cov_ok = (_cov_and == frozenset({"B"}) and len(_cov_none) == 1
               and _cov_or == frozenset({"A", "B"}))
    print(("  OK  " if _cov_ok else " FAIL ") +
          f"covering     forced-B->{sorted(_cov_and)}  none->{sorted(_cov_none)}  "
          f"OR-forced-B->{sorted(_cov_or)}")
    allok &= _cov_ok
    # evaluate sanity: or_and stays derivable if only A (and C) deleted-of-B? check
    f = formula_or_and(["A", "B"], "C")
    assert evaluate(f, {"A", "B", "C"}) is True          # full store: derivable
    assert evaluate(f, {"B", "C"}) is True               # lose A: B still feeds the OR
    assert evaluate(f, {"C"}) is False                   # lose A,B: OR empty
    assert evaluate(f, {"A", "B"}) is False              # lose C: AND fails
    print("\n" + ("ALL PASS" if allok else "SOME FAILED"))
    raise SystemExit(0 if allok else 1)
