The plan with each task's tests: `docs/superpowers/plans/2026-10-23-project-secrets.md`.

## 1. Core

- [x] 1.1 One reader for the outside folder and a project's secrets folder, with the
  project's checks (no link, no loose mode, the project's reserved names) (D8). Check:
  `tests/test_agent_env.py`.
- [x] 1.2 `project_secrets.py`: the data folder, atomic writes, link-safe removal (D1, D2,
  D3). Check: `tests/test_project_secrets.py` (new), each link × operation.
- [x] 1.3 `projects`: `check_name`, `set_secret`, one value per name, `unset` of either
  kind, `create` refusing a left data folder, `delete` removing it (D4, D5, D10). Check:
  `tests/test_project_variables_core.py`, the projects' create/delete tests.
- [ ] 1.4 The project's layer with secrets in `runtime._base_env`, the launch warnings
  (D7). Check: the runtime unit tests.

## 2. CLI, server, doctor

- [ ] 2.1 `lado project set --secret` (prompt, stdin, refusals), `unset`'s fixed text,
  `show`'s secrets (D6). Check: the CLI tests.
- [ ] 2.2 `PUT`/`DELETE /api/projects/{id}/secrets/{name}`, `secrets` in `GET`, 422
  without the input; `make web-types` (D9). Check: `tests/test_server_projects.py`, `make
  web`.
- [ ] 2.3 `lado doctor`'s `Project secrets` check and the override line (D11). Check:
  `tests/test_doctor.py`.

## 3. End to end

- [ ] 3.1 `tests/integration/test_project_secrets.py`: each agent kind with its project's
  secret, two projects, the layers' order, no project, `unset`, a kit key through
  `mcp_exec`, delete and create. Check: `uv run pytest -m integration -n auto
  tests/integration/test_project_secrets.py`.
- [ ] 3.2 `tests/integration/test_project_secrets_canary.py` (D12). Check: `uv run pytest -m
  integration -n auto tests/integration/test_project_secrets_canary.py`.
- [ ] 3.3 The smoke probe sees a project's secret (D14). Check: CI's smoke cells.

## 4. Docs

- [ ] 4.1 `docs/cli.md`, `docs/design/projects.md`, `docs/design/agents.md` (D13),
  `docs/design/modules.md`, `docs/install.md`, the docstrings, CHANGELOG (D15). Check:
  `make lint`, `openspec validate project-secrets --strict`, `openspec validate --specs
  --strict`, the trial archive.
