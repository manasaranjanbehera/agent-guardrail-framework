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


def test_estimate_cost_warns_on_unknown_model_id():
    tracker = CostTracker()
    with pytest.warns(UserWarning, match="No pricing configured"):
        tracker.estimate_cost("some-model-not-in-the-table", "hello")


def test_estimate_cost_no_warning_for_known_model_id():
    import warnings

    tracker = CostTracker()
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning here fails the test
        tracker.estimate_cost("anthropic.claude-3-haiku-20240307-v1:0", "hello")


def test_save_and_load_round_trip(tmp_path):
    state_path = tmp_path / "state.json"
    tracker = CostTracker(budgets={"alice": 10.0})
    tracker.record_spend("alice", 1.23)
    tracker.record_spend("bob", 0.5)
    tracker.save(state_path)

    reloaded = CostTracker.load(state_path, budgets={"alice": 10.0})

    assert reloaded.spend_so_far("alice") == 1.23
    assert reloaded.spend_so_far("bob") == 0.5


def test_load_from_nonexistent_path_starts_fresh(tmp_path):
    missing = tmp_path / "never_existed.json"
    tracker = CostTracker.load(missing)
    assert tracker.spend_so_far("anyone") == 0


def test_load_from_corrupted_file_warns_and_starts_fresh(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("{not valid json")

    with pytest.warns(UserWarning, match="Could not load cost tracker state"):
        tracker = CostTracker.load(state_path)

    assert tracker.spend_so_far("anyone") == 0


def test_save_creates_parent_directories(tmp_path):
    state_path = tmp_path / "nested" / "dir" / "state.json"
    tracker = CostTracker()
    tracker.record_spend("alice", 0.01)
    tracker.save(state_path)
    assert state_path.exists()
