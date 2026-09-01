"""Pre/post-call policy checks.

The point of this module: policy is enforced *before* a disallowed
request reaches the model and *before* a disallowed response reaches
the caller -- not just logged after the fact for someone to review
later.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str | None = None


class PolicyEngine:
    """Keyword denylist plus optional custom rule callables.

    Denylist terms are matched as whole words/phrases (case-insensitive,
    word-boundary matching), not as raw substrings -- a denylisted term
    like "ssn" matches "what's my SSN" but not "assassin".

    Custom rules are `(text) -> Optional[str]`: return a violation
    reason string to block, or None to allow.
    """

    def __init__(
        self,
        denylist: Iterable[str] | None = None,
        custom_rules: Iterable[Callable[[str], str | None]] | None = None,
    ) -> None:
        self.denylist = [term.lower() for term in (denylist or [])]
        self._denylist_patterns = [
            (term.lower(), re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE))
            for term in (denylist or [])
        ]
        self.custom_rules = list(custom_rules or [])

    @classmethod
    def from_config(
        cls,
        path: str | Path,
        custom_rules: Iterable[Callable[[str], str | None]] | None = None,
    ) -> PolicyEngine:
        """Build a PolicyEngine from a JSON policy file (see config/policy.json
        for the shape). Only the denylist is config-driven -- custom_rules are
        Python callables and can't be serialized, so pass them separately if
        needed.

        Kept to plain JSON (not YAML) deliberately: no extra dependency to
        read a config file that's really just a list of strings.
        """
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"policy config not found: {config_path}")
        try:
            data = json.loads(config_path.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(f"policy config at {config_path} is not valid JSON: {exc}") from exc
        denylist = data.get("denylist", [])
        return cls(denylist=denylist, custom_rules=custom_rules)

    def check(self, text: str) -> PolicyDecision:
        for term, pattern in self._denylist_patterns:
            if pattern.search(text):
                return PolicyDecision(allowed=False, reason=f"denylisted term matched: '{term}'")
        for rule in self.custom_rules:
            reason = rule(text)
            if reason:
                return PolicyDecision(allowed=False, reason=reason)
        return PolicyDecision(allowed=True)
