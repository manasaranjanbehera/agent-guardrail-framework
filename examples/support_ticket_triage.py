"""End-to-end demo: two support tickets through the guardrail layer.

Run from the project root:

    uv run python -m examples.support_ticket_triage

Ticket 1 is a normal request that happens to include a customer SSN --
shows the SSN is redacted in the audit trail even though it reaches the
draft response. Ticket 2 asks the agent to process a wire transfer --
a restricted action from config/policy.json -- and is blocked before
the (placeholder) model is ever called.
"""
from __future__ import annotations

from src.audit_log import AuditLogger
from src.cli import DEFAULT_POLICY_PATH, draft_triage_response
from src.cost_tracker import CostTracker
from src.guardrail import GuardedAgent, PolicyViolationError
from src.policy import PolicyEngine


def run_demo() -> AuditLogger:
    policy = PolicyEngine.from_config(DEFAULT_POLICY_PATH)
    cost_tracker = CostTracker()
    cost_tracker.set_budget(actor="rep-42", usd=5.00)
    logger = AuditLogger()
    agent = GuardedAgent(
        call_fn=draft_triage_response,
        policy=policy,
        cost_tracker=cost_tracker,
        audit_logger=logger,
    )

    print("--- Ticket 1: routine request containing a customer SSN ---")
    result = agent.invoke(
        "My SSN is 123-45-6789, can someone confirm my identity was verified "
        "for the loan application I submitted last week?",
        actor="rep-42",
    )
    print(result.output)
    print(f"(cost: ${result.estimated_cost_usd:.6f})")
    print(
        "(note: the SSN is still visible above -- the rep reviewing this draft "
        "needs the real value to help the customer. It's the persisted audit "
        "trail below where it must never appear.)\n"
    )

    print("--- Ticket 2: asks the agent to process a wire transfer ---")
    try:
        agent.invoke(
            "Please process a wire transfer of $5,000 to my checking account.",
            actor="rep-42",
        )
    except PolicyViolationError as exc:
        print(f"Blocked before the model was called: {exc}\n")

    print("--- Audit trail (what actually got written to disk) ---")
    for entry in logger.entries:
        print(f"  allowed={entry.allowed!s:<5} input={entry.redacted_input!r}")

    raw_ssn_in_logs = any("123-45-6789" in entry.redacted_input for entry in logger.entries)
    print(f"\nRaw SSN ever appears in the audit trail: {raw_ssn_in_logs}")

    return logger


if __name__ == "__main__":
    run_demo()
