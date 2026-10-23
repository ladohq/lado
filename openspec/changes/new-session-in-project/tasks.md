The plan with each task's tests: `docs/superpowers/plans/2026-10-23-new-session-in-project.md`.

## 1. Core and server

- [ ] 1.1 `runtime.project_session_name`, `projects.place` (the refusal's hint uses it)
  (D4, D6). Check: `tests/test_projects_core.py`, `tests/test_runtime_projects.py`.
- [ ] 1.2 `POST /api/sessions` with `where` of kind `project`: the CLI's core call, the
  refusals and the combinations (D2, D3). Check: `tests/test_server_project_launch.py`.
- [ ] 1.3 `GET /api/project-launch`, `name_state`'s project, `FolderInfo.project`; `make
  web-types` (D4, D5, D6, D9). Check: `tests/test_server_project_launch.py`,
  `tests/test_server_launch.py`, `make web`.

## 2. Web UI

- [ ] 2.1 `getProjectLaunch`, the Project field `LaunchProject.tsx`, `.repo-pick`, the
  phone's grid (D7, D9, D10). Check: `web/src/LaunchProject.test.tsx`.
- [ ] 2.2 Project wired into New session: the switch, the start, the defaults from the last
  session, Folder's refusal's buttons, `LaunchMode`'s project (D7, D8). Check:
  `web/src/Launch.test.tsx`.
- [ ] 2.3 The project's page: `New session in this project…` and the new line (D11).
  Check: `web/src/Projects.test.tsx`.

## 3. End to end

- [ ] 3.1 The canary starts its session through `POST /api/sessions` (D12). Check: `uv run
  pytest -m integration -n0 tests/integration/test_project_secrets_canary.py`.
- [ ] 3.2 `tests/ui/test_launch_project.py`: the start, the taken name, Folder's refusal,
  the page's link, the empty project, 390 px (D13). Check: `uv run pytest -m ui
  tests/ui/test_launch_project.py`.

## 4. Docs and the regression run

- [ ] 4.1 `docs/design/ui.md`, `docs/design/projects.md`, CHANGELOG (D14). Check: `make
  lint`, `openspec validate new-session-in-project --strict`.
- [ ] 4.2 The settings' Checks, the trial archive and `openspec validate --specs --strict`;
  CI's `ci-ok`.
