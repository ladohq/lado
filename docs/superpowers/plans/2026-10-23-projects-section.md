# The Projects section Implementation Plan

**Goal:** The web UI's Projects section lists the projects, makes one, and shows a project's
page with its plain variables and secrets (set, edit or replace, remove), the outside names
it overrides, the secret files its agents do not get, the security warning and its running
sessions; a secret's value leaves the browser only in the body of its `PUT`.

**Architecture:** The server gets `GET /api/projects`, `POST /api/projects` and `GET
/api/project-id`, and `ProjectInfo` three fields, each derived by one core function that
`lado doctor` shares (`projects.overrides`, `project_secrets.unused`) or `create` shares
(`projects.check_new`, `projects.suggest_id`). The web gets `Projects.tsx` (list, page,
dialog) and `ProjectVariables.tsx` (the two blocks), reading REST anew on open, after a
change, on the sessions' feed and on focus. The S5b canary grows over the new endpoints and
closes E6–E9; a UI test proves the secret's way in the browser.

**Tech Stack:** Python 3.10+, FastAPI/pydantic, React/TypeScript (Vite, vitest), pytest
(unit, integration with the fake agent, UI with Playwright's Chromium).

**Spec:** `openspec/changes/projects-section/` (proposal AC-1..AC-14, `design.md` D1-D16,
the delta of `projects`) and `docs/superpowers/specs/2026-10-23-projects-section-design.md`
(the human's view and the manual check). Mockup: the run's artifact `mockup-projects.html`.

## Global Constraints

- Texts, verbatim (the spec's):
  - `<id> · <N> repositories · <N> running`, `1 repository`, `no sessions running`, `folder
    not found`, `No project <id>`, `No projects yet`, `New project…`, `New project`,
    `Create project`, `← All projects`, `Find a project`;
  - `Its folder: <folder>. The id never changes.`;
  - `⚠ Projects of one LADO are not isolated from each other: an agent of one project can
    read another's variables and secrets. For clients that must not mix, run a separate
    LADO.` (the dialog's: `⚠ Projects of one LADO are not isolated from each other. For
    clients that must not mix, run a separate LADO.`);
  - `New values reach the agents started after a change; running agents keep the
    environment they started with. Running now: <sessions> — restart a session to give it
    the change.` / `New values reach the agents started after a change. No session of this
    project is running.`;
  - `Repositories, sessions, renaming and deleting the project: not built yet. Plan:
    Projects, step S7. Meanwhile: lado project show <id>, lado project repo add <id>
    <git-url>.`;
  - `Variables`, `Secrets`, `+ Add variable`, `+ Add secret`, `Edit`, `Save`, `Replace`,
    `Remove`, `Cancel`, `Add`, `set · hidden`, `New value (the old one is not shown)`,
    `value (not shown after saving)`, `Remove <NAME>?`, `Add <NAME> as a secret instead`;
  - `overrides outside value`, tooltip `The outside folder (LADO_ENV_DIR) also gives <NAME>.
    This project's sessions get the project's value; its outside value is not shown.`;
  - `⚠ Agents do not get it: <reason>`, `⚠ <name>: agents do not get it: <reason>`, `⚠ The
    secrets folder is not used: <reason>`.
- The core's refusals are shown as the server's 400 `detail`, never re-worded.
- A secret's value: never in React state, a URL, a query, storage, the console or an error
  the UI keeps (D6). `mcp_server.py`, `hooks.py` and the providers do not change.
- UI tests wait for states, never for time.
- Tests never touch the user's home: `LADO_HOME`, `LADO_REPOS`, `HOME` in `tmp_path`.

## Review Focus

- Every route answering a project: no value of a secret or of the outside folder
  (`overrides`, `unused`) (Tasks 1, 2, 7).
- The secret field: uncontrolled, emptied on success, Cancel and unmount; no `<form>`
  submission; no value in any state or log (Tasks 5, 8).
- `create` after `check_new` is factored: every refusal of S2 kept, same texts (Task 1).

## Task 1: The core: overrides, unused, check_new, suggest_id (D5)

**Files:** Modify `src/lado/projects.py`, `src/lado/project_secrets.py`,
`src/lado/doctor.py`. Test: `tests/test_projects_core.py`,
`tests/test_project_variables_core.py`, `tests/test_project_secrets_store.py`,
`tests/test_doctor.py`.

- [ ] Tests: `overrides` with an outside folder giving `BOARD_URL` and `GH_TOKEN` and a
  project holding them as a variable and a secret → both names, sorted; none without the
  folder; `unused` names a 644 file and a link with the reasons of `read` and returns no
  value (assert the value's text is in no item); `check_new` raises each of `create`'s
  refusals with the same text and makes nothing; `suggest_id("Магазин EU") ==
  "magazin-eu"`, `"ACME_crm"` → `acme-crm`, a 60-character title cut to 40 with no trailing
  `-`, `"日本"` → None with the fresh start's text; the doctor's lines unchanged.
- [ ] Implement; `create` calls `check_new`; the doctor's two checks use the new functions.
- [ ] `make test PYTEST_ARGS="-n0 -k 'project or doctor'"`; commit `The core says which
  names a project overrides and suggests a project's id (LAD-134)`.

## Task 2: The server: list, create, id, the project's new fields (D4)

**Files:** Modify `src/lado/server/app.py`, `src/lado/server/models.py`,
`src/lado/server/launch.py`; `web/openapi.json`, `web/src/api.gen.ts` by `make web-types`.
Test: `tests/test_server_projects.py`.

Requirements → tests: "The server lists the projects" (two projects, a folder not found,
no `lado.db` → `[]` and none made); "The server makes a project" (made, each refusal 400
with the core's text, without the token refused, `lado.db` made when missing); "The server
suggests a project's id from a title" (Cyrillic, taken, typed invalid id, no Latin letter,
nothing made); "The server gives a project with its repositories" (the four scenarios; the
outside value and the secret's value absent from the body).

- [ ] Tests first; implement; `make web-types`; commit `The server lists and makes
  projects and says what overrides the outside folder (LAD-134)`.

## Task 3: The web API and the section's routes (D2)

**Files:** Modify `web/src/api.ts` (`listProjects`, `getProject`, `createProject`,
`suggestProjectId`, `putVariable`, `deleteVariable`, `putSecret`, `deleteSecret`),
`web/src/App.tsx`, `web/src/pages.tsx` (placeholder gone), `web/src/paths.ts`
(`PLANS.projects` → the S7 plan). Create `web/src/Projects.tsx`. Test:
`web/src/Projects.test.tsx`, `web/src/App.test.tsx`.

Requirements → tests (vitest): "The Projects section lists the projects" (rows' texts,
search, unknown id), "The Projects section has an empty state", "The Projects section takes
the phone's screen in turns" (the phone layout's state), "The project list follows the
sessions" (a feed change refetches).

- [ ] Tests; implement the list and the page's head with the not-built line; commit `The
  Projects section lists the projects (LAD-134)`.

## Task 4: New project (D11)

**Files:** `web/src/Projects.tsx`, `web/src/styles.css`. Test: `web/src/Projects.test.tsx`.

Requirements → tests: "The UI makes a project", "New project's id follows the title until
edited" (follows, an edited id stays, a refusal disables Create, made opens the page).

- [ ] Tests; implement; commit `New project makes a project from the UI (LAD-134)`.

## Task 5: Variables and secrets (D6, D7, D9)

**Files:** Create `web/src/ProjectVariables.tsx`; `web/src/styles.css`. Test:
`web/src/ProjectVariables.test.tsx`.

Requirements → tests: "The UI sets, edits and removes a project's plain variables", "A
name that looks like a secret is offered as a secret" (the button moves the name, the value
field empty, `sk_test_1` in no input), "The UI sets, replaces and removes a project's
secrets without showing them", "A secret's value is typed into a hidden field emptied after
use" (`type=password`, `autocomplete=off`, empty after success, Cancel, unmount; kept after
a refusal; the value absent from the rendered HTML but the open field), "The project's page
marks a name that overrides the outside folder", "The project's page names a secret file
its agents do not get" (row, orphan line, folder line), "Removing a variable or a secret
asks in its row" (no request before the second Remove), "The project's page warns…",
"The project's page says which agents get new values" (links by title, follows a stop).

- [ ] Tests; implement; commit `A project's page sets its variables and secrets (LAD-134)`.

## Task 6: The head's link (D12)

**Files:** `web/src/Sessions.tsx`, `web/src/SessionDetails.tsx`. Test:
`web/src/SessionDetails.test.tsx`, the head's tests.

Requirement → test: "The session's API and head show its project" (the link's href, the
tooltip kept, the phone's details).

- [ ] Tests; implement; commit `The session head links to its project (LAD-134)`.

## Task 7: The canary (D13)

**Files:** `tests/integration/test_project_secrets_canary.py`.

Requirement → test: "A secret's value leaves the browser only in the body of its request"
(server side), AC-13.

- [ ] The new endpoints in `said`; an outside folder giving `CLI_NAME` with a second
  unique value and a loose hand-made file, both absent from every text; E6 (`ps` after each
  agent kind starts), E7 (`show-environment -t` per session), E8 (`files_holding` reads file
  links and raises on a read error but a socket or a vanished file), E9 (no secret's name in
  `lado bug-report` nor `GET /api/bug-report`).
- [ ] `uv run pytest -m integration -n0 tests/integration/test_project_secrets_canary.py`;
  commit `The canary covers the Projects API and reads every process and session (LAD-134)`.

## Task 8: End to end in the browser (D14)

**Files:** Create `tests/ui/test_projects.py`.

Requirements → tests: "A secret's value leaves the browser only in the body of its request"
(browser side), "The UI makes a project", "The UI sets, replaces and removes…", "The
project's page says which agents get new values" (a fake-agent session starts: the line
names it without a reload), "The session's API and head show its project" (the link), the
phone's turns at 390 px.

- [ ] Tests; `make test-ui PYTEST_ARGS="-k projects"`; commit `UI tests of the Projects
  section and the secret's way in the browser (LAD-134)`.

## Task 9: Docs (D15)

**Files:** `docs/design/ui.md`, `docs/design/projects.md`, `CHANGELOG.md`; the docstrings
of the new functions.

- [ ] Write; `openspec validate projects-section --strict`; commit `Docs of the Projects
  section (LAD-134)`.

## Task 10: The regression run

- [ ] `make check` (lint, the plugin, the web UI, unit, integration and UI tests); the
  trial archive `openspec archive projects-section --yes` in a scratch copy and
  `openspec validate --specs --strict`.
