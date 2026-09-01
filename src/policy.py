"""Pre/post-call policy checks.

The point of this module: policy is enforced *before* a disallowed
request reaches the model and *before* a disallowed response reaches
the caller -- not just logged after the fact for someone to review
later.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Optional


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: Optional[str] = None


class PolicyEngine:
    """Keyword denylist plus optional custom rule callables.

    Custom rules are `(text) -> Optional[str]`: return a violation
    reason string to block, or None to allow.
    """

    def __init__(
        self,
        denylist: Optional[Iterable[str]] = None,
        custom_rules: Optional[Iterable[Callable[[str], Optional[str]]]] = None,
    ) -> None:
        self.denylist = [term.lower() for term in (denylist or [])]
        self.custom_rules = list(custom_rules or [])

    def check(self, text: str) -> PolicyDecision:
        lowered = text.lower()
        for term in self.denylist:
            if term in lowered:
                return PolicyDecision(allowed=False, reason=f"denylisted term matched: '{term}'")
        for rule in self.custom_rules:
            reason = rule(text)
            if reason:
                return PolicyDecision(allowed=False, reason=reason)
        return PolicyDecision(allowed=True)
