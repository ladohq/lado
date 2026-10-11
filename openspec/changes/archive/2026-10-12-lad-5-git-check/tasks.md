## 1. Core: the folder check's kinds and hints

- [x] 1.1 `runtime.FolderProblem`, `Hint`, `git_version()`, `GIT_MIN`; `runtime.git`
  catches `OSError` (D1, D2, D4). Unit tests (`tests/test_runtime.py`): `git_version` with
  no git on PATH (`no_git`, PATH named), with a fake `git` script that exits 1 printing
  the xcrun line (`git_broken`), with a fake one printing `git version 2.30.2`.
- [x] 1.2 `check_repo` in the spec's order (D3): unit tests for each kind of "The folder
  check names what a folder lacks", with real git for `missing`, `not_folder`,
  `not_repo`, `no_commits`, and a fake `git` script on PATH for `no_git`, `git_broken` and
  `git_refused` (it passes `--version` and fails `rev-parse` with "detected dubious
  ownership"); the hints by kind and by `platform.system()` (D5).
- [x] 1.3 `gitcache._git` catches `OSError` (`GitError` with the `no_git` text);
  `gitpaths.rev_parse` returns None on `OSError` (D4). Unit tests: `gitcache` with no git
  on PATH; `gitpaths.git_root` with no git.
- [x] 1.4 CLI (D6): `lado start` on each hinted kind prints the two lines and exits 1;
  `lado kits add` with no git exits 1 with the text; no traceback (unit, `cli.main` with
  `capsys` and PATH set to an empty folder).

## 2. doctor and the system facts

- [x] 2.1 `doctor.check_git` after `tmux` (D9): unit tests for missing, not running, 2.30.2
  (`WARN`, exit status of the others), 2.47.1 and Apple's `2.39.5 (Apple Git-154)` (`OK`).
- [x] 2.2 `System.git`, `SystemInfo.git`, the report's `- git:` line (D7): unit tests of
  `system_info` and `report` (no path in either).

## 3. API

- [x] 3.1 `FolderInfo`: drop `has_commits`, add `problem_kind` and `hint` (D7); `make
  web-types`, commit `web/openapi.json` and `web/src/api.gen.ts`. Unit tests in
  `tests/test_server_launch.py`: each kind's `problem_kind` and `hint`; no git gives 200
  on `GET /api/folders` and 400 on `POST /api/sessions` (never 500).

## 4. Web UI

- [x] 4.1 `Launch.tsx` WhereField shows the hint (D8, mockup variant 2): vitest in
  `Launch.test.tsx`: a hinted kind shows the sentence, the command and Copy (copying
  calls the clipboard); `missing` and `git_refused` show no hint; Start stays off.
- [x] 4.2 `SystemPanel.tsx` shows the `git` row: vitest in `SystemPanel.test.tsx`.
- [x] 4.3 UI e2e (`tests/ui/`, marker `ui`): the New session window on a folder without
  commits shows the reason, the hint's command and Copy; screenshot of that screen as a
  run artifact.

## 5. Docs

- [x] 5.1 `docs/design/ui.md`: New session window (the kinds, the hint, Copy) and System
  panel (git row).
- [x] 5.2 `docs/install.md` Common problems: "git is not installed", "git does not run"
  (macOS stub), git older than 2.31.
- [x] 5.3 AGENTS.md Layout: `doctor.py` (the git check), `runtime.py` (`check_repo`'s
  kinds, `FolderProblem`, `git_version`); CHANGELOG.md: rename `## 0.35.1 (unreleased)`
  to `## 0.36.0 (unreleased)` and add the lines (D10).

## 6. Regression

- [x] 6.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui <changed files>`,
  `openspec validate --specs --strict`; CI runs the integration tests (no integration test
  is added: nothing here crosses processes beyond one git call).
