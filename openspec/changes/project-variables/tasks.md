The plan with each task's tests: `docs/superpowers/plans/2026-10-22-project-variables.md`.

## 1. Core

- [x] 1.1 The table `project_variables`, schema 34, its reads and writes,
  `previous_schema` (D1). Check: the state and migration tests.
- [x] 1.2 The name and value rule, `providers.base.CLI_VARIABLES`, `set_variable`,
  `unset_variable`, `running` (D2, D3, D6). Check: `tests/test_project_variables.py`
  (new), the test that each provider's launch variables are reserved.
- [x] 1.3 The project's layer in `agent_env.resolve` and `runtime._base_env` at a start, a
  resume and a spawn; the launch warning for a name LADO sets (D4, D5). Check: the
  agent_env and runtime unit tests.

## 2. CLI, server, doctor

- [x] 2.1 `lado project set|unset`, the variables in `show`, human only (D7). Check:
  the CLI tests.
- [ ] 2.2 `variables` in `GET /api/projects/{id}`, `PUT` and `DELETE
  /api/projects/{id}/variables/{name}`; `make web-types` (D8). Check:
  `tests/test_server_projects.py`, `make web`.
- [ ] 2.3 `lado doctor`'s `Project variables` line (D9). Check: `tests/test_doctor.py`.

## 3. End to end

- [ ] 3.1 `tests/integration/test_project_variables.py`: two projects, one name, each
  agent kind (supervisor, worker through MCP, flow run's worker, `start_session`) with its
  project's value; the layers' order with `LADO_ENV_DIR`; no project, no variable;
  `unset`; a kit key only in the project passes and reaches the server through
  `mcp_exec`, refused without; the warning for a name LADO sets. Check: `uv run pytest -m
  integration -n auto tests/integration/test_project_variables.py`.
- [ ] 3.2 The smoke's probe kit and test per provider (D10). Check: CI's smoke cells.

## 4. Documents and version

- [ ] 4.1 `docs/cli.md`, `docs/design/projects.md` (security boundary, #808),
  `docs/design/agents.md`, `docs/design/modules.md`, `docs/install.md` (D13). Check: `uv
  run pytest tests/test_agents_md.py`.
- [ ] 4.2 CHANGELOG: one line under `## 0.43.0 (unreleased)`.

## 5. Regression

- [ ] 5.1 `make lint`; `make test` (counts); the changed and neighbouring integration
  files (`test_outside_variables.py`, `test_project_sessions.py`,
  `test_project_repositories.py`, `test_agent_kits.py`); `make web`; `openspec validate
  --specs --strict`; the trial archive in a copy of `openspec/`; CI green with the
  container and smoke cells.
