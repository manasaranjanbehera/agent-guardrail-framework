.PHONY: install lint test run clean help

help:
	@echo "Targets:"
	@echo "  install  Sync dependencies with uv"
	@echo "  lint     Run Ruff linter"
	@echo "  test     Run the test suite"
	@echo "  run      Run the CLI (PROMPT=... ACTOR=rep-42 optional)"
	@echo "  clean    Remove local caches and virtualenv"

install:
	uv sync

lint:
	uv run ruff check src tests examples

test:
	uv run pytest -v

run:
	@test -n "$(PROMPT)" || (echo 'Usage: make run PROMPT="your ticket message here" [ACTOR=rep-42]' && exit 1)
	uv run python -m src.cli --actor $(or $(ACTOR),rep-42) "$(PROMPT)"

clean:
	rm -rf .venv .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
