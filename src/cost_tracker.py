"""Approximate per-call cost estimation and per-actor budget enforcement.

Token counts use a simple chars/4 heuristic -- a documented
approximation, not a billing-accurate count. Swap `estimate_tokens`
for a real tokenizer (e.g. the model provider's token-counting API) if
you need exact numbers; the budget-enforcement logic doesn't change.
Prices are USD per 1,000 tokens and configurable per model.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional


class BudgetExceededError(Exception):
    pass


@dataclass
class ModelPricing:
    input_per_1k: float
    output_per_1k: float


DEFAULT_PRICING: Dict[str, ModelPricing] = {
    "anthropic.claude-3-5-sonnet-20241022-v2:0": ModelPricing(input_per_1k=0.003, output_per_1k=0.015),
    "anthropic.claude-3-haiku-20240307-v1:0": ModelPricing(input_per_1k=0.00025, output_per_1k=0.00125),
}

_FALLBACK_PRICING = ModelPricing(input_per_1k=0.003, output_per_1k=0.015)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token for English text."""
    return max(1, len(text) // 4)


class CostTracker:
    def __init__(
        self,
        pricing: Optional[Dict[str, ModelPricing]] = None,
        budgets: Optional[Dict[str, float]] = None,
    ) -> None:
        self.pricing: Dict[str, ModelPricing] = dict(pricing or DEFAULT_PRICING)
        self.budgets: Dict[str, float] = dict(budgets or {})
        self._spend: Dict[str, float] = defaultdict(float)

    def set_budget(self, actor: str, usd: float) -> None:
        self.budgets[actor] = usd

    def spend_so_far(self, actor: str) -> float:
        return self._spend[actor]

    def estimate_cost(self, model_id: str, input_text: str, output_text: str = "") -> float:
        pricing = self.pricing.get(model_id, _FALLBACK_PRICING)
        input_cost = (estimate_tokens(input_text) / 1000) * pricing.input_per_1k
        output_cost = (estimate_tokens(output_text) / 1000) * pricing.output_per_1k
        return round(input_cost + output_cost, 6)

    def check_budget(self, actor: str, projected_additional_cost: float = 0.0) -> None:
        budget = self.budgets.get(actor)
        if budget is None:
            return
        spent = self._spend[actor]
        if spent + projected_additional_cost > budget:
            raise BudgetExceededError(
                f"actor '{actor}' would exceed budget: "
                f"${spent:.4f} spent + ${projected_additional_cost:.4f} projected > ${budget:.4f} budget"
            )

    def record_spend(self, actor: str, cost: float) -> None:
        self._spend[actor] += cost
