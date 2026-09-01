# Contributing

Thanks for your interest in this project.

## Development setup

```bash
uv sync
```

No API keys or cloud credentials are required. The full test suite runs offline
against stdlib-only code.

## Quality checks

Before opening a pull request, run:

```bash
make lint
make test
```

Or directly:

```bash
uv run ruff check src tests examples
uv run pytest -v
```

## Pull requests

1. Fork the repository and create a feature branch from `main`.
2. Make your changes and add or update tests when behavior changes.
3. Confirm lint and tests pass locally.
4. Open a pull request using the provided template.

CI runs automatically on pull requests (Ruff + pytest on Python 3.10–3.12) and
must pass before merge.

## Reporting issues

Use the GitHub issue templates for bug reports and feature requests. Include
steps to reproduce, expected behavior, and what you observed instead.

For security-sensitive reports, see [SECURITY.md](SECURITY.md).
