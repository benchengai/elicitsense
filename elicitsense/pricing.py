"""Published per-token prices, used to report what each LLM call costs.

USD per million tokens: (input, cached input, output), standard tier, short
context. Local models have no per-token price; their cost is machine time,
reported as latency.
"""

from __future__ import annotations

AS_OF = "2026-11-01"
SOURCES = {
    "anthropic": "https://platform.claude.com/docs/en/about-claude/pricing",
    "openai": "https://developers.openai.com/api/docs/pricing",
}

PRICES = {
    "claude-opus-5-5": (4.00, 0.20, 20.00),
    "claude-sonnet-5-5": (2.00, 0.10, 10.00),
    "gpt-6.1-sol": (2.00, 0.10, 10.00),
    "gpt-6.1-terra": (1.00, 0.05, 5.00),
    "gpt-6-luna": (0.10, 0.01, 0.50),
    "gpt-5.6-luna": (0.20, 0.02, 1.20),
    "gpt-5.4-mini": (0.75, 0.075, 4.50),
    "gpt-5.4-nano": (0.20, 0.02, 1.25),
    "gpt-4.1-mini": (0.40, 0.10, 1.60),
}


def price(model: str) -> tuple[float, float, float] | None:
    """Exact id, or a dated snapshot of a listed id (gpt-6.1-sol-2026-...)."""
    if model in PRICES:
        return PRICES[model]
    return next((p for m, p in PRICES.items() if model.startswith(m + "-")), None)


def cost_usd(provider: str, model: str, input_tokens: int, cached_input_tokens: int,
             output_tokens: int) -> float | None:
    if provider == "ollama":
        return 0.0
    if (p := price(model)) is None:
        return None
    uncached = input_tokens - cached_input_tokens
    return (uncached * p[0] + cached_input_tokens * p[1] + output_tokens * p[2]) / 1_000_000
