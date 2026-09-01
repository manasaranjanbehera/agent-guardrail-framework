# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-01

### Added

- `GuardedAgent` wrapper: policy checks, budget enforcement, and PII-redacted audit logging
- `PolicyEngine` with JSON config denylist and pluggable custom rules
- `CostTracker` with per-model pricing, per-actor budgets, and JSON persistence
- PII redaction for email, SSN, credit card, and phone patterns
- Append-only JSONL audit trail
- CLI entry point (`uv run python -m src.cli`) and support-ticket-triage example
- Full pytest suite (no network or cloud credentials required)
- uv-based dependency management with locked installs
- GitHub Actions CI matrix on Python 3.10–3.12 (lint + test)

[0.1.0]: https://github.com/manasaranjanbehera/agent-guardrail-framework/releases/tag/v0.1.0
