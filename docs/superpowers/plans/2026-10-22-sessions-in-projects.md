# Sessions in projects Implementation Plan

**Goal:** A session refers to its project in `lado.db`; `lado start --project <id> --repo
<name>` starts in a project's repository read from the disk; `start_session` and resumes
keep the project; no new session without a project starts inside LADO's `projects/` on any
path; the project shows in `lado ls`, the session's API and head; `lado project show`
lists repositories and `lado project delete` handles the project's sessions.

**Architecture:** `lado.projects` gains `repositories(id)`, `refusal(path)` and the
sessions' part of `delete`; `runtime.start_session` takes `project`/`repo` and asks
`projects.refusal` for a new session without one; `clone.check_target` and
`scratch.check_target` get the state `in_project` from the same function; the server's
folder check, Where hints and recent folders ask it too. `lado.db` gets
`sessions.project` (schema 33). The UI shows `SessionAbout.project` in the head.

**Tech Stack:** Python 3.10+ (standard library), SQLite, FastAPI/pydantic, React +
TypeScript (vitest), pytest (unit, integration with the fake agent, UI e2e in Chromium).

**Spec:** `openspec/changes/sessions-in-projects/` (proposal with AC-1..AC-9, `design.md`
D1-D13, delta specs `projects`, `repos-folder`, `session-clone`, `session-scratch`) and
`docs/superpowers/specs/2026-10-22-sessions-in-projects-design.md` (the human's view and
the manual check). Mockup: run artifact `task/lad-125/mockup-session-project.html`,
variant A.

## Global Constraints

- Python 3.10+, standard library only; no new dependency.
- Texts, verbatim (the spec's):
  - start: `Started session "<session>" in <folder> (project <id>)`;
    `unknown project "<id>"`; `project <id> has no repository <name>; its repositories:
    <names>`; `project <id> has no repositories yet: a repository is a git folder in
    <folder>`; `session "<s>" is in project <p>; a session's project never changes: give
    another name with --name` (and `is not in a project; …`);
  - usage (exit 2): `--project needs --repo NAME`; `--repo needs --project ID`;
    `--project takes no folder, git URL or --new: the folder is the project's repository`;
  - refusal: `<path> belongs to the project <title>: start a session in the project`,
    hints `Start a session in the project:` + `lado start --project <id> --repo <name>`,
    `See the project's repositories:` + `lado project show <id>`; `<path> is in
    <ws>/projects, which holds LADO's projects only: start a session in a project, or move
    the folder out of projects/`, hint `See the projects:` + `lado project list`;
  - ls: `  project <id>` after the folder, before the status;
  - show: `  repositories:`, `    <name>  <branch>  <remote>`, `(detached)`, `(no
    remote)`, `  repositories: none`;
  - delete: `project <id> has sessions not stopped: <names>; stop them first with lado
    stop <name>`; `Sessions to forget: <name> (<n> open run[s]), …`; `… with everything in
    it and forgets its <n> session[s]; run again with --yes`.
- Names in lists sorted, as S2 (`projects.names` cuts at three with `…`; the repositories
  of a refusal are listed whole).
- `mcp_server.py`, `hooks.py`, `providers/` do not change (the brief's threshold: if they
  must, stop and ask the human through the supervisor).
- Never the user's real home in tests: `HOME`, `LADO_HOME`, `LADO_REPOS` into `tmp_path`.
- Schema change: `SCHEMA_VERSION = 33`, `MIGRATIONS[32]`, `tests/agent_helpers.schema_before`.

## Review Focus

- A non-git folder inside a project: `lado start` says the project, not `git init`
  (Task 4).
- A link from outside into `projects/`: refused by real path (Task 3).
- `projects/` that is the human's own folder: nothing refused, `projects/` hinted (Tasks 3,
  6).
- A resume of a session from before schema 33 under `projects/`: not refused (Task 4).
- `start_session` from a session in a project whose repository was removed by hand:
  refused naming the repositories (Task 5).
- Delete: the foreign key keeps the record when a forget fails (Task 7).

---

### Task 1: Schema 33, `sessions.project`

**Files:** Modify `src/lado/state.py`, `tests/agent_helpers.py`. Test `tests/test_state.py`.

- [ ] Failing tests: a migration from `previous_schema()` backs up and gives schema 33
  with the column, existing sessions with `project` None (spec: A session refers to its
  project, "The upgrade"); `add_session` with `project="shop"` and `get_session` round
  trip; `resume_session` keeps the project; `project_sessions("shop")` lists only its
  sessions; deleting a project row that a session refers to raises
  `sqlite3.IntegrityError`.
- [ ] Implement D1: `SESSIONS_PROJECT`, `SCHEMA += …`, `MIGRATIONS[32]`,
  `SCHEMA_VERSION = 33`, `Session.project`, `add_session`, `_session`,
  `project_sessions`; `schema_before` undoes step 32 (assert the step, drop the column).
- [ ] Run `uv run pytest -n0 tests/test_state.py`; commit.

### Task 2: Repositories from the disk

**Files:** Modify `src/lado/projects.py`. Test `tests/test_projects_core.py` (real git).

- [ ] Failing tests (spec: A project's repositories are read from the disk; A project's
  repository shows its branch and remote from git): `frontend` cloned from a local bare
  repository with `origin` set to `https://token@github.com/shop/frontend` gives remote
  `https://github.com/shop/frontend`, branch `main`; `backend` (`git init`, commit, branch
  `dev`, no remote); not listed: `notes` (no git), `.web.clone-x1y2` (a repository,
  hidden), `docs` (link to a repository elsewhere), the project folder made a repository
  with a plain subfolder `plain`; a detached HEAD gives branch None; a missing folder gives
  `[]`; sorted by name.
- [ ] Implement D2 (`Repository`, `repositories`).
- [ ] Run `uv run pytest -n0 tests/test_projects_core.py`; commit.

### Task 3: The refusal

**Files:** Modify `src/lado/projects.py`, `src/lado/runtime.py` (`FolderProblemKind`).
Test `tests/test_projects_core.py`.

- [ ] Failing tests (spec: No new session without a project starts inside projects/; The
  refusal … names the project …; … for a folder of no project …): below a project's
  folder (repository, deeper path, non-git folder, missing path) → kind `in_project`, the
  text with the title (and the id without one), hint `lado start --project shop --repo
  frontend`; the project folder itself → hint `lado project show shop`; `projects/` and
  `projects/old` (no project) → the "holds LADO's projects only" text, `lado project
  list`; a link `~/code/front` → the same as its target; `projects/` the human's own (no
  project folder in it) → None; outside `projects/` → None; no `lado.db` → None.
- [ ] Implement D5 (`refusal`, `lado_owns_projects` or the inline condition).
- [ ] Run; commit.

### Task 4: `start_session` with a project, and the refusal at start

**Files:** Modify `src/lado/runtime.py`. Test `tests/test_runtime.py`.

- [ ] Failing tests (spec: lado start --project --repo starts…; … refuses what is no
  repository…; A session's project never changes; No new session without a project…):
  `start_session(None, None, …, project="shop", repo="frontend")` stores the project,
  names the session `shop-frontend`, path the repository's; unknown project; unknown
  repository with the list; no repositories yet; existing session of another project /
  none refused; same project resumed; a resume without `project` keeps `old.project`;
  a new session without a project in a project's repository refused with the refusal; a
  non-git folder there refused with the refusal (not `not_repo`); a stopped session from
  before schema 33 there (project None) resumes. Tmux and the provider faked as the
  existing `test_runtime.py` start tests do.
- [ ] Implement D4, D6 (start_session part).
- [ ] Run `uv run pytest -n0 tests/test_runtime.py -k "project or start"`; commit.

### Task 5: Inheritance through `start_session`

**Files:** Modify `src/lado/runtime.py` (`start_approved_session`). Test
`tests/test_runtime_start_approved.py`.

- [ ] Failing tests (spec: A session started from a session in a project is in the same
  project): from a session of project `shop` in `frontend`, the approved session has
  project `shop` and the same `repo`; from a session without a project, none; from a
  session without a project inside `projects/shop/frontend`, the refusal; from a session
  of `shop` whose `frontend` was removed, `project shop has no repository frontend; …`.
- [ ] Implement D7.
- [ ] Run; commit.

### Task 6: Clone and fresh-start targets, the server

**Files:** Modify `src/lado/clone.py`, `src/lado/scratch.py`, `src/lado/server/launch.py`,
`src/lado/server/clones.py`, `src/lado/server/models.py`, `src/lado/server/app.py`.
Tests `tests/test_clone.py`, `tests/test_scratch.py`, `tests/test_server_launch.py`,
`tests/test_server_clones.py`, `tests/test_server_session.py`.

- [ ] Failing tests (spec: Clones and fresh starts into projects/ …; The server's folder
  check …; The server gives a project…; The session's API…; repos-folder: The New
  session window starts Where…; session-clone and session-scratch `in_project`):
  `clone.check_target` and `scratch.check_target` give `in_project` with text and hint,
  checked before the other states; `scratch.make` makes nothing there; `GET
  /api/folders` for a project's repository: `ok: false`, `problem_kind: "in_project"`,
  hint, `scratch: false`, `subfolders: []`; for the workspace: no `projects` among the
  subfolders when it is LADO's, `projects` when it is the human's own; recent folders
  leave out a session's folder inside `projects/`; `GET /api/clone-target`,
  `GET /api/scratch-target` give `state: "in_project"` and `hint`; `POST /api/clones` 400,
  no job; `POST /api/sessions` folder and scratch 400 with the text; `GET
  /api/projects/shop` with its repositories, 404 for `nope`; `SessionInfo.project` and
  `SessionAbout.project{id, title}`.
- [ ] Implement D6 (targets, folder check), D8, D11; `make web-types`.
- [ ] Run the files with `-n0`; `make web` (stale-types check); commit with
  `web/openapi.json` and `web/src/api.gen.ts`.

### Task 7: The CLI: start, ls, project show and delete

**Files:** Modify `src/lado/cli.py`, `src/lado/projects.py` (`delete`). Test
`tests/test_cli.py`, `tests/test_projects_core.py`.

- [ ] Failing tests (spec: lado start --project and --repo go together…; lado ls prints a
  session's project; lado project show lists…; lado project list and show… (folder gone:
  `repositories: none`); lado project delete shows… (running session, stopped sessions);
  delete --yes … (sessions forgotten; folder failure keeps sessions; a failed forget
  keeps the record)): usage errors exit 2; `Started session … (project shop)`; the clone
  and `--new` refusals print the text and the hint line and exit 1 with nothing made;
  `lado ls` line; show's repository lines padded.
- [ ] Implement D3, D9, D10.
- [ ] Run; commit.

### Task 8: The UI: head, details, refusal hints

**Files:** Modify `web/src/Sessions.tsx`, `web/src/SessionDetails.tsx`,
`web/src/Launch.tsx`, `web/src/api.ts`, `web/src/styles.css` if a rule is needed. Test
`web/src/Layout.test.tsx` (head), `web/src/SessionDetails.test.tsx`,
`web/src/Launch.test.tsx`.

- [ ] Failing vitest tests (spec: The session's API and head show its project; The
  server's folder check …): the head's first fact `project Shop` with tooltip `Project
  shop`, the id without a title, nothing without a project; the phone's details line;
  Launch: a folder answer with `in_project` shows the text, the hint's sentence, command
  and Copy, Start off; a clone target and a scratch target `in_project` show their hint
  the same way.
- [ ] Implement D12 to the mockup's variant A.
- [ ] `make web`; commit.

### Task 9: Integration tests with the fake agent

**Files:** Create `tests/integration/test_project_sessions.py` (a basename no other test
module has).

- [ ] Tests, each a process path (AC-1, AC-4, AC-5, AC-8, AC-9):
  - `lado start --project shop --repo frontend --no-attach` (repository made by `git init`
    + commit in the project's folder): the session runs in the folder, `lado.db` has the
    project, `lado ls` prints `project shop`;
  - the fake supervisor's `start_session` after the human's approval (as
    `test_session_start.py` does): the new session has project `shop` and the same folder;
    `lado stop` + `lado start --project shop --repo frontend` resumes with the project;
  - every refusal path names the project and makes nothing: `lado start <repo folder>`,
    `lado start <file:// url> <ws>/projects/shop/web`, `lado start --new
    <ws>/projects/shop/site`, `start_session` from a session without a project whose
    folder is under `projects/` (its row written as before schema 33);
  - `lado project delete shop --yes` while the session runs: exit 1; after `lado stop`:
    the session is forgotten, the folder and the record gone;
  - an `lado.db` turned back with `previous_schema()` holding a session under
    `projects/shop/frontend`: the upgrade keeps it without a project and it resumes.
- [ ] Run `uv run pytest -m integration -n auto tests/integration/test_project_sessions.py
  tests/integration/test_projects_process.py tests/integration/test_server_launch_process.py`;
  commit.

### Task 10: UI e2e

**Files:** Modify `tests/ui/test_session_head.py`, `tests/ui/test_launch.py`.

- [ ] `test_session_head.py`: a session in project `shop` titled `Shop` (made through the
  CLI or the core in the fixture) shows `project Shop` first among the facts; screenshot.
- [ ] `test_launch.py`: Where typed with a folder under `projects/shop/frontend` shows the
  refusal box with `lado start --project shop --repo frontend` and Copy, Start disabled;
  Where on the workspace does not list `projects/`; screenshots.
- [ ] Run `uv run pytest -m ui tests/ui/test_session_head.py tests/ui/test_launch.py`;
  commit.

### Task 11: Documents and CHANGELOG

- [ ] `docs/cli.md`: `lado start --project/--repo` (name default, refusals, usage), the
  refusal inside `projects/`, `lado ls`'s project, `lado project show`'s repositories,
  `lado project delete` with sessions.
- [ ] `docs/design/projects.md`: "What is built" names S3; "How LADO knows a project's
  repositories" and "The session" built (the window's Project way still S6; adding
  repositories S4); "Deleting" with sessions built.
- [ ] `docs/design/ui.md`: Session head (the project fact, variant A, the phone's line),
  Where hints without `projects/`, the refusal box for a folder inside `projects/`.
- [ ] `docs/design/modules.md`: `projects.py` (repositories, refusal, delete with
  sessions), `state.py` (schema 33).
- [ ] CHANGELOG: one line under `## 0.43.0 (unreleased)`, Added: **Sessions in projects**.
- [ ] `uv run pytest tests/test_agents_md.py`; commit.

### Task 12: Regression run

- [ ] `make lint`; `make test` (report counts); the changed and added integration files
  with `-m integration`; the changed UI files with `-m ui`; `make web`;
  `openspec validate sessions-in-projects --strict`; `openspec validate --specs --strict`;
  CI `ci-ok` green with the container and smoke cells.
