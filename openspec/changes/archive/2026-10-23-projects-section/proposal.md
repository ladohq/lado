Task: LAD-134

## Why

Step S6 of the epic LAD-116 (`docs/epics/lad-116/plan.md`; the model is
`docs/design/projects.md` and the concept `projects-concept`, sections "The UI", "Environment
variables and secrets" and "The security boundary"). Steps S2–S5b built projects, their
repositories, plain variables and secrets in the core, the CLI and the server, but the web
UI still shows a placeholder for Projects: a human who runs LADO from the browser (or in
LADO's image, with no terminal at hand) cannot make a project or give it the keys its
sessions need.

The root cause: the server has no way to list or make a project, and `GET
/api/projects/{id}` lacks what a screen of variables must show besides the values (the
outside names a project overrides, the secret files its agents do not get, its running
sessions), which only `lado doctor` and the CLI's output say today.

The human split step S6 (question #1151): this change is **S6a**, the Projects section with
the project's variables and secrets; the Project way of the New session window (start in a
project's repository, "+ new repository", the Folder refusal leading into it) is **S6b**, a
task of its own.

## What Changes

- **Server API** (in OpenAPI, `make web-types`):
  - `GET /api/projects`: every project by id with its title, folder, whether the folder is
    there, its number of repositories read from the disk and its running sessions.
  - `GET /api/project-id?title=…` (or `?id=…`): the id a title gives (the fresh start's
    transliteration, cut to the id's rule), its folder and the core's refusal of that id,
    if any; it makes nothing.
  - `POST /api/projects` with `{id, title}` and the token for changes (`guard.changes`):
    makes the project as `lado project create` does; a refusal is 400 with the core's text.
  - `GET /api/projects/{id}` (and the answers of the routes that change a project) gains
    `running` (its sessions that run, by name), `overrides` (the names of its variables and
    secrets that the outside folder `LADO_ENV_DIR` gives too, never a value) and `unused`
    (the files of its secrets folder its agents do not get, by name with why, as `lado
    doctor` says it).
- **The Projects section** replaces the placeholder (`/projects`): the list of projects at
  the left as Sessions has it (title, or the id without one; the id; the repositories; the
  running sessions; `folder not found`), a search, a "+" that opens **New project**, and
  the project at the right at `/projects/<id>`. On a phone the list fills the screen and a
  project opens in its place with `← All projects`. With no project: what a project is and
  one button **New project…**.
- **New project**: a dialog with Title (optional) and Id; the id follows the title until the
  human edits it; the core's refusal shows under Id before Create; the security boundary's
  short warning. Create opens the new project.
- **The project's page** (minimal; the rest is S7): the title, the id, `N repositories · N
  sessions running · folder <path>`, and one line naming what is not built yet with the
  CLI meanwhile. Above the variables, always: the security boundary's warning and the line
  "New values reach the agents started after a change…" with the running sessions as links.
- **Variables**: a block of plain variables (name, value; Edit in place, Remove, "+ Add
  variable") and a block of secrets (name, `set · hidden`; Replace, Remove, "+ Add
  secret"). A secret's value is typed into a hidden field that is empty after saving and is
  never read back. The core's refusals show verbatim under the row; a name that looks like a
  secret offers "Add NAME as a secret instead", which moves the name only. A name that
  overrides the outside folder's carries the mark `overrides outside value` (no outside
  value shown); a secret file the agents do not get shows `Agents do not get it: <reason>`.
  Remove asks in the row.
- **The session's head**: `project Shop` becomes a link to `/projects/shop` (the phone's
  details line too).
- **The canary** (`tests/integration/test_project_secrets_canary.py`) covers the new
  endpoints and the feed, and closes the gaps E6–E9 of S5b's review: `ps` read more than
  once, the tmux sessions' environment besides the global one, the file search following
  links and failing on a read error, and no secret's *name* in the bug report. A UI test
  sets and replaces a secret in the browser and finds its value nowhere in the page's
  storage, URL or the server's log.
- **Docs**: `docs/design/ui.md` (the Projects section, the head's link),
  `docs/design/projects.md` (what is built; F3/E5: a secret is read through links above
  `secrets/`, written and removed never through one; the S6a/S6b split),
  CHANGELOG under `## 0.43.0 (unreleased)`.

## Acceptance criteria

- AC-1. `GET /api/projects` lists every project by id with `{id, title, folder, found,
  repos, running}`, `repos` the number of repositories on disk; an empty list without
  `lado.db`, which it does not make.
- AC-2. `POST /api/projects` with the change token makes the project and its folder as
  `lado project create` does and answers the project; each refusal of the core (bad id,
  taken id, existing folder, left data folder, the human's own `projects/`, a bad title) is
  400 with the core's text and makes nothing; without the token it is refused.
- AC-3. `GET /api/project-id?title=Магазин EU` answers `id: "magazin-eu"` with its folder
  and `problem: null`; for a taken or invalid id (`?id=`) `problem` is the core's refusal; a
  title with no Latin letter or digit gives `id: null`; nothing is made.
- AC-4. `GET /api/projects/{id}` carries `running`, `overrides` and `unused`; `overrides`
  and `unused` hold names and reasons only, never a value of the project or of the outside
  folder.
- AC-5. The Projects section lists the projects as AC-1 gives them (title or id, id,
  repositories, running sessions, `folder not found`), filters them by the search, and
  opens one at `/projects/<id>`; an unknown id shows "No project <id>"; with none it shows
  the empty state; on a phone the list and the project take the screen in turn.
- AC-6. New project derives the id from the title until the human edits the id, shows the
  core's refusal under Id and disables Create while it holds, and opens the new project
  after Create.
- AC-7. The project's page shows its head, the S7 line, the security warning and the line
  of new values with the running sessions as links (or "No session of this project is
  running"), updated when a session of the project starts or stops.
- AC-8. A plain variable is added, edited in place and removed (after the in-row
  confirmation); each refusal of the core shows verbatim; "Add NAME as a secret instead"
  opens the secret's form with the name and an empty value.
- AC-9. A secret is added, replaced and removed; the value field is a hidden field that is
  empty after a save, Cancel or leaving the page; no screen shows a value of a secret; a
  name held by the other kind, a reserved name, an invalid name and an empty value show the
  core's refusal.
- AC-10. A secret's value travels only in the body of one `PUT
  /api/projects/{id}/secrets/{name}`: never in a URL, the server's log, `localStorage`,
  `sessionStorage` or the form history; the UI test and the canary prove it.
- AC-11. A name the outside folder gives too has the mark `overrides outside value` with
  its tooltip; a secret file the agents do not get shows `Agents do not get it: <reason>`
  (a file with no usable name, and the folder itself, as a line under the block).
- AC-12. The session's head links `project <title>` to `/projects/<id>`, on a phone too.
- AC-13. The canary passes with E6–E9 closed and the new endpoints and the feed in it.
- AC-14. `docs/design/ui.md`, `docs/design/projects.md`, the living spec and CHANGELOG say
  what is built; `make check` passes.

## Out of scope

- The Project way of New session, a start in a project from the UI (`POST /api/sessions`
  with a project), "+ new repository" by clone or from scratch, the Folder refusal leading
  into Project: **S6b**, a new task (the human's split, #1151). Until then the UI says
  `lado start --project <id> --repo <name>` as today.
- The project's page beyond the head and the variables: its repositories, sessions,
  "+ Add repository", renaming and deleting the project: step S7. Adding a repository from
  the UI comes in S6b (with a start) and S7 (on the page); meanwhile the CLI (#1158).
- A feed of projects: `projects` is not journaled and secrets are files; the page reads
  REST (D3 of `design.md`).
- Global variables, outside secrets per project, isolation of projects, sessions over
  several repositories: "Not now" of the concept.
- The findings of S2, G1 of S3, X3 of S4 and F5 of S5a: step S7.

## Impact

- Code: `server/app.py` (three routes), `server/models.py` (`ProjectSummary`, `ProjectId`,
  `ProjectNew`, `ProjectInfo`'s new fields, `UnusedSecret`), `server/launch.py`,
  `projects.py` (`overrides`, `suggest_id`, `check_new`), `project_secrets.py` (`unused`),
  `doctor.py` (its override line from `projects.overrides`); `web/src/Projects.tsx` (new),
  `web/src/api.ts`, `web/src/App.tsx`, `web/src/pages.tsx`, `web/src/Sessions.tsx`,
  `web/src/SessionDetails.tsx`, `web/src/styles.css`, `web/openapi.json`,
  `web/src/api.gen.ts`; tests (unit, vitest, UI e2e, the integration canary).
- No change of `mcp_server.py`, `hooks.py`, a provider's files or the agents' protocol; no
  schema migration.
- Version: the minor (API endpoints, a new section), already 0.43.0 (unreleased); one
  CHANGELOG line.
