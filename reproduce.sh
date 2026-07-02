#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Reproduce the deletion-completeness results (both paper drafts).
#
# Prereqs:
#   - project venv (override with PYTHON=...)
#   - .env with OPENAI_API_KEY  (LLM_PROVIDER now defaults to openai)
#   - for exp09/exp10 ONLY: local Neo4j (:7687), Postgres (:5432), Letta (:8283)
#     up first — see docs/CONTEXT_NOT_IN_CODE.md for the no-sudo start commands.
#
# The code defaults now reproduce the papers: provider=openai, --n=all facts,
# planner entailment judge = gpt-4o. Run from the repo root.
# ---------------------------------------------------------------------------
set -euo pipefail
PY="${PYTHON:-/home/salman/Desktop/venv/myenv/bin/python}"

# 0. Validate the load-bearing judges -> data/results/judge_validation_*.json
"$PY" evaluation/judge.py

# 1-2. Residual survival on Mem0 (all 48 isolated PII facts)
"$PY" experiments/exp01_baseline.py          # naive deletion residual
"$PY" experiments/exp02_artifact_purge.py    # naive vs artifact-aware (-> 0%)
"$PY" experiments/exp05_duplication.py       # duplication factorial (embedder x cadence)

# 3. Planner (all 34 multi-hop; gpt-4o entailment by default) + depth-first comparator
"$PY" experiments/exp03_planner.py                       # threshold: k=0.91, 0 spurious
"$PY" experiments/exp03_planner.py --heuristic depth_first   # comparator: k=5.65, 126 spurious

# 4. Re-derivation bins (all 34 multi-hop, two reasoners) -> 0% after co-delete
"$PY" experiments/exp04_parametric.py

# 7. Parametric floor rho (49 facts, 6 samples/reasoner).
#    NOTE: rho samples at temperature 0.7 with use_cache=False, so it is NOT
#    bit-reproducible across runs (no server-side seed). The committed answers are
#    logged in data/results/exp07_*.json -> the REPRODUCIBLE path is to re-score
#    those logged answers (free, no API calls).
"$PY" experiments/exp07_rho_gradient.py --n-samples 6

# 8. Membership inference on Mem0 (48 members + 2 matched twins each)
"$PY" experiments/exp08_mia.py

# 9-10. Cross-system convergence (REQUIRE the local services above to be up)
# "$PY" experiments/exp09_zep_kg_residual.py    # Graphiti: edge 40% / summary 80%
# "$PY" experiments/exp10_letta.py              # Letta: 0% faithful / 100% archival
# "$PY" experiments/exp11_letta_rederivation.py # Letta re-derivation bins + rho floor

echo "Done. Results in data/results/ ; certificates in data/results/certificates/"
