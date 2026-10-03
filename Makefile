.PHONY: help lint fmt test test-integration test-js test-live test-ui web web-types dist browser check

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

test-ui: web browser ## UI end-to-end tests: Chromium against a real lado server, fake agent
	uv run pytest -m ui $(PYTEST_ARGS)

web: ## the web UI: install, check types, unit tests, build into src/lado/server/static
	cd web && npm ci --no-audit --no-fund
	@uv run python -m lado.server.app | diff -u web/openapi.json - \
		|| { echo "web/openapi.json is stale: run make web-types"; exit 1; }
	@cd web && npx openapi-typescript openapi.json 2>/dev/null | diff -u src/api.gen.ts - \
		|| { echo "web/src/api.gen.ts is stale: run make web-types"; exit 1; }
	cd web && npm run typecheck && npm test && npm run build

web-types: ## make web/openapi.json and the UI's TypeScript types from the server's API
	uv run python -m lado.server.app > web/openapi.json
	cd web && npm run types

dist: web ## build the sdist and the wheel into dist/ and check that both ship the web UI's bundle
	rm -rf dist && uv build
	@unzip -l dist/*.whl | grep -q ' lado/server/static/index.html$$' \
		|| { echo "the wheel has no lado/server/static/index.html"; exit 1; }
	@tar tzf dist/*.tar.gz | grep -q '/src/lado/server/static/index.html$$' \
		|| { echo "the sdist has no src/lado/server/static/index.html"; exit 1; }
	@echo "dist/: the sdist and the wheel ship the web UI's bundle"

browser: ## install Chromium for the UI tests (Playwright)
	uv run playwright install chromium

check: lint test-js web browser ## everything; run after your last change and when a merge brings new commits. Unit, integration and UI tests in one parallel run
	uv run pytest -m 'not live' $(PYTEST_ARGS)
