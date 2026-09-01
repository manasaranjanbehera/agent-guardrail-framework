"""GuardedAgent: wraps any `call_fn(prompt: str) -> str` -- a Bedrock
Converse call, a LangChain chain, a plain function -- with policy
checks, PII-redacted audit logging, and per-actor cost/budget
enforcement.

This is the control layer described for regulated deployments: checks
implemented around the model client rather than inside it, so they
apply consistently no matter which foundation model or agent
framework sits underneath.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .audit_log import AuditEntry, AuditLogger
from .cost_tracker import BudgetExceededError, CostTracker
from .pii import redact
from .policy import PolicyEngine


class PolicyViolationError(Exception):
    pass


@dataclass
class GuardedResult:
    output: str
    estimated_cost_usd: float
    call_id: str


class GuardedAgent:
    def __init__(
        self,
        call_fn: Callable[[str], str],
        model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
        policy: PolicyEngine | None = None,
        cost_tracker: CostTracker | None = None,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        self.call_fn = call_fn
        self.model_id = model_id
        self.policy = policy or PolicyEngine()
        self.cost_tracker = cost_tracker or CostTracker()
        self.audit_logger = audit_logger or AuditLogger()

    def invoke(self, prompt: str, actor: str = "default") -> GuardedResult:
        redacted_prompt = redact(prompt)

        # 1. Policy check BEFORE the model ever sees the prompt.
        input_decision = self.policy.check(prompt)
        if not input_decision.allowed:
            self._log_blocked(actor, redacted_prompt, input_decision.reason)
            raise PolicyViolationError(input_decision.reason)

        # 2. Budget check BEFORE spending money on the call. This is only
        #    an input-only estimate -- the response doesn't exist yet, so
        #    it catches requests that are already over budget before any
        #    money is spent, but can't know the real cost of this call.
        projected_cost = self.cost_tracker.estimate_cost(self.model_id, prompt)
        try:
            self.cost_tracker.check_budget(actor, projected_cost)
        except BudgetExceededError as exc:
            self._log_blocked(actor, redacted_prompt, str(exc))
            raise

        # 3. The actual call -- this is the only line that touches the model.
        output = self.call_fn(prompt)

        # 4. Policy check on the OUTPUT too, before it reaches the caller.
        output_decision = self.policy.check(output)
        redacted_output = redact(output)
        cost = self.cost_tracker.estimate_cost(self.model_id, prompt, output)

        # 5. Re-check budget against the REAL cost (input + actual output),
        #    not just the pre-call estimate: a long or expensive response
        #    can still push an actor over budget even when the prompt alone
        #    looked affordable. The call has already happened, so the spend
        #    is always recorded either way -- but a call that lands the
        #    actor over budget is blocked from being returned, the same way
        #    a disallowed policy output is, so the overage is caught at the
        #    next possible moment instead of silently accepted.
        try:
            self.cost_tracker.check_budget(actor, cost)
            budget_exceeded_reason: str | None = None
        except BudgetExceededError as exc:
            budget_exceeded_reason = str(exc)
        self.cost_tracker.record_spend(actor, cost)

        allowed = output_decision.allowed and budget_exceeded_reason is None
        block_reason = (
            output_decision.reason if not output_decision.allowed else budget_exceeded_reason
        )

        entry = AuditEntry(
            actor=actor,
            redacted_input=redacted_prompt,
            redacted_output=redacted_output if allowed else "[BLOCKED OUTPUT]",
            allowed=allowed,
            policy_reason=block_reason,
            estimated_cost_usd=cost,
        )
        self.audit_logger.log(entry)

        if not output_decision.allowed:
            raise PolicyViolationError(output_decision.reason)
        if budget_exceeded_reason:
            raise BudgetExceededError(budget_exceeded_reason)

        return GuardedResult(output=output, estimated_cost_usd=cost, call_id=entry.call_id)

    def _log_blocked(self, actor: str, redacted_prompt: str, reason: str | None) -> None:
        entry = AuditEntry(
            actor=actor,
            redacted_input=redacted_prompt,
            redacted_output="",
            allowed=False,
            policy_reason=reason,
            estimated_cost_usd=0.0,
        )
        self.audit_logger.log(entry)
