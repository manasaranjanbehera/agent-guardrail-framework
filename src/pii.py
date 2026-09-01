"""Lightweight PII detection and redaction.

Deliberately regex-based and dependency-free so it can run inline on
every agent call with negligible latency. This is intentionally a
heuristic, not a guarantee: for production use with stricter recall
requirements, swap in Amazon Comprehend PII detection or AWS Bedrock
Guardrails -- `redact()` is designed to be a drop-in replacement
target (same signature: str -> str).
"""
from __future__ import annotations

import re

# Order matters: more specific patterns run first so a generic digit
# run (credit_card / phone) doesn't get a chance to partially match
# text that a more specific pattern (ssn) should own instead.
_PATTERNS = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]?){13,16}\d\b")),
    ("PHONE", re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
]


def redact(text: str) -> str:
    """Replace detected PII with a `[REDACTED:<TYPE>]` placeholder."""
    redacted = text
    for label, pattern in _PATTERNS:
        redacted = pattern.sub(f"[REDACTED:{label}]", redacted)
    return redacted


def contains_pii(text: str) -> bool:
    return any(pattern.search(text) for _, pattern in _PATTERNS)
