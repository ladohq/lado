The plan with each task's tests: `docs/superpowers/plans/2026-11-01-agent-model-visible.md`.

## 1. Core

- [x] 1.1 Six columns of `agents`, schema 36 (checked against main's at each merge of the
  base), `Agent` fields, `source_words`, `set_model`;
  `previous_schema` undoes it (D1, D2). Check: `tests/test_state.py`, `tests/test_cli.py
  -k schema`.
- [x] 1.2 `Event.model`/`effort`, `state.report_model`, `hooks.handle` records it (D4, D5).
  Check: `tests/test_state.py`, the hooks' unit tests.
- [x] 1.3 `Choice` (in `state.py`, beside `Agent`: `base` imports `state`, and `set_model`
  takes it), `Launch.model`/`effort`; Codex's carried model and effort by the
  profile rule; each provider's `parse_event`; `runtime` records a launch's choice (D3, D4).
  Check: `tests/test_codex.py`, `tests/test_providers.py`, `tests/test_runtime.py`.
- [x] 1.4 The plugin's `chat.message` payload gets `model` and `variant` (D4). Check:
  `make test-js`.

## 2. Interfaces

- [x] 2.1 `list_agents` fields, `AgentInfo.model`/`effort` (`ModelInfo`), `make
  web-types` (D6, D7). Check: `tests/test_mcp_server.py`, `tests/test_server_agents.py`,
  `make web`.
- [x] 2.2 The fake agent reports a model; integration test from the event to `lado.db`,
  `list_agents` and the API. Check: `uv run pytest -m integration -n auto
  tests/integration/test_agents.py tests/integration/test_fake_agent.py`.

## 3. UI and CLI

- [x] 3.1 The agent's page (head line, Model, Effort), the Team tooltip, `lado ls` (D8,
  D9). Check: `web/src/Agents.test.tsx`, `web/src/Team.test.tsx`, `tests/test_cli.py`,
  `make web`.
- [x] 3.2 UI e2e of the page with and without a model; screenshots as run artifacts.
  Check: `uv run pytest -m ui tests/ui/test_agents_tab.py`.

## 4. Docs and regression

- [x] 4.1 `docs/design/agents.md`, `docs/design/ui.md`, `docs/cli.md`,
  `docs/design/modules.md`, CHANGELOG: the heading `## 0.45.0 (unreleased)` added above `## 0.44.0`,
  the line under it (Added), BACKLOG's "Choose
  the model per agent" → LAD-154.
- [ ] 4.2 Regression: `make lint`, `make test`, `make web`, `make test-js`, the changed
  integration and UI files with their markers, `openspec validate --specs --strict`; CI
  green.
