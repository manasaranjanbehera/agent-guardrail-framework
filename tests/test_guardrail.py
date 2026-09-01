import pytest

from src.audit_log import AuditLogger
from src.cost_tracker import CostTracker
from src.guardrail import GuardedAgent, PolicyViolationError
from src.policy import PolicyEngine


def echo_agent(prompt: str) -> str:
    return f"echo: {prompt}"


def test_successful_call_returns_output_and_logs_audit_entry():
    logger = AuditLogger()
    agent = GuardedAgent(call_fn=echo_agent, audit_logger=logger)

    result = agent.invoke("hello there", actor="alice")

    assert result.output == "echo: hello there"
    assert result.estimated_cost_usd > 0
    assert len(logger.entries) == 1
    assert logger.entries[0].allowed is True
    assert logger.entries[0].actor == "alice"


def test_audit_log_never_stores_raw_pii():
    logger = AuditLogger()
    agent = GuardedAgent(call_fn=lambda p: f"reply for {p}", audit_logger=logger)

    agent.invoke("my email is jane@example.com", actor="alice")

    logged_input = logger.entries[0].redacted_input
    assert "jane@example.com" not in logged_input
    assert "[REDACTED:EMAIL]" in logged_input


def test_denylisted_prompt_is_blocked_before_calling_the_model():
    calls = []

    def tracking_agent(prompt):
        calls.append(prompt)
        return "should never run"

    policy = PolicyEngine(denylist=["forbidden"])
    logger = AuditLogger()
    agent = GuardedAgent(call_fn=tracking_agent, policy=policy, audit_logger=logger)

    with pytest.raises(PolicyViolationError):
        agent.invoke("please do the forbidden thing", actor="alice")

    assert calls == []  # underlying model was never called
    assert logger.entries[0].allowed is False


def test_over_budget_actor_is_blocked_before_calling_the_model():
    calls = []

    def tracking_agent(prompt):
        calls.append(prompt)
        return "x" * 10000  # expensive response

    tracker = CostTracker(budgets={"alice": 0.0000001})
    agent = GuardedAgent(call_fn=tracking_agent, cost_tracker=tracker)

    with pytest.raises(Exception):
        agent.invoke("hello", actor="alice")

    assert calls == []


def test_disallowed_output_is_blocked_and_not_leaked_to_caller():
    def bad_agent(prompt):
        return "here is the forbidden secret answer"

    policy = PolicyEngine(denylist=["forbidden"])
    logger = AuditLogger()
    agent = GuardedAgent(call_fn=bad_agent, policy=policy, audit_logger=logger)

    with pytest.raises(PolicyViolationError):
        agent.invoke("safe looking prompt", actor="alice")

    assert logger.entries[0].redacted_output == "[BLOCKED OUTPUT]"


def test_audit_log_writes_jsonl_to_disk(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    logger = AuditLogger(log_path=log_path)
    agent = GuardedAgent(call_fn=echo_agent, audit_logger=logger)

    agent.invoke("hi", actor="bob")

    assert log_path.exists()
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    import json
    entry = json.loads(lines[0])
    assert entry["actor"] == "bob"
