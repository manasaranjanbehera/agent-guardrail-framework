"""Approximate per-call cost estimation and per-actor budget enforcement.

Token counts use a simple chars/4 heuristic -- a documented
approximation, not a billing-accurate count. Swap `estimate_tokens`
for a real tokenizer (e.g. the model provider's token-counting API) if
you need exact numbers; the budget-enforcement logic doesn't change.
Prices are USD per 1,000 tokens and configurable per model.

Recorded spend can be persisted to a JSON file with `save()`/`load()`
so an actor's running total survives a process restart -- an in-memory
counter alone would quietly reset every deploy, silently discarding
budget history. There is deliberately no automatic period reset (daily,
monthly, etc.): what "period" means, and when it rolls over, is a
policy decision that varies by organization, so it's left as an
integration point rather than guessed at here (see the README).

Not thread-safe: `check_budget` and `record_spend` are separate calls,
so concurrent invocations for the same actor can both pass a budget
check before either records its spend (a classic check-then-act race).
Add a lock around the check/record pair in `GuardedAgent.invoke` if
this is used from multiple threads against a shared `CostTracker`.
"""
from __future__ import annotations

import json
import warnings
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


class BudgetExceededError(Exception):
    pass


@dataclass
class ModelPricing:
    input_per_1k: float
    output_per_1k: float


DEFAULT_PRICING: dict[str, ModelPricing] = {
    "anthropic.claude-3-5-sonnet-20241022-v2:0": ModelPricing(
        input_per_1k=0.003, output_per_1k=0.015
    ),
    "anthropic.claude-3-haiku-20240307-v1:0": ModelPricing(
        input_per_1k=0.00025, output_per_1k=0.00125
    ),
}

_FALLBACK_PRICING = ModelPricing(input_per_1k=0.003, output_per_1k=0.015)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token for English text."""
    return max(1, len(text) // 4)


class CostTracker:
    def __init__(
        self,
        pricing: dict[str, ModelPricing] | None = None,
        budgets: dict[str, float] | None = None,
    ) -> None:
        self.pricing: dict[str, ModelPricing] = dict(pricing or DEFAULT_PRICING)
        self.budgets: dict[str, float] = dict(budgets or {})
        self._spend: dict[str, float] = defaultdict(float)

    def set_budget(self, actor: str, usd: float) -> None:
        self.budgets[actor] = usd

    def spend_so_far(self, actor: str) -> float:
        return self._spend[actor]

    def estimate_cost(self, model_id: str, input_text: str, output_text: str = "") -> float:
        pricing = self.pricing.get(model_id)
        if pricing is None:
            warnings.warn(
                f"No pricing configured for model_id={model_id!r}; falling back to "
                "default pricing. Cost estimates for this model may be inaccurate -- "
                "add it to CostTracker(pricing={...}) for an accurate estimate.",
                stacklevel=2,
            )
            pricing = _FALLBACK_PRICING
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
                f"${spent:.4f} spent + ${projected_additional_cost:.4f} projected "
                f"> ${budget:.4f} budget"
            )

    def record_spend(self, actor: str, cost: float) -> None:
        self._spend[actor] += cost

    def save(self, path: str | Path) -> None:
        """Persist recorded spend (not budgets or pricing -- those are
        configuration, passed in fresh each run) to a JSON file."""
        state_path = Path(path)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"spend": dict(self._spend)}, indent=2))

    @classmethod
    def load(
        cls,
        path: str | Path,
        pricing: dict[str, ModelPricing] | None = None,
        budgets: dict[str, float] | None = None,
    ) -> CostTracker:
        """Build a CostTracker, restoring recorded spend from `path` if it
        exists. A missing file is the expected first-run state and starts
        with zero spend; a present-but-corrupted file starts fresh too, but
        warns loudly instead of silently discarding what looks like it
        should have been real budget history."""
        tracker = cls(pricing=pricing, budgets=budgets)
        state_path = Path(path)
        if not state_path.exists():
            return tracker
        try:
            data = json.loads(state_path.read_text())
            for actor, spent in data.get("spend", {}).items():
                tracker._spend[actor] = spent
        except (json.JSONDecodeError, OSError) as exc:
            warnings.warn(
                f"Could not load cost tracker state from {state_path}: {exc}. "
                "Starting with zero recorded spend for all actors.",
                stacklevel=2,
            )
        return tracker
