.PHONY: help lint fmt test test-integration test-js test-live check

# Unit and integration tests run on one pytest worker per CPU (pytest-xdist). To debug a
# test serially, with its output in order: make test PYTEST_ARGS=-n0 (or any pytest options).
PYTEST_ARGS ?= -n auto

help: ## list the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-17s %s\n", $$1, $$2}'

lint: ## check formatting and lint
	uv run ruff format --check
	uv run ruff check

fmt: ## format and fix lint
	uv run ruff format
	uv run ruff check --fix

test: ## unit tests, in parallel (PYTEST_ARGS=-n0: serially)
	uv run pytest $(PYTEST_ARGS)

test-integration: ## integration tests: real tmux, git and processes, fake agent, no LLM; in parallel
	uv run pytest -m integration $(PYTEST_ARGS)

test-js: ## Node tests of the Kilo plugin
	node --test tests/js/*.test.mjs

test-live: ## live e2e tests with real agent CLIs and models, serially; PROVIDER=kilo|claude picks one
	uv run pytest -m live -n0 $(if $(PROVIDER),-k $(PROVIDER)) -v

check: lint test-js ## everything; run before a release. Unit and integration tests in one parallel run
	uv run pytest -m 'not live' $(PYTEST_ARGS)
