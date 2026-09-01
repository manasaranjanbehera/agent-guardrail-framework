import pytest

from src.cost_tracker import BudgetExceededError, CostTracker, estimate_tokens


def test_estimate_tokens_rough_heuristic():
    assert estimate_tokens("") == 1  # never zero
    assert estimate_tokens("a" * 400) == 100


def test_estimate_cost_known_model():
    tracker = CostTracker()
    model = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    cost = tracker.estimate_cost(model, input_text="a" * 4000, output_text="b" * 4000)
    # 1000 input tokens * 0.003/1k + 1000 output tokens * 0.015/1k = 0.018
    assert cost == pytest.approx(0.018, abs=1e-6)


def test_budget_not_set_never_blocks():
    tracker = CostTracker()
    tracker.check_budget("alice", projected_additional_cost=1000.0)  # should not raise


def test_budget_blocks_when_exceeded():
    tracker = CostTracker(budgets={"alice": 0.01})
    tracker.record_spend("alice", 0.009)
    with pytest.raises(BudgetExceededError):
        tracker.check_budget("alice", projected_additional_cost=0.005)


def test_budget_allows_when_under():
    tracker = CostTracker(budgets={"alice": 1.0})
    tracker.record_spend("alice", 0.5)
    tracker.check_budget("alice", projected_additional_cost=0.4)  # should not raise
    assert tracker.spend_so_far("alice") == 0.5
