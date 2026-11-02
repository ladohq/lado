The plan with each task's tests: `docs/superpowers/plans/2026-11-02-session-model.md`.

## 1. Core

- [ ] 1.1 `sessions.power` (schema 37, checked against main's at each merge of the base),
  `PowerRow`/`PowerTable`, `Session.power`, the source `session`, `Choice.name` optional;
  `previous_schema` undoes it (D1, D2, D12). Check: `tests/test_state.py`,
  `tests/test_cli.py -k schema`.
- [ ] 1.2 `Provider.same_model` (Claude's aliases), `report_model` keeps the source for an
  alias's full name and for a first name (D6). Check: `tests/test_state.py`,
  `tests/test_providers.py`.
- [ ] 1.3 `AgentSpec.model`, `runtime.session_model`, each provider applies it (Claude
  `--model`, Codex config.toml top level and profile, OpenCode/Kilo config content, the
  fake provider), the other CLI's note and warning (D3, D4, D5). Check:
  `tests/test_providers.py`, `tests/test_codex.py`, `tests/test_runtime.py`.
- [ ] 1.4 `model_check.py`, `Provider.model_list` per provider (D7). Check:
  `tests/test_model_check.py`, `tests/test_providers.py`, `tests/test_codex.py`.

## 2. Interfaces

- [ ] 2.1 `start_session(model=)`: check, keep, drop, provider change, changes line;
  `lado start --model` (D8, D9). Check: `tests/test_runtime.py`, `tests/test_cli.py`.
- [ ] 2.2 `Launch.model`, `Resume.model`, `SessionInfo.model`, `GET
  /api/providers/{name}/models`, `make web-types` (D10). Check:
  `tests/test_server_launch.py`, `tests/test_server_providers.py`, `make web`.
- [ ] 2.3 Integration with the fake agent: the model to the agent, `lado.db`,
  `list_agents`, the API; a refusal; a worker of another provider. Check: `uv run pytest
  -m integration -n auto <the changed files>`.

## 3. UI

- [ ] 3.1 The Model field in Advanced (New session, Resume), its notes, suggestions,
  Start off, the folded summary (D11). Check: `web/src/Launch.test.tsx`, `make web`.
- [ ] 3.2 UI e2e of the field and the agent's page; screenshots as run artifacts. Check:
  `uv run pytest -m ui tests/ui/test_launch.py tests/ui/test_agents_tab.py`.

## 4. Smoke, docs and regression

- [ ] 4.1 Smoke per provider: the model reaches the real CLI's argv or config. Check: CI's
  smoke cells (written, not run locally).
- [ ] 4.2 `docs/cli.md`, `docs/design/ui.md`, `docs/design/agents.md`,
  `docs/design/modules.md`, CHANGELOG under `## 0.45.0 (unreleased)`.
- [ ] 4.3 Regression: `make lint`, `make test`, `make web`, changed integration and UI
  files with their markers, `openspec validate session-model --strict`, `openspec
  validate --specs --strict`, CI green.
