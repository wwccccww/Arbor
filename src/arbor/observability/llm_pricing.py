from __future__ import annotations

import os


def _price_per_million(model: str, kind: str) -> float:
    key = f"ARBOR_LLM_PRICE_{model.upper().replace('-', '_')}_{kind.upper()}"
    raw = os.environ.get(key)
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    defaults = {
        "deepseek-chat": (0.14, 0.28),
        "deepseek-reasoner": (0.55, 2.19),
    }
    pair = defaults.get(model.lower(), (0.0, 0.0))
    return pair[0] if kind == "input" else pair[1]


def estimated_llm_cost_usd(*, model: str, input_tokens: int | None, output_tokens: int | None) -> float:
    if not input_tokens and not output_tokens:
        return 0.0
    in_price = _price_per_million(model, "input")
    out_price = _price_per_million(model, "output")
    cost = 0.0
    if input_tokens:
        cost += (input_tokens / 1_000_000.0) * in_price
    if output_tokens:
        cost += (output_tokens / 1_000_000.0) * out_price
    return round(cost, 8)
