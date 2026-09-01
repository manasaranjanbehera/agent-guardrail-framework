"""Smoke-tests examples/support_ticket_triage.py: it should run end-to-end
and actually demonstrate what its docstring claims (PII redacted in the
audit trail, the restricted action blocked)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples"))

from support_ticket_triage import run_demo  # noqa: E402


def test_demo_redacts_ssn_and_blocks_wire_transfer(capsys):
    logger = run_demo()

    assert len(logger.entries) == 2
    assert logger.entries[0].allowed is True
    assert "123-45-6789" not in logger.entries[0].redacted_input
    assert "[REDACTED:SSN]" in logger.entries[0].redacted_input

    assert logger.entries[1].allowed is False
    assert logger.entries[1].policy_reason is not None
    assert "wire transfer" in logger.entries[1].policy_reason
