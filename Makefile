.PHONY: help lint fmt test test-integration test-js check

help: ## list the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-17s %s\n", $$1, $$2}'

lint: ## check formatting and lint
	uv run ruff format --check
	uv run ruff check

fmt: ## format and fix lint
	uv run ruff format
	uv run ruff check --fix

test: ## unit tests
	uv run pytest

test-integration: ## integration tests: real tmux, git and processes, fake agent, no LLM
	uv run pytest -m integration

test-js: ## Node tests of the Kilo plugin
	node --test tests/js/*.test.mjs

check: lint test test-integration test-js ## everything; run before a release
