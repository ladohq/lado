The plan with each task's tests: `docs/superpowers/plans/2026-10-23-projects-section.md`.

## 1. Core and server

- [x] 1.1 `projects.overrides`, `project_secrets.unused`, `projects.check_new`,
  `projects.suggest_id`; `create` and `lado doctor` use them (D5). Check:
  `tests/test_projects_core.py`, `tests/test_project_variables_core.py`,
  `tests/test_project_secrets_store.py`, `tests/test_doctor.py`.
- [x] 1.2 `GET /api/projects`, `POST /api/projects`, `GET /api/project-id`, `ProjectInfo`'s
  `running`, `overrides`, `unused`; `make web-types` (D4). Check:
  `tests/test_server_projects.py`, `make web`.

## 2. Web UI

- [x] 2.1 The section's routes, the list, the empty state, the phone's turns, the page's
  head (D2, D3). Check: `web/src/Projects.test.tsx`, `web/src/App.test.tsx`.
- [x] 2.2 New project (D11). Check: `web/src/Projects.test.tsx`.
- [x] 2.3 Variables and secrets, the warning, the running line, the marks, the in-row
  removal (D6, D7, D9, D10). Check: `web/src/ProjectVariables.test.tsx`.
- [x] 2.4 The head's link to the project (D12). Check: `web/src/SessionDetails.test.tsx` and
  the head's tests.

## 3. End to end

- [x] 3.1 The canary over the new endpoints, E6–E9 (D13). Check: `uv run pytest -m
  integration -n0 tests/integration/test_project_secrets_canary.py`.
- [x] 3.2 `tests/ui/test_projects.py`: the section, New project, variables, the secret's
  way in the browser, the running line, the head's link, the phone (D14). Check: `make
  test-ui PYTEST_ARGS="-k projects"`.

## 4. Docs and the regression run

- [x] 4.1 `docs/design/ui.md`, `docs/design/projects.md` (with F3/E5 and S6a/S6b),
  CHANGELOG (D15). Check: `make lint`, `openspec validate projects-section --strict`.
- [ ] 4.2 `make check`; the trial archive and `openspec validate --specs --strict`.
