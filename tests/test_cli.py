"""Tests src/cli.py end-to-end via its main() function -- no subprocess,
no real AWS, just a temp policy config and a temp state file per test."""
import json

from src.cli import main


def _write_policy(tmp_path, denylist):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"denylist": denylist}))
    return path


def test_normal_ticket_succeeds_and_persists_state(tmp_path, capsys):
    policy_path = _write_policy(tmp_path, ["wire transfer"])
    state_path = tmp_path / "state.json"

    exit_code = main(
        [
            "Customer can't find their December statement",
            "--actor", "rep-42",
            "--policy", str(policy_path),
            "--state", str(state_path),
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "DRAFT" in out
    assert "estimated cost" in out
    assert state_path.exists()
    saved = json.loads(state_path.read_text())
    assert saved["spend"]["rep-42"] > 0


def test_restricted_ticket_is_blocked_and_exits_nonzero(tmp_path, capsys):
    policy_path = _write_policy(tmp_path, ["wire transfer"])
    state_path = tmp_path / "state.json"

    exit_code = main(
        [
            "Please process a wire transfer today",
            "--actor", "rep-42",
            "--policy", str(policy_path),
            "--state", str(state_path),
        ]
    )

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "BLOCKED (policy)" in out
    assert "wire transfer" in out


def test_over_budget_ticket_is_blocked_and_exits_nonzero(tmp_path, capsys):
    policy_path = _write_policy(tmp_path, [])
    state_path = tmp_path / "state.json"

    exit_code = main(
        [
            "A perfectly normal ticket",
            "--actor", "rep-42",
            "--policy", str(policy_path),
            "--state", str(state_path),
            "--budget", "0.0000001",
        ]
    )

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "BLOCKED (budget)" in out


def test_spend_persists_across_separate_main_calls(tmp_path, capsys):
    policy_path = _write_policy(tmp_path, [])
    state_path = tmp_path / "state.json"
    common_args = ["--actor", "rep-42", "--policy", str(policy_path), "--state", str(state_path)]

    main(["First ticket", *common_args])
    first_spend = json.loads(state_path.read_text())["spend"]["rep-42"]

    main(["Second ticket", *common_args])
    second_spend = json.loads(state_path.read_text())["spend"]["rep-42"]

    assert second_spend > first_spend
