# A New Session in a Project Implementation Plan

**Goal:** The New session window gets a fourth way, Project: choose a project and one of
its repositories and start a session there, exactly as `lado start --project <id> --repo
<name>` does; Folder's refusal inside a project leads there; the project's page opens the
window on its project.

**Architecture:** `POST /api/sessions` takes `where` of kind `project` and calls the CLI's
core function (`runtime.start_session` with `project` and `repo_name`). A read-only `GET
/api/project-launch` gives the window the projects, the choice of project and repository,
the default name and its state, the provider and the repository's last session, all
decided in `server/launch.py` next to the core. `GET /api/folders` names the project a
refused folder is in (`projects.place`, shared with the refusal's hint). The web gets
`LaunchProject.tsx` (the field) wired into `Launch.tsx`, and a link on the project's page.
The canary starts its session through the API.

**Tech Stack:** Python 3.10+, FastAPI/pydantic, React/TypeScript (Vite, vitest), pytest
(unit, integration with the fake agent, UI with Playwright's Chromium).

**Spec:** `openspec/changes/new-session-in-project/` (proposal AC-1..AC-12, `design.md`
D1-D15, the delta of `projects` and `session-clone`) and
`docs/superpowers/specs/2026-10-23-new-session-in-project-design.md` (the human's view and
the manual check). Mockup: the run's artifact `mockup-project-way.html` (version 2).

## Global Constraints

- Texts, verbatim (the spec's): `Project` (the switch), `Project` (the select's label),
  `Repository`, `<title> · <id>`, `folder not found`, `<N> repositories · <N> sessions
  running · folder <folder>` (as the Projects section counts: `1 repository`, `1 session`,
  `no sessions running`), `No repositories yet. Add one on the project's page:`, `Open
  <title>`, `No projects yet. A project keeps its repositories and the variables its sessions
  get.`, `Make one in Projects`, `Start in the project <title>`, `Open the project <title>`,
  `New session in this project…`, the page's line `Not built yet: the repositories on this
  page (adding, removing), renaming and deleting the project. Plan: Projects, step S7.
  Meanwhile: lado project show <id>, lado project repo add <id> <git-url>.`
- The core's refusals are shown as the server's `detail`, never re-worded.
- The window only chooses a repository: no clone, no fresh start from Project.
- The other three ways of `Launch.tsx` keep their code but the switch and Folder's
  refusal's button (the brief's threshold: a wider change is a stop and a question to the
  human).
- `mcp_server.py`, `hooks.py`, `providers/` and the schema do not change.
- UI tests wait for states, never times (LAD-127).

## Review Focus

- The start's kind `project` calls `runtime.start_session` with `project` and `repo_name`
  and no path, `resume=False`; no second start path (Tasks 2, 7).
- The `where` combinations: nothing starts on any refused one (Task 2).
- `project-launch` makes nothing and gives no secret or variable (Task 3).
- `Launch.tsx`: the Project wiring only; the other ways unchanged (Task 5).

## Task 1: The core: the session's name in a project and the place of a path (D4, D6)

**Files:** Modify `src/lado/runtime.py` (`project_session_name`), `src/lado/projects.py`
(`Place`, `place`; `refusal`/`_hint` use it). Test: `tests/test_projects_core.py`,
`tests/test_runtime_projects.py`.

- [ ] Tests: `project_session_name("shop", "Front.End") == "shop-front-end"`;
  `start_session` with a project still names `shop-frontend` by default; `place` of
  `<ws>/projects/shop/frontend/src` → `Place("shop", "frontend")`, of `<ws>/projects/shop`
  and of `<ws>/projects/shop/notes` (no git) → `Place("shop", None)`, of a foreign folder
  of `projects/`, of a path outside and with the human's own `projects/` → None, through a
  link the same as its target; every existing refusal and hint test passes unchanged.
- [ ] Implement; `make test PYTEST_ARGS="-n0 -k 'project'"`; commit `The core names a
  project's session and the project a path is in (LAD-137)`.

## Task 2: The server: a start in a project (D2, D3)

**Files:** Modify `src/lado/server/models.py` (`Where`), `src/lado/server/app.py`
(`start`). Test: `tests/test_server_project_launch.py` (new).

Requirements → tests: "The server starts a session in a project's repository" (a recorder
of `runtime.start_session` sees `path=None, project="shop", repo_name="frontend",
resume=False` and the name, kits, provider, mode, without, prompt, title given; a real
start with the fake provider answers `Started` with `session.project == "shop"`); "The
server refuses a start in a project as the core does" (unknown project 404, unknown
repository 404 with `project shop has no repository docs; its repositories: backend,
frontend`, a link 400 with the core's text, a taken name 409 `Taken`, `path` with kind
`project` 400, no `repo` 400, `project` with kind `folder` 400, `repo` with kind `scratch`
400, an unknown kind 400 as before; nothing started in each; without the token refused).

- [ ] Tests first; implement; commit `The server starts a session in a project's
  repository (LAD-137)`.

## Task 3: The server: what the Project way shows; the folder's project (D4, D5, D6, D9)

**Files:** Modify `src/lado/server/models.py` (`ProjectLaunch`, `ProjectPlace`,
`FolderInfo.project`), `src/lado/server/launch.py` (`project_launch`, `name_state`'s
`project`, `folder_info`), `src/lado/server/app.py` (`GET /api/project-launch`);
`web/openapi.json`, `web/src/api.gen.ts` by `make web-types`. Test:
`tests/test_server_project_launch.py`, `tests/test_server_launch.py` (the folder check).

Requirements → tests: "The server tells the New session window what a start in a project
takes" (the fields; `projects` sorted by title case aside; no `lado.db` → no projects and
none made; no secret or variable value in the body); "The Project way chooses the project
and repository last used" (the five scenarios: asked, last used, first found, a not-found
project skipped unless asked, empty project → `repo` null); "A name held outside the project
is taken elsewhere" (a session `shop-frontend` without a project → `taken_elsewhere`; this
project's stopped one → `stopped_here`); "The folder check names the project a folder is
in" (repository, project folder, foreign folder → null, outside → null).

- [ ] Tests first; implement; `make web-types`; commit `The server tells the New session
  window what a start in a project takes (LAD-137)`.

## Task 4: The web API and the Project field (D7, D9)

**Files:** Modify `web/src/api.ts` (`getProjectLaunch(project?, repo?)`, `startSession`'s
`where` type); create `web/src/LaunchProject.tsx`, `web/src/LaunchProject.test.tsx`;
`web/src/styles.css` (`.repo-pick`, D10's grid).

Requirements → tests: "The Project way only chooses a repository, from a list always shown"
(one repository listed and chosen; no add control); "The Project way sends the human to the
project when nothing can be chosen" (empty project line and link, no project line and link,
each link closes the window); the select: order, `folder not found` off.

- [ ] Tests first (`projectFakes.ts` extended); implement the field as in frames 1-3;
  `make web`; commit `The New session window's Project field (LAD-137)`.

## Task 5: Wiring Project into New session (D7, D8)

**Files:** Modify `web/src/Launch.tsx`, `web/src/Launch.test.tsx`.

Requirements → tests: "The New session window starts a session in a project" (Project last
in the switch; the request's body `where: {kind: "project", project: "shop", repo:
"frontend"}` with the name, kits, provider, mode; the window still opens in Folder, and in
Project with `{kind: "new", project}`); "The Project way takes the session's settings as
Folder does" (kits and mode from `last`, untouched fields only; the name note; a 409 shows
the core's text and `Resume it`); "Folder's refusal inside a project leads to the project"
(both buttons, the switch to Project with the place's project and repository, the
navigation); "The New session window clones from a URL" (the switch's four buttons).

- [ ] Tests first; implement; `make web`; commit `New session starts a session in a
  project (LAD-137)`.

## Task 6: The project's page (D11)

**Files:** Modify `web/src/Projects.tsx`, `web/src/Projects.test.tsx`.

Requirements → tests: "The project's page shows the project and what is not built yet"
(the new line; the link opens the window in Project with the project).

- [ ] Tests first; implement; commit `The project's page opens New session on its project
  (LAD-137)`.

## Task 7: The canary (D12)

**Files:** Modify `tests/integration/test_project_secrets_canary.py`.

Requirement → test: AC-11 (the start through `POST /api/sessions` of kind `project`, 200,
`session.project == "shop"`, the answer in `said`; every later check unchanged).

- [ ] Change; `uv run pytest -m integration -n0
  tests/integration/test_project_secrets_canary.py`; commit `The canary starts its session
  in the project through the server (LAD-137)`.

## Task 8: End to end in the browser (D13)

**Files:** Create `tests/ui/test_launch_project.py`.

Tests: Project → `Shop` → `frontend` → Start session, the session's page with `project Shop`
in the head (AC-6); the stopped session's repository chosen again and the taken name's
refusal text with `Resume it` (AC-8); Folder with `<ws>/projects/shop/backend` →
`Start in the project Shop` → Project with Shop and backend (AC-9); `/projects/shop` →
`New session in this project…` → Project with Shop (AC-10); an empty project's line and its
link (AC-7); 390 px: the switch's four buttons inside the window, two rows (AC-5).
Screenshots of frames 1, 2, 4, 6 and the phone for the build report.

- [ ] Write; `uv run pytest -m ui tests/ui/test_launch_project.py`; commit `UI tests of a
  new session in a project (LAD-137)`.

## Task 9: Docs (D14, D15)

**Files:** Modify `docs/design/ui.md` (Launch and session control: the fourth way, `where`
of kind `project`, `GET /api/project-launch`, the refusal's buttons; Projects: the page's
line), `docs/design/projects.md` (The session: the window only chooses; The UI: built in
S6b, "+ Add repository" on the page in S7; the step table's S6b row), `CHANGELOG.md`
(`## 0.43.0 (unreleased)`, Added).

- [ ] Write; `make lint`; `openspec validate new-session-in-project --strict`; commit
  `Docs: a new session in a project from the browser (LAD-137)`.

## Task 10: The regression run

- [ ] The settings' Checks: `make lint`, `make test`, `uv run pytest -m integration -n auto
  tests/integration/test_project_secrets_canary.py`, `uv run pytest -m ui
  tests/ui/test_launch_project.py tests/ui/test_launch.py tests/ui/test_projects_section.py`,
  `make web`, `openspec validate --specs --strict`, `openspec validate
  new-session-in-project --strict`; the trial archive in a scratch copy (`openspec archive
  new-session-in-project -y`, then `openspec validate --specs --strict`); CI's `ci-ok` on
  the pull request.
