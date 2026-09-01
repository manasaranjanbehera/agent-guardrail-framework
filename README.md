# Agent Guardrail & Audit Framework

[![CI](https://img.shields.io/github/actions/workflow/status/manasaranjanbehera/agent-guardrail-framework/ci.yml?branch=main&label=CI)](https://github.com/manasaranjanbehera/agent-guardrail-framework/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![uv-managed](https://img.shields.io/badge/deps-uv-DE5FE9)](https://github.com/astral-sh/uv)

A model-agnostic wrapper layer that puts **policy enforcement, PII-redacted
audit logging, and per-actor cost/budget control** around any agent or LLM
call — AWS Bedrock, LangChain, a plain function, anything with a
`(prompt: str) -> str` shape.

## The problem this solves

A bank wants an AI agent to triage incoming customer support tickets:
draft a first response, summarize the issue for a human rep, and flag
anything urgent. Three requirements come with that, straight from
compliance and support ops:

1. **The agent must never sound like it executed a restricted action** —
   wire transfers, account closures, card reissues, fraud-hold overrides —
   those require a human to actually perform them. If a customer's message
   asks for one, the agent should be stopped before it drafts a response
   that could be mistaken for a confirmation, not just flagged afterward.
2. **Customer PII (SSNs, card numbers, phone numbers) must never end up in
   the audit trail**, even though the rep reviewing a draft needs to see
   the real ticket to actually help the customer.
3. **Each support rep's AI usage has a budget**, and going over it should
   stop future calls from that rep, with a full, persistent record of what
   was asked, what was blocked, and what it cost — not just for this
   process's lifetime, but across restarts and deploys.

This project is that control layer: a wrapper any agent implementation can
sit behind, plus a runnable CLI (`src/cli.py`) and a JSON policy config
(`config/policy.json`) that a compliance team can edit without touching
application code, built around exactly this scenario.

## Quick start

```bash
uv sync
uv run pytest -v
uv run python -m src.cli --actor rep-42 "A normal ticket"
uv run python -m examples.support_ticket_triage
```

Or use the Makefile shortcuts:

```bash
make install
make lint
make test
make run PROMPT="Customer can't find their December statement"
```

No API keys or cloud credentials are required — the full test suite runs
offline.

## How it works

```
prompt
  │
  ▼
┌─────────────────────┐
│ 1. Policy check      │──▶ blocked? raise PolicyViolationError, log it, STOP
│    (before the model)│      (the model is never called — no wasted spend)
└──────────┬───────────┘
           ▼
┌─────────────────────┐
│ 2. Budget check       │──▶ already over budget? raise BudgetExceededError,
│    (pre-call estimate)│      log it, STOP (estimate covers the prompt only)
└──────────┬────────────┘
           ▼
┌─────────────────────┐
│ 3. call_fn(prompt)    │  ← the only line that touches the wrapped agent/model
└──────────┬────────────┘
           ▼
┌─────────────────────┐
│ 4. Policy check        │──▶ disallowed output? block it before it reaches
│    (on the response)   │     the caller, log "[BLOCKED OUTPUT]" not the text
└──────────┬──────────────┘
           ▼
┌─────────────────────┐
│ 5. Budget re-check     │──▶ real cost pushes actor over budget? block the
│    (real cost)         │     output too, but spend is still recorded
└──────────┬──────────────┘
           ▼
┌─────────────────────┐
│ 6. Cost recorded,      │  (input/output are PII-redacted before logging —
│    audit entry logged  │   raw PII is never written to disk)
│    (JSONL, append-only)│
└──────────┬──────────────┘
           ▼
      GuardedResult(output, estimated_cost_usd, call_id)
```

Calling `GuardedAgent.invoke(prompt, actor)` (`src/guardrail.py`) runs the
six steps above in order:

1. **Policy check on the prompt.** `PolicyEngine.check()` (`src/policy.py`)
   runs a keyword denylist and any custom rule callables. A blocked prompt
   raises `PolicyViolationError` immediately and is logged — the underlying
   `call_fn` is never invoked.
2. **Budget check (pre-call estimate).** `CostTracker.estimate_cost()`
   (`src/cost_tracker.py`) estimates the cost of the call from the prompt
   alone — the response doesn't exist yet — and `check_budget()` raises
   `BudgetExceededError` if the actor is already over budget before
   `call_fn` runs.
3. **The wrapped call.** `call_fn(prompt)` executes — this is the only step
   that touches the actual model or agent.
4. **Policy check on the response.** The output is checked the same way the
   prompt was. A disallowed response is blocked before it reaches the
   caller; the audit log records `"[BLOCKED OUTPUT]"` rather than the text.
5. **Budget re-checked against the real cost.** The pre-call estimate only
   covers the prompt; once the actual response exists, the real cost
   (input + output) is checked against budget again. A response that pushes
   the actor over budget is blocked from being returned — but the spend is
   always recorded, since the model call already happened and already cost
   money either way.
6. **Cost recorded, audit entry logged.** The actual cost is added to the
   actor's running spend, and an `AuditEntry` is written (`src/audit_log.py`)
   with the prompt and response redacted of PII (`src/pii.py`) before they
   are ever written to disk.

## Configuration: `config/policy.json`

Restricted phrases live in a JSON file, not hardcoded Python, so the
support-ops or compliance team that owns the policy can change it without
a code deploy or a redeploy of this package:

```json
{
  "version": "1.0",
  "updated": "2026-09-01",
  "description": "Restricted actions for the AI support-ticket triage agent...",
  "denylist": ["wire transfer", "close my account", "unlock my card", "..."]
}
```

Load it with `PolicyEngine.from_config("config/policy.json")`. Only the
denylist is config-driven — custom rule callables are Python and can't be
serialized, so pass them separately: `PolicyEngine.from_config(path,
custom_rules=[...])`.

## Persistence: `CostTracker.save()` / `.load()`

An in-memory spend counter resets every time the process restarts, which
makes budget enforcement meaningless in anything long-running. `CostTracker`
persists recorded spend to a JSON file:

```python
tracker = CostTracker.load("state/cost_state.json", budgets={"rep-42": 5.00})
# ... use the tracker via GuardedAgent ...
tracker.save("state/cost_state.json")
```

A missing state file is the expected first run (starts at zero spend); a
corrupted one starts fresh too, but with a loud `UserWarning` instead of
silently discarding what should have been real history. There is
deliberately **no automatic period reset** (daily, monthly, etc.) — what
"period" means and when it rolls over is an organizational policy decision,
not something to guess at in a library. Resetting a period is as simple as
deleting or archiving the state file on whatever cadence your organization
uses.

## Command-line usage

`src/cli.py` wires the policy config, persistent cost tracker, and a
`GuardedAgent` together against the scenario above. The wrapped "agent" is
a deterministic placeholder that drafts a triage acknowledgement for human
review — swap `draft_triage_response` for a real Bedrock call (see the
companion project, [agentic-research-assistant](https://github.com/manasaranjanbehera/agentic-research-assistant)) to go from a demo to a
working agent; nothing else needs to change.

```bash
uv run python -m src.cli --actor rep-42 "Customer can't find their December statement"
# [DRAFT -- human review required] Thanks for reaching out about: "..."
# (estimated cost: $0.000648 | actor spend so far: $0.000648 of $5.00)

uv run python -m src.cli --actor rep-42 "Please process a wire transfer of $5,000"
# BLOCKED (policy): denylisted term matched: 'wire transfer'
```

State persists in `state/cost_state.json` between runs (gitignored — it's
runtime data, not source). Flags: `--policy` (default `config/policy.json`),
`--state` (default `state/cost_state.json`), `--budget` (default `$5.00`).

## Modules
- `src/pii.py` — regex-based detection/redaction (email, SSN, credit card,
  phone). Explicitly a heuristic; the docstring says exactly what to swap in
  (Amazon Comprehend PII / Bedrock Guardrails) for production-grade recall.
- `src/policy.py` — keyword denylist + pluggable custom rule callables,
  checked on both the prompt and the response; loadable from a JSON config.
- `src/cost_tracker.py` — per-model $/1K-token pricing table, a documented
  chars/4 token-count approximation, per-actor budget caps, and JSON-based
  save/load so spend survives a restart.
- `src/audit_log.py` — append-only JSONL audit trail; one line per call.
- `src/guardrail.py` — `GuardedAgent`, the class that wires all of the above
  around a `call_fn`.
- `src/cli.py` — runnable entry point tying policy, persistence, and
  `GuardedAgent` together against the support-ticket-triage scenario.
- `config/policy.json` — the sample policy config for that scenario.

## Design notes
- **Model-agnostic on purpose**: `call_fn` is just `Callable[[str], str]`.
  Wrapping the Bedrock research pipeline from
  [agentic-research-assistant](https://github.com/manasaranjanbehera/agentic-research-assistant) needs zero changes to this package — see
  `src/cli.py`'s docstring for the one-line swap.
- **Fails closed, not open**: policy and budget checks happen *before* the
  underlying model is called, so a blocked request never costs money or
  reaches the model at all (verified in `tests/test_guardrail.py` by
  asserting the wrapped function was never invoked).
- **Audit log never contains raw PII** — enforced in code, not just policy;
  `tests/test_guardrail.py::test_audit_log_never_stores_raw_pii` checks this
  directly rather than relying on the docstring.
- **Denylist matching is word-boundary based, not substring**: a term like
  `"ssn"` matches "what's my SSN" but not "assassin" (`src/policy.py`).
- **Budget enforcement is two-stage**: a cheap pre-call estimate catches
  requests that are already over budget, and a post-call recheck against the
  real cost catches a response that turns out larger than expected — see
  `tests/test_guardrail.py::test_actual_cost_over_budget_blocks_output_even_though_prompt_looked_affordable`.
- **Unknown model IDs don't fail silently**: `CostTracker.estimate_cost()`
  emits a `UserWarning` when a `model_id` isn't in the pricing table instead
  of quietly estimating with the wrong price.
- **Persistence adds no new dependency**: config and state are both plain
  JSON via the standard library — the "zero third-party runtime dependency"
  property holds even with config-driven policy and durable budget tracking.
- **Not thread-safe**: `CostTracker`'s check-then-record is not atomic —
  concurrent calls for the same actor can both pass a budget check before
  either records spend. Add a lock around that pair if used from multiple
  threads against a shared tracker.
- **41 unit tests, zero third-party runtime dependency** — stdlib only
  (`pytest` is dev-only), so the logic is straightforward to audit and drop
  into any stack.

## Project structure

```
agent-guardrail-framework/
├── .github/
│   ├── workflows/ci.yml       # Ruff + pytest on Python 3.10–3.12
│   ├── dependabot.yml
│   ├── pull_request_template.md
│   └── ISSUE_TEMPLATE/
├── config/
│   └── policy.json            # Editable denylist for compliance teams
├── examples/
│   ├── __init__.py
│   └── support_ticket_triage.py
├── src/
│   ├── audit_log.py           # Append-only JSONL audit trail
│   ├── cli.py                 # Runnable CLI entry point
│   ├── cost_tracker.py        # Per-actor budgets and model pricing
│   ├── guardrail.py           # GuardedAgent wrapper
│   ├── pii.py                 # PII detection and redaction
│   └── policy.py              # PolicyEngine and JSON config loader
├── state/                     # Runtime cost persistence (gitignored)
├── tests/
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── Makefile
├── pyproject.toml
├── SECURITY.md
└── uv.lock
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports and feature requests use the
GitHub issue templates. Security issues: [SECURITY.md](SECURITY.md).

## License

MIT — see [LICENSE](LICENSE). Release history: [CHANGELOG.md](CHANGELOG.md).

## Possible extensions
- Swap `pii.redact` for Amazon Comprehend / Bedrock Guardrails when recall
  on rarer PII types (passport numbers, medical record numbers, etc.)
  matters more than the zero-dependency footprint.
- Point `AuditLogger` at CloudWatch Logs or a database instead of a local
  JSONL file for multi-instance deployments.
- Add an explicit period-reset mechanism (daily/monthly) on top of
  `CostTracker`'s persistence, once a specific organization's reset cadence
  is known — deliberately not guessed at in the library itself (see
  Persistence, above).
- Wrap the Researcher/Summarizer/Critic pipeline in
  [agentic-research-assistant](https://github.com/manasaranjanbehera/agentic-research-assistant) agent-by-agent instead of end-to-end, so
  each stage gets its own budget and policy profile.
