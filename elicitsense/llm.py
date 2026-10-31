"""Provider-neutral structured-output calls (Claude or GPT).

Every LLM step in the pipeline goes through `complete_json`: a system prompt,
a user prompt and a strict JSON schema in, the raw JSON text out. The callers
validate the result and do all trust-critical work deterministically.
"""

from __future__ import annotations

import os

DEFAULT_MODELS = {"anthropic": "claude-opus-5-5", "openai": "gpt-6.1-sol"}


class LLMError(RuntimeError):
    pass


def resolve_provider(provider: str) -> str:
    """'auto' picks whichever provider has a key configured, preferring Anthropic."""
    if provider != "auto":
        return provider
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "anthropic"


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
    return text, {
        "provider": "anthropic",
        "model": response.model,
        "request_id": response._request_id,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
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
    return response.output_text, {
        "provider": "openai",
        "model": response.model,
        "request_id": response._request_id,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }


def complete_json(system: str, prompt: str, schema: dict, name: str,
                  provider: str = "auto", model: str | None = None) -> tuple[str, dict]:
    provider = resolve_provider(provider)
    call = {"anthropic": _anthropic, "openai": _openai}[provider]
    return call(system, prompt, schema, name, model or DEFAULT_MODELS[provider])
