"""Provider-neutral structured-output calls (Claude, GPT, or a local model via Ollama).

Every LLM step in the pipeline goes through `complete_json`: a system prompt,
a user prompt and a strict JSON schema in, the raw JSON text out. The callers
validate the result and do all trust-critical work deterministically.

Each call also returns usage metadata: tokens, latency and cost in USD.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from .pricing import cost_usd

DEFAULT_MODELS = {"anthropic": "claude-opus-5-5", "openai": "gpt-6.1-sol", "ollama": "qwen3:8b"}
PROVIDERS = tuple(DEFAULT_MODELS)

# Room for the largest prompt (register + transcript, about 2k tokens here) plus the
# answer and any reasoning. Kept small because the KV cache competes for memory on a
# 16 GB laptop.
OLLAMA_CONTEXT = 8192
OLLAMA_MAX_OUTPUT = 6144


class LLMError(RuntimeError):
    pass


def resolve_provider(provider: str) -> str:
    """'auto' picks whichever API provider has a key configured, preferring Anthropic.
    Local models are only used when asked for by name."""
    if provider != "auto":
        return provider
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "anthropic"


def parse_model_spec(spec: str) -> tuple[str, str]:
    """'openai:gpt-6.1-sol' or 'ollama:qwen3:8b' -> (provider, model)."""
    provider, sep, model = spec.partition(":")
    if not sep or provider not in PROVIDERS or not model:
        raise ValueError(f"model spec must be provider:model with provider in {PROVIDERS}: {spec!r}")
    return provider, model


def _anthropic(system: str, prompt: str, schema: dict, name: str, model: str) -> tuple[str, dict]:
    import anthropic

    response = anthropic.Anthropic().beta.messages.create(
        model=model,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": schema}},
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise LLMError(f"model declined the request ({response.stop_details})")
    if response.stop_reason == "max_tokens":
        raise LLMError("output hit max_tokens before the JSON was complete")
    text = next(b.text for b in response.content if b.type == "text")
    u = response.usage
    cached = u.cache_read_input_tokens or 0
    return text, {
        "provider": "anthropic",
        "model": response.model,
        "request_id": response._request_id,
        "input_tokens": u.input_tokens + cached + (u.cache_creation_input_tokens or 0),
        "cached_input_tokens": cached,
        "output_tokens": u.output_tokens,
    }


def _openai(system: str, prompt: str, schema: dict, name: str, model: str) -> tuple[str, dict]:
    import openai

    response = openai.OpenAI().responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        text={"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}},
    )
    if response.status == "incomplete":
        raise LLMError(f"response incomplete: {response.incomplete_details}")
    for item in response.output:
        if item.type == "message":
            for part in item.content:
                if part.type == "refusal":
                    raise LLMError(f"model declined the request ({part.refusal})")
    u = response.usage
    return response.output_text, {
        "provider": "openai",
        "model": response.model,
        "request_id": response._request_id,
        "input_tokens": u.input_tokens,
        "cached_input_tokens": u.input_tokens_details.cached_tokens or 0,
        "output_tokens": u.output_tokens,
        "reasoning_tokens": u.output_tokens_details.reasoning_tokens or 0,
    }


def _ollama(system: str, prompt: str, schema: dict, name: str, model: str) -> tuple[str, dict]:
    """Local open-weight model through Ollama's native chat API, which constrains
    decoding to the JSON schema and lets us set the context length. A "+think"
    suffix (qwen3:8b+think) turns on the model's reasoning mode."""
    label = model
    model, think = model.removesuffix("+think"), model.endswith("+think")
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    if not host.startswith("http"):
        host = f"http://{host}"
    body = {
        "model": model,
        "stream": False,
        "format": schema,
        "think": think,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "options": {"num_ctx": OLLAMA_CONTEXT, "num_predict": OLLAMA_MAX_OUTPUT},
    }
    request = urllib.request.Request(f"{host}/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=1800) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise LLMError(f"Ollama error {e.code}: {e.read().decode(errors='replace')[:200]}") from e
    except urllib.error.URLError as e:
        raise LLMError(f"could not reach Ollama at {host} (is `ollama serve` running?)") from e
    except TimeoutError as e:
        raise LLMError("Ollama did not answer within 30 minutes") from e
    if data.get("done_reason") == "length":
        raise LLMError("output hit the token limit before the JSON was complete")
    if data.get("prompt_eval_count", 0) >= OLLAMA_CONTEXT:
        raise LLMError("prompt filled the context window and was truncated")
    return data["message"]["content"], {
        "provider": "ollama",
        "model": label,
        "request_id": None,
        "input_tokens": data.get("prompt_eval_count", 0),
        "cached_input_tokens": 0,
        "output_tokens": data.get("eval_count", 0),
    }


def complete_json(system: str, prompt: str, schema: dict, name: str,
                  provider: str = "auto", model: str | None = None) -> tuple[str, dict]:
    provider = resolve_provider(provider)
    call = {"anthropic": _anthropic, "openai": _openai, "ollama": _ollama}[provider]
    started = time.perf_counter()
    text, meta = call(system, prompt, schema, name, model or DEFAULT_MODELS[provider])
    meta["latency_s"] = round(time.perf_counter() - started, 2)
    meta["cost_usd"] = cost_usd(provider, meta["model"], meta["input_tokens"],
                                meta["cached_input_tokens"], meta["output_tokens"])
    return text, meta
