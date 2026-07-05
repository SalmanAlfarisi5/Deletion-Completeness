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
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")  # custom endpoint for a "new API"; blank = default OpenAI
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

# --------------------------------------------------------------------------- #
# Frontier adversary reasoners (RTBF worst-adversary set, Def. 4)
# --------------------------------------------------------------------------- #
# Added ALONGSIDE the pinned gpt-4o-mini/gpt-4o backbone: extraction + judge stay
# pinned for reproducibility (and to preserve the memory-store findings); these
# only ever play the re-derivation / rho ADVERSARY role. sup_A over a larger,
# stronger adversary set can only RAISE the uncertifiable count -> strengthens
# the limit result. Authoring stays on gpt-4o-mini (a held-out, weaker model) to
# avoid measurement/authoring circularity.
SONNET_MODEL = os.getenv("SONNET_MODEL", "claude-sonnet-5")  # newer Claude adversary
GPT5_MODEL = os.getenv("GPT5_MODEL", "gpt-5.5")              # newer OpenAI adversary
# Whether the frontier models participate this run (kept OFF until wired+smoke-tested).
USE_FRONTIER_REASONERS = os.getenv("USE_FRONTIER_REASONERS", "0") == "1"


def reasoner_models(include_frontier: bool | None = None) -> list[str]:
    """Ordered, de-duplicated adversary set. Backbone first (the calibrated
    temp-0.7 rho gradient), then any frontier worst-case reasoners."""
    if include_frontier is None:
        include_frontier = USE_FRONTIER_REASONERS
    models = [REASONER_MODEL, SECOND_MODEL]
    if include_frontier:
        for m in (SONNET_MODEL, GPT5_MODEL):
            if m and m not in models:
                models.append(m)
    return models


# Models that REJECT an explicit `temperature` (Anthropic Opus 4.7/4.8, Sonnet 5,
# Fable/Mythos 5; OpenAI GPT-5 / o-series). llm.chat() omits temperature for these;
# estimate_rho() then draws its n samples from inherent run-to-run stochasticity
# instead of a temp knob (the temp-0.7 backbone reasoners remain the calibrated
# gradient). Extend without a code change via TEMP_FREE_EXTRA (comma-separated).
_TEMP_FREE_PREFIXES = ("claude-opus-4-7", "claude-opus-4-8", "claude-sonnet-5",
                       "claude-fable-5", "claude-mythos-5", "gpt-5", "o1", "o3", "o4")


def model_rejects_temperature(model: str) -> bool:
    m = (model or "").lower()
    extra = tuple(x.strip().lower() for x in os.getenv("TEMP_FREE_EXTRA", "").split(",") if x.strip())
    return m.startswith(_TEMP_FREE_PREFIXES + extra)


def uses_max_completion_tokens(model: str) -> bool:
    """GPT-5 / o-series Chat Completions want `max_completion_tokens`, not `max_tokens`."""
    return (model or "").lower().startswith(("gpt-5", "o1", "o3", "o4"))


def provider_for(model: str) -> str:
    """Route by model NAME so a single run can mix OpenAI + Anthropic reasoners."""
    m = (model or "").lower()
    if m.startswith(("claude", "anthropic")):
        return "anthropic"
    if m.startswith(("gpt", "o1", "o3", "o4", "text-", "ft:")):
        return "openai"
    return LLM_PROVIDER  # fall back to the configured default


# Newer-Claude thinking control. Salman chose cost-controlled ("thinking off"):
# Sonnet 5 runs ADAPTIVE thinking when `thinking` is omitted, so we send an
# explicit setting. Only the adaptive-only family accepts it (Haiku 4.5 / older
# reject the param) -> return None for those so nothing is sent.
_THINKING_MODELS = ("claude-sonnet-5", "claude-opus-4-7", "claude-opus-4-8",
                    "claude-fable-5", "claude-mythos-5")


def anthropic_thinking_for(model: str) -> dict | None:
    if (model or "").lower().startswith(_THINKING_MODELS):
        return {"type": os.getenv("ANTHROPIC_THINKING", "disabled")}
    return None


# Local embedding model — free, runs on the GPU. Used by embedding probes and
# (optionally) as Mem0's embedder in OSS mode.
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")

# --------------------------------------------------------------------------- #
# Experiment knobs
# --------------------------------------------------------------------------- #
GLOBAL_SEED = int(os.getenv("GLOBAL_SEED", "42"))
USER_ID_PREFIX = os.getenv("USER_ID_PREFIX", "u_alice")

TAU = 0.10               # recoverability threshold below which deletion is "COMPLETE"

# Pinned "today" for all elicitation prompts (probes/parametric_probe.py). A fixed
# date instead of date.today() keeps age-anchored facts (e.g. "35" from a 1991 birth
# year) and the LLM cache key stable across calendar days -- otherwise a re-run on a
# later day silently re-buys every rederivation/rho answer and can flip age ground
# truth at New Year (RF4 M-13).
EXPERIMENT_DATE = os.getenv("EXPERIMENT_DATE", "2026-06-27")  # the canonical wave date
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
