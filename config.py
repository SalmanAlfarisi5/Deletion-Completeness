"""Central configuration: API keys, model choices, thresholds, paths.

All secrets come from `.env` (see `.env.example`). Everything else has a
sensible default here so experiments are reproducible from a clean checkout.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Disable third-party telemetry BEFORE mem0/chroma are imported anywhere — a
# deletion-completeness project must not itself phone home.
os.environ.setdefault("MEM0_TELEMETRY", "False")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
FACTS_DIR = DATA_DIR / "facts"
RESULTS_DIR = DATA_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------- #
# Backend selection
# --------------------------------------------------------------------------- #
MEM0_MODE = os.getenv("MEM0_MODE", "oss").lower()          # "oss" | "hosted"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()  # "openai" | "anthropic" — openai reproduces the papers

# --------------------------------------------------------------------------- #
# Keys
# --------------------------------------------------------------------------- #
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MEM0_API_KEY = os.getenv("MEM0_API_KEY", "")

# Neo4j for the Zep/Graphiti adapter (local, no-sudo tarball install).
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "deletetest123")

# Letta/MemGPT (tertiary system) — local server over local Postgres.
LETTA_BASE_URL = os.getenv("LETTA_BASE_URL", "http://localhost:8283")
LETTA_MODEL = os.getenv("LETTA_MODEL", "openai/gpt-4o-mini")
LETTA_EMBEDDING = os.getenv("LETTA_EMBEDDING", "openai/text-embedding-3-small")

# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
_DEFAULT_JUDGE = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini-2024-07-18",   # pinned snapshot — the judge is load-bearing
}
JUDGE_MODEL = os.getenv("JUDGE_MODEL", _DEFAULT_JUDGE.get(LLM_PROVIDER, "gpt-4o-mini-2024-07-18"))

# Re-derivation reasoner (the adversary's model) and a SECOND model for
# reasoner-vs-reasoner and judge-vs-judge agreement checks. Pinned snapshots.
REASONER_MODEL = os.getenv("REASONER_MODEL", JUDGE_MODEL)
SECOND_MODEL = os.getenv("SECOND_MODEL", "gpt-4o-2024-08-06")

# Local embedding model — free, runs on the GPU. Used by embedding probes and
# (optionally) as Mem0's embedder in OSS mode.
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")

# --------------------------------------------------------------------------- #
# Experiment knobs
# --------------------------------------------------------------------------- #
GLOBAL_SEED = int(os.getenv("GLOBAL_SEED", "42"))
USER_ID_PREFIX = os.getenv("USER_ID_PREFIX", "u_alice")

TAU = 0.10               # recoverability threshold below which deletion is "COMPLETE"
ENTAILMENT_THRESHOLD = 0.50  # entailment-EDGE threshold for judge VALIDATION + the
# dataset near-miss gate (evaluation/judge.py, data/validate_facts.py). NOTE: the
# planner's co-deletion cutoff is config.TAU (planner/optimizer.py), NOT this knob.
N_PARAPHRASES = 5        # paraphrase probe variants per fact

# Settle time between injections. Mem0's add() decides ADD-vs-UPDATE by searching
# existing memories; without a pause, rapid back-to-back writes race and create
# duplicate rows (a measurement artifact). 1.5s eliminates it in our setup.
INJECT_SETTLE_SECONDS = float(os.getenv("INJECT_SETTLE_SECONDS", "1.5"))

# --------------------------------------------------------------------------- #
# Mem0 (open-source) config — local Chroma + local embedder + chosen LLM.
# Kept fully local for reproducibility; hosted mode ignores this.
# --------------------------------------------------------------------------- #
def mem0_oss_config(embedder: str = "huggingface",
                    collection: str = "deletion_completeness") -> dict:
    """Build the config dict for open-source Mem0 (`Memory.from_config`).

    `embedder` is "huggingface" (local MiniLM, free) or "openai"
    (text-embedding-3-small). Each embedder uses its own Chroma path so the
    differing vector dimensions never collide.
    """
    if LLM_PROVIDER == "anthropic":
        llm = {"provider": "anthropic",
               "config": {"model": "claude-haiku-4-5-20251001", "temperature": 0.0}}
    else:
        llm = {"provider": "openai",
               "config": {"model": "gpt-4o-mini-2024-07-18", "temperature": 0.0}}
    if embedder == "openai":
        emb = {"provider": "openai", "config": {"model": "text-embedding-3-small"}}
    else:
        emb = {"provider": "huggingface", "config": {"model": EMBED_MODEL}}
    return {
        "llm": llm,
        "embedder": emb,
        "vector_store": {
            "provider": "chroma",
            "config": {"collection_name": collection,
                       "path": str(RESULTS_DIR / f"chroma_{embedder}")},
        },
        "version": "v1.1",
    }


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def validate() -> list[str]:
    """Return a list of human-readable problems with the current config.

    Empty list == good to go. Call this at the top of every experiment script.
    """
    problems: list[str] = []
    if MEM0_MODE not in ("oss", "hosted"):
        problems.append(f"MEM0_MODE must be 'oss' or 'hosted', got {MEM0_MODE!r}")
    if LLM_PROVIDER not in ("anthropic", "openai"):
        problems.append(f"LLM_PROVIDER must be 'anthropic' or 'openai', got {LLM_PROVIDER!r}")

    if MEM0_MODE == "hosted" and not MEM0_API_KEY:
        problems.append("MEM0_MODE=hosted but MEM0_API_KEY is empty")
    if LLM_PROVIDER == "anthropic" and not ANTHROPIC_API_KEY:
        problems.append("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is empty")
    if LLM_PROVIDER == "openai" and not OPENAI_API_KEY:
        problems.append("LLM_PROVIDER=openai but OPENAI_API_KEY is empty")
    return problems


if __name__ == "__main__":
    print(f"MEM0_MODE     = {MEM0_MODE}")
    print(f"LLM_PROVIDER  = {LLM_PROVIDER}")
    print(f"JUDGE_MODEL   = {JUDGE_MODEL}")
    print(f"EMBED_MODEL   = {EMBED_MODEL}")
    print(f"RESULTS_DIR   = {RESULTS_DIR}")
    issues = validate()
    print("\nConfig OK" if not issues else "Problems:\n- " + "\n- ".join(issues))
