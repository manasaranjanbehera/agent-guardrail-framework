"""Append-only JSONL audit trail for every guarded agent call.

One line per call, safe to tail, grep, or ship to a log aggregator.
Only ever stores redacted text (see pii.py) -- never raw PII.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class AuditEntry:
    actor: str
    redacted_input: str
    redacted_output: str
    allowed: bool
    policy_reason: str | None
    estimated_cost_usd: float
    call_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = field(default_factory=time.time)


class AuditLogger:
    """Keeps entries in memory (for inspection/tests) and optionally
    appends each one as a JSON line to `log_path`."""

    def __init__(self, log_path: Path | None = None) -> None:
        self.log_path = Path(log_path) if log_path else None
        self.entries: list[AuditEntry] = []

    def log(self, entry: AuditEntry) -> None:
        self.entries.append(entry)
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry)) + "\n")
