The plan with each task's tests: `docs/superpowers/plans/2026-10-23-project-delete.md`.

## 1. Core and server

- [x] 1.1 `projects.deletion` and `delete` acting on it: the sessions without a project
  in a real folder, a link folder announced and matched as a link, a missing folder's
  text, an unreadable folder's line; the CLI prints the preview (D1–D5). Check:
  `tests/test_projects_core.py`, `tests/test_cli.py`.
- [x] 1.2 F2: a project folder that is a repository does not count its repositories;
  S5a's F5: a set racing a delete is an unknown project (D6, D7). Check:
  `tests/test_project_repos.py`, `tests/test_projects_core.py`,
  `tests/test_project_variables_core.py`.
- [x] 1.3 `GET /api/projects/{id}/deletion`, `DELETE /api/projects/{id}`,
  `ProjectDeletion`; `make web-types` (D8). Check: `tests/test_server_projects.py`,
  `make web`.

## 2. Web UI

- [x] 2.1 `ProjectDelete.tsx`: the block and the dialog, the id always typed, the list
  after the delete (D9, D11). Check: `web/src/ProjectDelete.test.tsx`,
  `web/src/Projects.test.tsx`.
- [x] 2.2 F1: `useCloneJob` cancels a running job on unmount (D10). Check:
  `web/src/cloneJob.test.ts`, `web/src/ProjectRepos.test.tsx`; `web/src/Launch.test.tsx`
  unchanged and green.

## 3. End to end

- [ ] 3.1 `tests/ui/test_project_page.py` (AC-2..AC-4, AC-9) and the canary over the
  delete (AC-12) (D12). Check: `uv run pytest -m ui tests/ui/test_project_page.py
  tests/ui/test_launch.py`; `uv run pytest -m integration -n0
  tests/integration/test_project_secrets_canary.py`.

## 4. Docs and the regression run

- [ ] 4.1 `docs/design/ui.md`, `docs/design/projects.md`, `docs/cli.md`, CHANGELOG (D13).
  Check: `make lint`, `openspec validate project-delete --strict`.
- [ ] 4.2 The settings' Checks, the trial archive and `openspec validate --specs --strict`;
  CI's `ci-ok`.
