"""CLI: run one support-ticket message through the guardrail layer.

This is the runnable shape of the project: it wires a policy config
file, persistent per-actor spend, and a GuardedAgent together against
the customer-support-ticket-triage scenario described in the README.

The wrapped "agent" here is a deterministic placeholder that drafts a
triage acknowledgement -- it never claims to execute an action itself,
which is exactly why the denylisted phrases in config/policy.json are
things like "wire transfer" or "close my account": those are actions a
human has to perform, and the agent should never sound like it already
did one. Swap `draft_triage_response` for a real Bedrock call (see the
companion project, agentic-research-assistant) to go from a demo to
a working agent; nothing else in this file needs to change.

Usage:
    uv run python -m src.cli --actor rep-42 "Customer is asking us to process a wire transfer"
    uv run python -m src.cli --actor rep-42 "Customer can't find their December statement"
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .cost_tracker import BudgetExceededError, CostTracker
from .guardrail import GuardedAgent, PolicyViolationError
from .policy import PolicyEngine

DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "config" / "policy.json"
DEFAULT_STATE_PATH = Path(__file__).resolve().parent.parent / "state" / "cost_state.json"
DEFAULT_DAILY_BUDGET_USD = 5.00


def draft_triage_response(ticket_text: str) -> str:
    """Placeholder for a real LLM call. Always drafts for human review --
    never claims to have taken action, since the agent's only job here is
    triage, not execution."""
    preview = ticket_text.strip().splitlines()[0][:80]
    return (
        f"[DRAFT -- human review required] Thanks for reaching out about: "
        f"\"{preview}\". A member of our support team will follow up shortly."
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("message", help="The support ticket text to triage")
    parser.add_argument(
        "--actor",
        required=True,
        help="Support rep or system identifier for budget/audit tracking",
    )
    parser.add_argument(
        "--policy",
        default=str(DEFAULT_POLICY_PATH),
        help="Path to a policy config JSON file",
    )
    parser.add_argument(
        "--state",
        default=str(DEFAULT_STATE_PATH),
        help="Path to persisted cost-tracker state",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=DEFAULT_DAILY_BUDGET_USD,
        help=f"Budget ceiling in USD for this actor (default: ${DEFAULT_DAILY_BUDGET_USD:.2f})",
    )
    args = parser.parse_args(argv)

    policy = PolicyEngine.from_config(args.policy)
    cost_tracker = CostTracker.load(args.state)
    cost_tracker.set_budget(args.actor, args.budget)

    agent = GuardedAgent(call_fn=draft_triage_response, policy=policy, cost_tracker=cost_tracker)

    try:
        result = agent.invoke(args.message, actor=args.actor)
    except PolicyViolationError as exc:
        print(f"BLOCKED (policy): {exc}")
        cost_tracker.save(args.state)
        return 1
    except BudgetExceededError as exc:
        print(f"BLOCKED (budget): {exc}")
        cost_tracker.save(args.state)
        return 1

    cost_tracker.save(args.state)
    print(result.output)
    print(f"\n(estimated cost: ${result.estimated_cost_usd:.6f} | "
          f"actor spend so far: ${cost_tracker.spend_so_far(args.actor):.6f} "
          f"of ${args.budget:.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
