# Security Policy

## Reporting a vulnerability

If you discover a security issue, please report it privately rather than opening
a public GitHub issue.

Email **manasabehera5901@gmail.com** with:

- A description of the vulnerability
- Steps to reproduce
- Potential impact

You can expect an acknowledgment within a few business days. Please do not
disclose the issue publicly until we have had a chance to address it.

## Scope

This project is a library and CLI for policy enforcement, audit logging, and
budget control around agent/LLM calls. Security-relevant areas include:

- PII redaction before audit log writes
- Policy denylist matching and bypass resistance
- Budget enforcement correctness under concurrency

Known limitations (documented in the README) — such as heuristic PII detection
and non-atomic budget checks — are design trade-offs, not undisclosed
vulnerabilities.
