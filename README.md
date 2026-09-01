# Agent Guardrail & Audit Framework

A model-agnostic wrapper layer that puts **policy enforcement, PII-redacted
audit logging, and per-actor cost/budget control** around any agent or LLM
call — AWS Bedrock, LangChain, a plain function, anything with a
`(prompt: str) -> str` shape.

This is the piece most "agentic AI" freelance work skips, and the strongest
differentiator in this portfolio: production agent deployments in regulated
or cost-sensitive environments need these controls *around* the model call,
not bolted on afterward as a logging afterthought.

## What it actually does

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
│ 2. Budget check       │──▶ over budget? raise BudgetExceededError, log it, STOP
│    (before the model) │
└──────────┬────────────┘
           ▼
┌─────────────────────┐
│ 3. call_fn(prompt)    │  ← the ONLY line that touches your actual agent/model
└──────────┬────────────┘
           ▼
┌─────────────────────┐
│ 4. Policy check        │──▶ disallowed output? block it before it reaches
│    (on the response)   │     the caller, log "[BLOCKED OUTPUT]" not the text
└──────────┬──────────────┘
           ▼
┌─────────────────────┐
│ 5. Cost tracked,       │
│    audit entry logged  │  (input/output are PII-redacted before logging —
│    (JSONL, append-only)│   raw PII is never written to disk)
└──────────┬──────────────┘
           ▼
      GuardedResult(output, estimated_cost_usd, call_id)
```

## Modules
- `src/pii.py` — regex-based detection/redaction (email, SSN, credit card,
  phone). Explicitly a heuristic; the docstring says exactly what to swap in
  (Amazon Comprehend PII / Bedrock Guardrails) for production-grade recall.
- `src/policy.py` — keyword denylist + pluggable custom rule callables,
  checked on both the prompt and the response.
- `src/cost_tracker.py` — per-model $/1K-token pricing table, a documented
  chars/4 token-count approximation, and per-actor budget caps that block
  a call *before* it spends money, not after.
- `src/audit_log.py` — append-only JSONL audit trail; one line per call.
- `src/guardrail.py` — `GuardedAgent`, the class that wires all of the above
  around a `call_fn`.

## Why this design is a portfolio piece, not a toy
- **Model-agnostic on purpose**: `call_fn` is just `Callable[[str], str]`.
  Wrapping the Bedrock research pipeline from
  `../01-agentic-research-assistant` needs zero changes to this package —
  see `examples/wrap_any_agent.py` for the one-line adapter.
- **Fails closed, not open**: policy and budget checks happen *before* the
  underlying model is called, so a blocked request never costs money or
  reaches the model at all (verified in `tests/test_guardrail.py` by
  asserting the wrapped function was never invoked).
- **Audit log never contains raw PII** — enforced in code, not just policy;
  `tests/test_guardrail.py::test_audit_log_never_stores_raw_pii` checks this
  directly rather than trusting the docstring.
- **21 unit tests, zero AWS dependency** — this whole package has no
  third-party runtime dependency at all (stdlib only; `pytest` is dev-only),
  so it's trivial for a client to audit and drop into any stack.

## Setup & run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

pytest -v                              # 21 tests, no AWS/network required
PYTHONPATH=. python examples/wrap_any_agent.py   # see it wrap a fake agent end-to-end
```

## Extending this for a client engagement
- Point `PolicyEngine.custom_rules` at a client's specific compliance rules
  (e.g. block requests referencing specific internal system names).
- Swap `pii.redact` for Amazon Comprehend / Bedrock Guardrails when recall
  on rarer PII types (passport numbers, medical record numbers, etc.)
  matters more than the zero-dependency footprint.
- Point `AuditLogger` at CloudWatch Logs or a database instead of a local
  JSONL file for multi-instance deployments.
- Wrap the Researcher/Summarizer/Critic pipeline in
  `../01-agentic-research-assistant` agent-by-agent instead of end-to-end,
  so each stage gets its own budget and policy profile.
