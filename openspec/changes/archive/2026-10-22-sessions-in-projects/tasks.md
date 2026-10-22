The plan with each task's tests: `docs/superpowers/plans/2026-10-22-sessions-in-projects.md`.

## 1. Core

- [x] 1.1 Schema 33: `sessions.project` referring to `projects(id)`, `Session.project`,
  `project_sessions`, `schema_before` (D1). Check: `tests/test_state.py` (migration from
  `previous_schema` with its backup, the foreign key).
- [x] 1.2 `projects.repositories` (D2). Check: `tests/test_projects_core.py` with real git
  (clone, init, hidden, link, plain folder, the project folder itself, detached HEAD).
- [x] 1.3 `projects.refusal`, kind `in_project` (D5). Check: `tests/test_projects_core.py`
  (repository, deeper, non-git, missing, project folder, foreign, `projects/`, link,
  the human's own `projects/`).
- [x] 1.4 `start_session(…, project, repo_name)` and the refusal at start (D4, D6). Check:
  `tests/test_runtime_projects.py` (a module of its own beside the long `test_runtime.py`).
- [x] 1.5 `start_approved_session` inherits the project (D7). Check:
  `tests/test_runtime_start_approved.py`.

## 2. Server and CLI

- [x] 2.1 `in_project` in `clone.check_target` and `scratch.check_target` with a hint; the
  server's folder check, Where hints, recent folders; `GET /api/projects/{id}`;
  `SessionInfo.project`, `SessionAbout.project`; `make web-types` (D6, D8, D11). Check:
  `tests/test_clone.py`, `test_scratch.py`, `test_server_launch.py`,
  `test_server_clones.py`, `test_server_session.py`, `make web`.
- [x] 2.2 `lado start --project/--repo`, `lado ls`, `lado project show`, `lado project
  delete` with sessions (D3, D9, D10). Check: `tests/test_cli.py`,
  `tests/test_projects_core.py`.

## 3. UI

- [x] 3.1 The head's project fact (variant A), the phone's details line, the `in_project`
  hint for a folder, a clone and a fresh start (D12). Check: vitest
  (`SessionDetails.test.tsx`, `Launch.test.tsx`, where the head's facts are tested),
  `make web`.

## 4. End to end

- [x] 4.1 `tests/integration/test_project_sessions.py`: start in a project, `lado ls`,
  `start_session` inherits, resume keeps, every refusal path, delete with a running and a
  stopped session, the upgrade of a session from before schema 33. Check: `uv run pytest
  -m integration -n auto <files>`.
- [x] 4.2 `tests/ui/test_session_head.py` (project in the head), `tests/ui/test_launch.py`
  (refusal box, Where hints), screenshots. Check: `uv run pytest -m ui <files>`.

## 5. Documents and version

- [x] 5.1 `docs/cli.md`, `docs/design/projects.md`, `docs/design/ui.md`,
  `docs/design/modules.md` (D13). Check: `uv run pytest tests/test_agents_md.py`.
- [x] 5.2 CHANGELOG: one line under `## 0.43.0 (unreleased)`.

## 6. Regression

- [x] 6.1 `make lint`; `make test` (counts); the changed integration and UI files with
  their markers; `make web`; `openspec validate sessions-in-projects --strict`;
  `openspec validate --specs --strict`; CI `ci-ok` green (container and smoke cells
  included).
