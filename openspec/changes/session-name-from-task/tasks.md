## 1. The core's default name

- [x] 1.1 `runtime.project_session_name` by design D8, with failing pytest first
  (`tests/test_runtime_projects.py`: `lado`/`lado` → `lado`, `lado`/`lado-site` → `lado-site`,
  `acme-web`/`web` → `acme-web`, `acme`/`api` → `acme-api`, `lado start --project lado --repo
  lado` starts `lado` and leaves a stopped `lado-lado`; `tests/test_server_project_launch.py`:
  `default_name: "lado"`) (AC-6). Check: `uv run pytest -n auto tests/test_runtime_projects.py
  tests/test_server_project_launch.py tests/test_projects_core.py tests/test_cli.py`.

## 2. The rule (web)

- [x] 2.1 `web/src/sessionName.ts` (`autoBase`, `freeName`, `slug`, `sessionName`) with
  `web/src/sessionName.test.ts` first: the examples of the design doc's rule and the spec's
  table (AC-2, AC-3, AC-4). Check: `npx vitest run src/sessionName.test.ts`.
- [x] 2.2 `web/src/sessionSlug.cases.json` read by vitest against `slug` and by
  `tests/test_session_slug_cases.py` against `runtime.slug` (D2). Check: both pass.

## 3. The window (web)

- [x] 3.1 Name on Task's label row by D3–D7 and D11, with failing vitest first in
  `web/src/Launch.test.tsx` (the list of plan Task 3); the existing tests of Team's Name and
  Session name follow (AC-1–AC-5, AC-9). Check: `make web`.
- [x] 3.2 Kits by D10 in `LaunchTeam.tsx` and `Launch.tsx`, with vitest first
  (`LaunchTeam.test.tsx`, `Launch.test.tsx`); one chevron on Change/Hide; the summary wraps at
  760 px or less (AC-8). Check: `make web`.
- [x] 3.3 Where on one line by D9 in `LaunchWhere.tsx` and `styles.css`, with vitest first
  (`LaunchWhere.test.tsx`, the badge's assertions in `Launch.test.tsx`) (AC-7). Check: `make web`.

## 4. In a browser (UI e2e)

- [x] 4.1 `tests/ui/test_launch.py`, `tests/ui/test_launch_project.py`,
  `tests/ui/launch_window.py`: existing texts follow; new tests of a task's key naming the
  session, a typed name with its title, the project `lado`/`lado`, the phone's label row (F8)
  and Where on one line at 390 px (AC-1, AC-2, AC-4, AC-6, AC-7, AC-9). Screenshots at 390, 768
  and 1440 px as run artifacts. Check: `uv run pytest -m ui tests/ui/test_launch.py
  tests/ui/test_launch_project.py`.

## 5. Documents and regression

- [x] 5.1 `docs/design/ui.md` (Launch and session control), `docs/cli.md` (`lado start
  --project`'s name), `docs/design/modules.md` (`sessionName.ts`); grep `docs/` for `Session
  name`, `Team setup`, `Add setup`, the badge `Project <title>` and `<project>-<repo>` and fix
  every hit.
- [x] 5.2 CHANGELOG.md: `## 0.45.1 (unreleased)` becomes `## 0.46.0 (unreleased)`; New: the
  name beside Task, from the task, kept as typed; Changed: a project's default session name
  no longer repeats the project (resume an older one by its name), Where on one line, Kits
  (AC-10).
- [x] 5.3 Regression: `make lint`, `make test`, `make web`, the UI run of 4.1, `openspec
  validate session-name-from-task --strict`, `openspec validate --specs --strict` and the trial
  archive of the settings' Checks.
