"""Provider-agnostic LLM helpers (OpenAI | Anthropic) with on-disk caching.

Every LLM call costs money, so results are cached by (model, messages, params)
to `data/results/llm_cache.json`. This makes entailment/judge calls free on
re-run and keeps experiments reproducible.
"""
from __future__ import annotations

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


def _save() -> None:
    with _lock:
        _CACHE_PATH.write_text(json.dumps(_cache, indent=0))


def chat(messages: list[dict], model: str | None = None, temperature: float = 0.0,
         max_tokens: int = 1024, json_mode: bool = False, use_cache: bool = True) -> str:
    """Single chat completion -> text. Routed by config.LLM_PROVIDER."""
    model = model or config.JUDGE_MODEL
    k = _key(model, messages, temperature=temperature, max_tokens=max_tokens,
             json_mode=json_mode, provider=config.LLM_PROVIDER)
    if use_cache and k in _cache:
        return _cache[k]

    if config.LLM_PROVIDER == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=config.OPENAI_API_KEY)
        kwargs: dict = dict(model=model, messages=messages,
                            temperature=temperature, max_tokens=max_tokens)
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        out = resp.choices[0].message.content or ""
    else:  # anthropic
        from anthropic import Anthropic

        client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        convo = [m for m in messages if m["role"] != "system"]
        resp = client.messages.create(model=model, system=system or None,
                                       messages=convo, temperature=temperature,
                                       max_tokens=max_tokens)
        out = resp.content[0].text if resp.content else ""

    if use_cache:
        _cache[k] = out
        _save()
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


def embed(texts: list[str]):
    """Local sentence-transformer embeddings (free, on GPU). L2-normalized."""
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer

        _st_model = SentenceTransformer(config.EMBED_MODEL)
    return _st_model.encode(texts, normalize_embeddings=True)
