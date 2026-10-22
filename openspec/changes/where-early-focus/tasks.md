## 1. The window

- [x] 1.1 `web/src/Launch.tsx`, `WhereField`: an empty Where taking the focus opens its
  list whether the workspace is known yet or not (`onFocus` without the `made`
  condition); the list shows once the workspace and its subfolders are known, and only
  while the field has the focus (`onBlur` closes it as today). A comment names the early
  focus.
- [x] 1.2 `web/src/Launch.test.tsx` (unit: the lowest layer for the window's state),
  beside "an empty Where suggests the workspace's subfolders on focus": with
  `/api/repos-folder` held back, a focus before its answer lists `api/`, `app/`,
  `site/` after it (AC-1); a blur before the answer leaves no list after it (AC-2); a
  workspace not made and an early focus suggest nothing (AC-3). Each new test fails
  without 1.1. Run `make web`.

## 2. The UI test

- [x] 2.1 `tests/ui/test_launch.py` stays unchanged. By hand, with a throwaway UI test
  not committed, hold `GET /api/repos-folder` back 1.5 s in the browser (a fetch wrapper
  in an init script) and run the steps of
  `test_a_folder_in_a_project_is_refused_with_the_projects_command` up to the list: it
  fails before 1.1 and passes after (AC-4). Then 20 runs in a row of
  `uv run pytest -m ui tests/ui/test_launch.py -n auto` pass; report the counts in
  `build-report`.

## 3. Documents

- [x] 3.1 CHANGELOG.md, `### Fixed` under `## 0.43.0 (unreleased)`: in the New session
  window, clicking into Where before it learned the workspace now shows the workspace's
  folders as soon as it does.

## 4. Checks

- [ ] 4.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui
  tests/ui/test_launch.py` pass; `openspec validate where-early-focus --strict` passes;
  CI green on the pull request's last commit (AC-5).
