"""Experiment 9 — Zep/Graphiti KG-node residual layer (cross-system).

Graphiti's explicit deletion (remove_episode) hard-deletes the episode, its
RELATES_TO edges, and orphaned entities. But a SHARED entity (kept alive by
another episode) survives with a `summary` that still states the deleted fact,
and community summaries built pre-deletion are not recomputed. Those are the
structural KG-residual channels — by design (bi-temporal/derived summaries),
distinct from Mem0's dedup-failure duplication.

Residual counts a value present in any surviving edge/summary text regardless of
its bi-temporal invalid_at/expired_at — consistent with the full-read-access
threat model (the adversary reads the whole surviving store).

Per target: inject a 'keeper' fact about the same subject + the target fact,
build communities, then remove the target episode and probe the KG for residue.

Usage:  python experiments/exp09_zep_kg_residual.py -v
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

import config  # noqa: E402
from pipeline.injector import Injector, load_facts  # noqa: E402
from probes.exact_match import ExactMatchProbe  # noqa: E402
from probes.kg_node_residue import KGNodeResidueProbe  # noqa: E402

# target (deleted) fact  +  keeper fact that shares the subject (keeps the entity
# alive). Each pair runs in its own isolated graph (per-target user_id), so a keeper
# can back several same-subject targets. Canonical pairs (curated keepers C013/C014/
# C015) are kept first; the set is then auto-scaled to --n by pairing isolated facts
# that share a subject (see select_pairs).
CANONICAL_PAIRS = [
    ("F001", "C013"), ("F004", "C013"), ("F007", "C013"), ("F010", "C013"),  # Alice Chen
    ("F008", "C014"), ("F002", "C014"), ("F005", "C014"),                    # Bob Tan
    ("F003", "C015"), ("F009", "C015"), ("F012", "C015"),                    # Carol Lim
]


def select_pairs(iso: dict, store: dict, n: int) -> list:
    """(target_id, keeper_id) pairs sharing a subject. Canonical curated pairs first,
    then auto-pair isolated facts grouped by subject (keeper = another isolated fact
    about the same person, guaranteeing a shared entity node)."""
    pairs = [(t, k) for t, k in CANONICAL_PAIRS if t in iso and k in store]
    seen = {t for t, _ in pairs}
    by_subj: dict[str, list[str]] = {}
    for fid, f in iso.items():
        by_subj.setdefault(f["subject"], []).append(fid)
    for _subj, fids in by_subj.items():
        if len(pairs) >= n:
            break
        if len(fids) < 2:
            continue
        keeper = fids[0]
        for t in fids[1:]:
            if len(pairs) >= n:
                break
            if t not in seen:
                pairs.append((t, keeper))
                seen.add(t)
    return pairs


def main() -> None:
    ap = argparse.ArgumentParser(description="Zep/Graphiti KG-residual")
    ap.add_argument("--no-communities", action="store_false", dest="communities",
                    default=True, help="skip community build (default: build them)")
    ap.add_argument("--n", type=int, default=30, help="shared-subject pairs (enlarged from 10)")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()
    if config.validate():
        raise SystemExit("Config not ready:\n  - " + "\n  - ".join(config.validate()))

    iso = {f["id"]: f for f in load_facts(config.FACTS_DIR / "isolated_facts.json")}
    ctx = {c["id"]: c for c in load_facts(config.FACTS_DIR / "context_facts.json")}
    store = {**ctx, **iso}
    PAIRS = select_pairs(iso, store, args.n)
    print(f"KG-residual on {len(PAIRS)} shared-subject pairs")

    from systems.zep_adapter import ZepGraphitiAdapter
    adapter = ZepGraphitiAdapter()
    injector = Injector(adapter)
    exact, kg = ExactMatchProbe(), KGNodeResidueProbe()

    rows = []
    for target_id, keeper_id in PAIRS:
        target, keeper = store[target_id], store[keeper_id]
        uid = f"{config.USER_ID_PREFIX}_zep_{target_id}"
        adapter.delete_all_memories(uid)
        # keeper first (creates the shared entity), then the target fact
        inj = injector.inject_many(uid, [keeper, target], settle_seconds=0.0)
        if args.communities:
            try:
                adapter.build_communities(uid)
            except Exception as e:  # noqa: BLE001
                print(f"  build_communities warn: {repr(e)[:80]}")

        before_edge = exact.run(adapter, uid, target).score          # value in an edge?
        before_kg = kg.run(adapter, uid, target)

        episode_uuids = inj[target_id]["memory_ids"]                  # remove the target episode
        for ep in episode_uuids:
            adapter.delete_memory(uid, ep)

        after_edge = exact.run(adapter, uid, target).score
        after_kg = kg.run(adapter, uid, target)
        row = {"target": target_id, "keeper": keeper_id,
               "edge_before": before_edge, "edge_after": after_edge,
               "kg_residue_before": before_kg.score, "kg_residue_after": after_kg.score,
               "channels_after": after_kg.detail.get("channels", []),
               "evidence_after": after_kg.evidence[:3]}
        rows.append(row)
        if args.verbose:
            print(f"  [{target_id}] edge {before_edge:.0f}->{after_edge:.0f}  "
                  f"KG-residue {before_kg.score:.0f}->{after_kg.score:.0f}  "
                  f"channels={after_kg.detail.get('channels', [])}")
        if not args.keep:
            adapter.delete_all_memories(uid)
    adapter.close()

    df = pd.DataFrame(rows)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = config.RESULTS_DIR / f"exp09_zep_kg_residual_{stamp}"
    df.drop(columns=["evidence_after"]).to_csv(base.with_suffix(".csv"), index=False)
    metrics = {
        "edge_residual_after_rate": float(df["edge_after"].mean()),
        "kg_residue_after_rate": float(df["kg_residue_after"].mean()),
        "n": len(df),
    }
    base.with_suffix(".json").write_text(json.dumps(
        {"experiment": "exp09_zep_kg_residual", "timestamp_utc": stamp,
         "system": "zep/graphiti", "metrics": metrics, "rows": rows}, indent=2, default=str))

    print("\n" + "=" * 64)
    print("  EXP09 — ZEP/GRAPHITI KG-NODE RESIDUAL")
    print("=" * 64)
    print(f"  After remove_episode (explicit deletion):")
    print(f"    value still in an EDGE        : {metrics['edge_residual_after_rate']:.0%}  (edges hard-deleted)")
    print(f"    value still in the KG (summary): {metrics['kg_residue_after_rate']:.0%}  (structural residue)")
    print(f"    channels: {sorted({c for r in rows for c in r['channels_after']})}")
    print(f"\n  Results: {base.with_suffix('.csv')}")


if __name__ == "__main__":
    main()
