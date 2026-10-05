# services/vibe/src/vibe/usage/pricing.py
"""Configurable price table (USD per 1M tokens).

Prices change, so they live here as data, not scattered through the code.
Models not listed are treated as free (cost 0).
"""
from __future__ import annotations

# (provider, model) -> (input_price, output_price) per 1M tokens, USD.
PRICE_TABLE: dict[tuple[str, str], tuple[float, float]] = {
    ("openai", "gpt-4o"): (2.50, 10.00),
    ("openai", "gpt-4o-mini"): (0.15, 0.60),
    ("anthropic", "claude-sonnet-4-6"): (3.00, 15.00),
    ("opencode-go", "kimi-k3"): (0.40, 1.60),
    ("opencode-go", "grok-4.7"): (0.50, 2.00),
    ("opencode-go", "deepseek-v4-flash"): (0.20, 0.80),
    ("opencode-go", "longcat-2.5-preview-free"): (0.0, 0.0),
}

# Cached-input tokens are typically charged at a fraction of the full input price.
CACHE_DISCOUNT = 0.5


def cost_usd(provider: str, model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> float:
    """Compute the USD cost of one LLM call from the price table."""
    prices = PRICE_TABLE.get((provider, model))
    if prices is None:
        return 0.0
    in_price, out_price = prices
    billable_input = max(input_tokens - cached_tokens, 0)
    return (billable_input / 1_000_000) * in_price + (cached_tokens / 1_000_000) * in_price * CACHE_DISCOUNT + (output_tokens / 1_000_000) * out_price
