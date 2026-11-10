# The session's name from the task, beside Task: Implementation Plan

**Goal:** New session shows the session's name as a field **Name** on Task's label row, made
from the task until the human types; a typed name is kept as the title; a project's place is
named without repeats; Where is one line; Team says Kits.

**Architecture:** The rule is a pure browser module, `web/src/sessionName.ts` (design D1), fed
by the task, the place's `default_name` and the live store's sessions (D3); `Launch.tsx` holds
`nameMode`/`typed` (D4) and renders Name in Task's label row with its notes (D6);
`LaunchTeam.tsx` loses the name and says Kits (D10); `LaunchWhere.tsx` drops the badge for a
one-line secondary (D9). The core changes only `runtime.project_session_name` (D8). No API
model change.

**Tech Stack:** Python 3.10+, React + TypeScript, CSS, vitest, pytest, Playwright.

**Spec:** `openspec/changes/session-name-from-task/` (proposal, design.md D1–D13, delta specs
of new-session-window, projects, session-scratch, session-model, repos-folder),
`docs/superpowers/specs/2026-11-10-session-name-from-task-design.md` (words, exactly), session
artifacts `ui-design/new-session-dialog-2/spec` and `mockup.html`, run artifact
`mockup-task-name-phone.html` (option B).

## Global Constraints

- Colours and sizes by tokens of `web/src/tokens.css` only; no new token. UI texts word for
  word from the design doc. `Limits.max_title` from `GET /api/limits`, never a literal 80.
- No schema migration, no API model change: `make web` must pass its stale-types check with
  `web/openapi.json` and `web/src/api.gen.ts` untouched.
- CHANGELOG.md: rename `## 0.45.1 (unreleased)` to `## 0.46.0 (unreleased)` (a feature, D13);
  items under New (the name beside Task, from the task) and Changed (a project's default name;
  Where one line and Kits), by docs/release.md's rules.
- Docs: `docs/design/ui.md` Launch and session control (Where, Task and Name, Team, "The name
  beside a stopped session", the footer's items, Resume's summary), `docs/cli.md` (`lado start
  --project` without `--name`), `docs/design/modules.md` for `sessionName.ts`.
- Edit with edit tools; no sub-agents. UI tests with `-m ui`; suites with `-n auto`.

## Review Focus

- The browser's `slug` against `runtime.slug` (the shared cases, D2).
- Auto → custom → cleared → auto: the value stays empty while focused, the placeholder shows
  the automatic id, blur puts it back; a partial edit of the automatic name is custom.
- A typed name re-checked on a change of the place or the sessions, never replaced.
- The 409 race: the note under Task, the focus on Name, Team left closed.

## Task 1: The core's default name

**Files:** `src/lado/runtime.py` (`project_session_name`), `tests/test_runtime_projects.py`,
`tests/test_server_project_launch.py`.

- [ ] Failing tests first (pytest, unit): `project_session_name` for `lado`/`lado` → `lado`,
  `lado`/`lado-site` → `lado-site`, `acme-web`/`web` → `acme-web`, `acme`/`api` → `acme-api`,
  and the existing `shop`/`Front.End` → `shop-front-end`; `GET /api/project-launch?project=lado
  &repo=lado` answers `default_name: "lado"`; `lado start --project lado --repo lado` starts
  `lado` and leaves a stopped `lado-lado` stopped (projects: "A project's default session name
  does not repeat the project", "lado start --project --repo starts…", "The server tells the
  New session window…").
- [ ] Implement by D8; the longest-name test (`test_the_longest_project_and_repository_…`)
  still passes.
- [ ] Run: `uv run pytest -n auto tests/test_runtime_projects.py
  tests/test_server_project_launch.py tests/test_projects_core.py tests/test_cli.py`.

## Task 2: The rule, pure

**Files:** create `web/src/sessionName.ts`, `web/src/sessionName.test.ts`,
`web/src/sessionSlug.cases.json`; `tests/test_session_slug_cases.py`.

- [ ] Failing vitest of `autoBase`, `freeName`, `slug`, `sessionName` with the spec's examples
  table (key at the start, `[KEY]`, key later not taken, `HTTP-2 support`, filler, three words,
  a first word over 32 cut to 32, under 3 characters → the place, non-Latin → the place, no task
  and no place → none; custom `Review Kao` → id `review-kao`, title `Review Kao`; `lad-263-docs`
  → id only; `Вход после сессии` → the automatic id with that title; numbering against taken)
  (new-session-window: "LADO names the session…", "A typed name is kept…").
- [ ] Shared slug cases (D2): vitest reads `sessionSlug.cases.json` against `slug`; a pytest
  reads the same file against `runtime.slug` (an empty expected slug meaning the core's `lado`).
- [ ] Implement; `npx vitest run src/sessionName.test.ts` and the pytest pass.

## Task 3: Name on Task's label row

**Files:** `web/src/Launch.tsx`, `web/src/LaunchTeam.tsx` (name props out), `web/src/styles.css`,
`web/src/Launch.test.tsx`.

- [ ] Failing vitest in `Launch.test.tsx`: Name beside Task and not in Team (folder, project,
  clone), none for New empty folder (Folder name notes `Also the session’s name.`) and Resume;
  the task's key 300 ms after typing (fake timers) and at once on Task's blur; a change of
  place recomputes with and without a task; numbered with its note; typed kept across task and
  place changes and re-checked; cleared → placeholder, value on blur; partial edit of the
  automatic name is custom; the start posts `name` and `title`; taken typed name → note, `Use
  <next>`, no Resume, footer `choose another name`; 81 characters → `shorten the name`; clone
  without URL and task → `name the session`; a 409 → the note under Task, focus on Name, Team
  closed; the draft keeps a typed name; Start beside a stopped session reads `Start new session
  <id>` (new-session-window: "Name stands on Task's label row", "A name taken elsewhere…",
  "The footer says what is missing", "The start button keeps the focus…", "A stopped session
  of the place…", "The Resume window…"; projects: "The Project way takes the session's
  settings…"; session-scratch: "From scratch shows…").
- [ ] Implement by D3–D7, D11 (`.task-head`, `.name-inline`, the phone rule of F8 option B);
  `TeamRefs.name` moves to the new input.
- [ ] Update the existing tests that read Team's Name or Session name (about 21 places in
  `Launch.test.tsx`).

## Task 4: Team says Kits

**Files:** `web/src/LaunchTeam.tsx`, `web/src/LaunchTeam.test.tsx`, `web/src/Launch.tsx`,
`web/src/styles.css` (one chevron on Change/Hide, the summary wrapping at 760 px or less).

- [ ] Failing vitest: summary `Kits default`, no Name; opened **Kits** with its info text
  always, `+ Add kit` (`aria-label="Add kit"`); footer `choose a kit`; Team's info `Kits and
  permissions are LADO's defaults.` (new-session-window: "Team is a summary…"; session-model:
  "The launch window's Model field" scenario "The window says agent CLI").
- [ ] Implement by D10; the file's header comment follows.

## Task 5: Where on one line

**Files:** `web/src/LaunchWhere.tsx`, `web/src/LaunchWhere.test.tsx`, `web/src/Launch.test.tsx`
(the badge's assertions), `web/src/styles.css`.

- [ ] Failing vitest: a project's box and Recent row read `<repo>` and `in project <title>` in
  `.place-sub`, no `.place-badge`; the box's `title` is `<name> — <secondary>`; a folder's
  Where info carries its full path (new-session-window: "Where shows a place on one line",
  "Where lists the recent places…"; projects: "The New session window starts a session in a
  project", "Folder's refusal inside a project…"; repos-folder: "Where hints and recent
  folders…").
- [ ] Implement by D9 (the shrink rule, `Badge` removed).

## Task 6: In a browser (UI e2e)

**Files:** `tests/ui/test_launch.py`, `tests/ui/test_launch_project.py`,
`tests/ui/launch_window.py`.

- [ ] Update the existing tests that read Team's Name, `Setup` or the badge.
- [ ] New: a task `LAD-7: fix the thing` in a folder starts `lad-7` and its page opens under
  it; a typed `Review Kao` starts `review-kao` whose head shows the title `Review Kao`; in a
  project `lado`/`lado` the window offers `lado`.
- [ ] At 390 px: the gap between `Task ⓘ` and `Name` is wider than inside a label (F8), and
  Where's box is one line with `in project …` visible; screenshots of the window at 390, 768
  and 1440 px (Task's label row, a numbered name, a typed name, Team open with Kits) as run
  artifacts.
- [ ] Run: `uv run pytest -m ui tests/ui/test_launch.py tests/ui/test_launch_project.py`.

## Task 7: Documents and regression

- [ ] `docs/design/ui.md`, `docs/cli.md`, `docs/design/modules.md` as the constraints say;
  grep `docs/` for `Session name`, `Team setup`, `Add setup`, `Project <title>` badge and
  `<project>-<repo>` and fix every hit.
- [ ] CHANGELOG.md as the constraints say.
- [ ] Regression: `make lint`, `make test`, `make web`, the UI run of Task 6, `openspec
  validate session-name-from-task --strict`, `openspec validate --specs --strict` and the trial
  archive of the settings' Checks.
