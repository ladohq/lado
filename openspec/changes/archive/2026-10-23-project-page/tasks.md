The plan with each task's tests: `docs/superpowers/plans/2026-10-23-project-page.md`.

## 1. Core and server

- [x] 1.1 The unpushed lines name commits on a detached HEAD and stashes; `unpushed` lists a
  project folder that is a repository and a worktree inside it once (F2, F3, D10). Check:
  `tests/test_project_repos.py`, `tests/test_projects_core.py`.
- [x] 1.2 Removing a repository names and forgets its sessions without a project; the CLI's
  ` (no project)`; `SessionToForget.project` (D9). Check: `tests/test_project_repos.py`,
  `tests/test_server_projects.py`.
- [x] 1.3 `PATCH /api/projects/{id}`, `RemoteInfo.repo_name`, `ProjectLaunch.gone`,
  `CloneTarget.project`, `ScratchTarget.project`; `make web-types` (D2, D4, D7, D12).
  Check: `tests/test_server_projects.py`, `tests/test_server_clones.py`,
  `tests/test_server_project_launch.py`, `tests/test_server_launch.py`, `make web`.

## 2. Web UI

- [x] 2.1 `useCloneJob` in `web/src/cloneJob.ts`, used by New session's Clone and start
  (D3). Check: `web/src/cloneJob.test.ts`; `web/src/Launch.test.tsx` and the clone tests of
  `tests/ui/test_launch.py` unchanged and green.
- [x] 2.2 `TitleEdit` made generic, in a commit of its own (D2). Check: `web/src/TitleEdit.test.tsx`,
  `tests/ui/test_session_head.py`.
- [x] 2.3 The page's head: Rename in place with Tab taking the id, `New session…`, the S7b line; `LaunchMode.repo`
  (D2, D6, D15). Check: `web/src/Projects.test.tsx`.
- [x] 2.4 `ProjectRepos.tsx`: Repositories, Sessions, Add repository (clone, scratch),
  Delete repository with the name typed for unpushed work (D5, D8, D11, D15). Check: `web/src/ProjectRepos.test.tsx`.
- [x] 2.5 E1's warning, `Open the project <title>` for Clone into and Create in, E2's note,
  M1's narrow window (D7, D12, D13, D14). Check: `web/src/LaunchProject.test.tsx`,
  `web/src/Launch.test.tsx`, `web/src/Projects.test.tsx`.

## 3. End to end

- [x] 3.1 `tests/ui/test_project_page.py` (AC-1..AC-15), the slow clone fixture moved to
  `tests/ui/conftest.py` (D16). Check: `uv run pytest -m ui tests/ui/test_project_page.py
  tests/ui/test_launch.py`.

## 4. Docs and the regression run

- [x] 4.1 `docs/design/ui.md`, `docs/design/projects.md`, `docs/cli.md`, CHANGELOG (D17).
  Check: `make lint`, `openspec validate project-page --strict`.
- [x] 4.2 The settings' Checks, the trial archive and `openspec validate --specs --strict`;
  CI's `ci-ok`.
