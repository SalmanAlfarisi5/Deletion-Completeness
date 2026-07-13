"""Provider-agnostic LLM helpers (OpenAI | Anthropic) with on-disk caching.

Every LLM call costs money, so results are cached by (model, messages, params)
to `data/results/llm_cache.json`. This makes entailment/judge calls free on
re-run and keeps experiments reproducible.
"""
from __future__ import annotations

import atexit
import hashlib
import json
import threading

import config

_CACHE_PATH = config.RESULTS_DIR / "llm_cache.json"
_lock = threading.Lock()
try:
    _cache: dict = json.loads(_CACHE_PATH.read_text())
except (FileNotFoundError, json.JSONDecodeError):
    _cache = {}

_st_model = None  # lazily-loaded sentence-transformer


def _key(model: str, messages: list[dict], **params) -> str:
    blob = json.dumps([model, messages, params], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


_dirty = 0


def _save() -> None:
    with _lock:
        try:  # fold in any concurrent writer's new entries before overwriting
            if _CACHE_PATH.exists():
                for k, v in json.loads(_CACHE_PATH.read_text() or "{}").items():
                    _cache.setdefault(k, v)
        except (OSError, json.JSONDecodeError):
            pass
        _CACHE_PATH.write_text(json.dumps(_cache, indent=0))


def _touch() -> None:
    """Persist in batches (every 50 writes, plus on exit) rather than on every
    call, turning O(n^2) whole-file rewrites into O(n/50)."""
    global _dirty
    _dirty += 1
    if _dirty >= 50:
        _dirty = 0
        _save()


atexit.register(_save)


def chat(messages: list[dict], model: str | None = None, temperature: float = 0.0,
         max_tokens: int = 1024, json_mode: bool = False, use_cache: bool = True) -> str:
    """Single chat completion -> text. Provider is routed by the MODEL name
    (config.provider_for) so ONE run can mix OpenAI + Anthropic reasoners. Models
    that reject an explicit temperature (Sonnet 5 / Opus 4.7-4.8 / GPT-5 / o-series)
    get it omitted (config.model_rejects_temperature)."""
    model = model or config.JUDGE_MODEL
    provider = config.provider_for(model)
    no_temp = config.model_rejects_temperature(model)
    # eff_temp keeps the cache key IDENTICAL for the pinned backbone (temp applied),
    # while temp-free models key on None (they're non-deterministic; estimate_rho
    # sets use_cache=False for its sampling draws anyway).
    eff_temp = None if no_temp else temperature
    k = _key(model, messages, temperature=eff_temp, max_tokens=max_tokens,
             json_mode=json_mode, provider=provider)
    if use_cache and k in _cache:
        return _cache[k]

    if provider == "openai":
        from openai import OpenAI

        # max_retries=8 so rate-limit (429) / transient (5xx) errors back off and retry
        # instead of raising -> under parallel load a throttled call is retried, not
        # miscounted as a refusal (which would deflate rho in exp07/estimate_rho).
        client = OpenAI(api_key=config.OPENAI_API_KEY,
                        base_url=config.OPENAI_BASE_URL or None,
                        max_retries=8, timeout=90.0)
        kwargs: dict = dict(model=model, messages=messages)
        if config.uses_max_completion_tokens(model):
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens
        if not no_temp:
            kwargs["temperature"] = temperature
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        out = resp.choices[0].message.content or ""
    else:  # anthropic
        from anthropic import Anthropic

        client = Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=8, timeout=90.0)
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        convo = [m for m in messages if m["role"] != "system"]
        kwargs = dict(model=model, messages=convo, max_tokens=max_tokens)
        if system:  # omit when empty (newer models 400 on system=null) + array-block form
            kwargs["system"] = [{"type": "text", "text": system}]
        if not no_temp:
            kwargs["temperature"] = temperature
        thinking = config.anthropic_thinking_for(model)
        if thinking:
            kwargs["thinking"] = thinking
        resp = client.messages.create(**kwargs)
        # Robust to thinking-on responses (first block may be a thinking block).
        out = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")

    if use_cache:
        _cache[k] = out
        _touch()
    return out


def chat_json(messages: list[dict], **kw) -> dict:
    """chat() but parse JSON, tolerating fenced/messy output."""
    raw = chat(messages, json_mode=True, **kw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        s, e = raw.find("{"), raw.rfind("}")
        if 0 <= s < e:
            try:
                return json.loads(raw[s:e + 1])
            except json.JSONDecodeError:
                pass
    return {}


def paraphrase(text: str, n: int = 5) -> list[str]:
    """Return up to n meaning-preserving rewrites of `text`."""
    msgs = [
        {"role": "system", "content": "You rewrite a statement in several different "
         "ways, preserving meaning but varying wording and structure. Respond only "
         'with JSON: {"paraphrases": ["...", ...]}.'},
        {"role": "user", "content": f"Statement: {text}\nProduce {n} paraphrases."},
    ]
    out = chat_json(msgs, temperature=0.7, max_tokens=512)
    paras = out.get("paraphrases", [])
    return [p for p in paras if isinstance(p, str)][:n] or [text]


def value_twin(text: str) -> str:
    """A matched near-twin: same template/wording, only the specific value changed
    to a different plausible (never-stored) one. Used as the MIA control."""
    msgs = [
        {"role": "system", "content": "Rewrite the statement keeping the EXACT template, "
         "subject and wording, but replace ONLY the specific value (number, code, name, "
         "amount, or category) with a different, plausible, clearly different value. "
         'Respond only as JSON {"twin": "..."}.'},
        {"role": "user", "content": text},
    ]
    out = chat_json(msgs, temperature=0.0, max_tokens=120)
    twin = out.get("twin")
    return twin if isinstance(twin, str) and twin.strip() else text


def value_twins(text: str, n: int = 2) -> list[str]:
    """n matched near-twins: same template/subject/wording, only the specific value
    swapped to n DIFFERENT plausible (never-stored) values. Used as MIA controls
    (a 2nd matched control per fact boosts the test's power). Degrades gracefully
    to the single-twin call if the model under-delivers."""
    if n <= 1:
        return [value_twin(text)]
    msgs = [
        {"role": "system", "content": "Rewrite the statement keeping the EXACT template, "
         "subject and wording, but replace ONLY the specific value (number, code, name, "
         "amount, or category) with DIFFERENT, plausible, clearly different values. Produce "
         f"{n} variants, each using a DISTINCT replacement value (all different from the "
         'original and from each other). Respond only as JSON {"twins": ["...", "..."]}.'},
        {"role": "user", "content": text},
    ]
    out = chat_json(msgs, temperature=0.0, max_tokens=120 * n)
    raw = out.get("twins", []) if isinstance(out, dict) else []
    seen: set[str] = set()
    uniq: list[str] = []
    for t in raw:
        if isinstance(t, str) and t.strip() and t not in seen:
            seen.add(t)
            uniq.append(t)
    if not uniq:                       # model gave nothing usable -> single-twin fallback
        uniq = [value_twin(text)]
    while len(uniq) < n:               # pad if it returned fewer distinct twins than asked
        uniq.append(uniq[-1])
    return uniq[:n]


def embed(texts: list[str]):
    """Local sentence-transformer embeddings (free, on GPU). L2-normalized."""
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer

        _st_model = SentenceTransformer(config.EMBED_MODEL)
    return _st_model.encode(texts, normalize_embeddings=True)
