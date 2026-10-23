Task: LAD-137

## Why

Step S6b of the epic LAD-116 (`docs/epics/lad-116/plan.md`; the model is
`docs/design/projects.md` and the concept `projects-concept`, section "The session"). Steps
S3–S6a built sessions in a project (`lado start --project <id> --repo <name>`), a project's
repositories, its variables and secrets, and the Projects section of the web UI, but a
session in a project still starts only from the CLI: the New session window knows a folder,
a fresh start and a clone, and the server's start (`POST /api/sessions`) only the kinds
`folder` and `scratch`. A human who runs LADO from the browser (or in LADO's image) can make
a project and give it keys, and then cannot start a session that gets them. Worse, Folder
refuses a project's repository ("belongs to the project Shop: start a session in the
project") and offers only a CLI command.

The root cause: the start's request has no way to name a project and its repository, and the
window has no way to choose them.

The human narrowed the step at its design (answers #1282, #1283): **the New session window
only chooses** a project and one of its repositories; a project's repositories are managed
on the project's page only, and that page's repositories (list, adding, removing) stay in
step S7. The concept's "+ new repository" in the window is dropped.

## What Changes

- **Server API** (in OpenAPI, `make web-types`):
  - `POST /api/sessions` takes `where: {kind: "project", project: <id>, repo: <name>}` and
    starts the session as `lado start --project <id> --repo <name>` does, through the same
    core function (`runtime.start_session` with `project` and `repo_name`), with the core's
    refusals: an unknown project or repository is 404 with the core's text, a taken name 409
    `Taken` as for a folder, any other refusal 400. A `project` or `repo` with another kind,
    or a `path` with this one, is 400.
  - `GET /api/project-launch?project=&repo=` (new, read-only): what the Project way shows —
    the projects sorted by title, the project chosen (the one asked, else the project of the
    latest started session in a project, else the first), its repositories, the repository
    chosen (the one asked, else that of the project's latest started session, else the
    first, none in an empty project), and for that repository the session's default name
    `<project>-<repo>`, the name's state, the provider a new session there takes and the
    repository's last session (its kits and mode become the window's defaults, as in
    Folder).
  - `GET /api/folders` gains `project` for a folder inside a project's folder: `{id, title,
    repo}`, `repo` the project's repository the folder is in, or null.
- **The New session window**: the switch becomes **From scratch | Folder | Clone from URL |
  Project** (a 2×2 grid on a phone). Project shows a select of the projects (one whose
  folder is not found is off, marked `folder not found`), the project's facts, and its
  repositories as a list that always shows, even with one item (name, branch, remote). Name
  is `<project>-<repo>` until edited; Kits, Provider and Permission mode as in Folder, from
  the repository's last session. **Start session** starts it. An empty project shows `No
  repositories yet. Add one on the project's page:` with a link to the page; no project at
  all shows `No projects yet…` with a link to the Projects section. The window still opens
  in Folder (From scratch without recent folders).
- **Folder's refusal inside a project** gains a button: for a project's repository `Start in
  the project <title>` switches the window to Project with that project and repository; for
  any other folder of a project `Open the project <title>` opens the project's page. The CLI
  command stays below it. The refusals of Clone into and Create in stay as they are.
- **The project's page**: its not-built line starts with the link `New session in this
  project…`, which opens the window in Project with this project, and names what S7 brings.
- **The canary** (`tests/integration/test_project_secrets_canary.py`) starts its session in
  the project through `POST /api/sessions`: no secret in the start's answer, the feed or the
  logs.
- **Docs**: `docs/design/ui.md` (Launch: the fourth way; Projects: the page's line),
  `docs/design/projects.md` (the session's way without "+ new repository", what is built,
  the step table), CHANGELOG under `## 0.43.0 (unreleased)`.

## Acceptance criteria

- AC-1. `POST /api/sessions` with `where: {kind: "project", project: "shop", repo:
  "frontend"}` and the change token starts `shop-frontend` in
  `<workspace>/projects/shop/frontend` with project `shop`, by `runtime.start_session(None,
  …, project="shop", repo_name="frontend")`; the answer is `Started` as for a folder.
- AC-2. Its refusals: unknown project or repository 404 with the core's text; a name any
  session has (of this project, another or none) 409 `Taken`; `path` with kind
  `project`, a missing `project` or `repo`, or `project`/`repo` with kind `folder` or
  `scratch` 400; without the token it is refused.
- AC-3. `GET /api/project-launch` answers the projects by title, the chosen project and
  repository by the rule of What Changes, the default name, `name_state` (a session of that
  name in another project or none counts as `taken_elsewhere`), the provider suggestion and
  the last session; it makes nothing (no `lado.db` without one: no projects).
- AC-4. `GET /api/folders` for a path inside a project's folder carries `project: {id,
  title, repo}`; for a path outside, or inside a foreign folder of `projects/`, `project` is
  null.
- AC-5. The window's switch has Project last; on a 390 px screen the four buttons form a 2×2
  grid within the window.
- AC-6. Project chooses a project and a repository as AC-3 says, shows the list always,
  disables a project whose folder is not found, and starts with `where.kind: "project"`;
  the session opens with `project Shop` in its head.
- AC-7. An empty project shows the line with the link to its page and Start is off; with no
  project the line links to `/projects`.
- AC-8. A refused start (taken name) shows the core's text and `Resume it` as Folder does.
- AC-9. Folder's refusal of a project's repository offers `Start in the project <title>`,
  which switches to Project with it; of another folder of a project, `Open the project
  <title>`, which opens `/projects/<id>`.
- AC-10. The project's page shows `New session in this project…`, which opens the window in
  Project with the project chosen.
- AC-11. The canary starts its session in the project through the API, and no secret is in
  the start's answer, the feed, the logs or the files it searches.
- AC-12. `docs/design/ui.md`, `docs/design/projects.md` and CHANGELOG say it; the settings'
  checks and CI are green.

## Out of scope

- **Adding a repository from the New session window** ("+ new repository", by clone or from
  scratch): dropped by the human (#1282); repositories are managed on the project's page.
- **The project's page with its repositories** (list, "+ Add repository", delete), its
  sessions, renaming and deleting the project: step S7 (#1283), with S5a's findings S2, G1,
  X3, F5 and S6a's E2, M1.
- **A Project button for the refusals of Clone into and Create in**: they would lead to
  adding a repository from the window, which the human dropped; they keep the core's text
  and command.
- **Sessions over several repositories** ("all repositories" in the list): the concept's
  "Not now".
- **Opening the window in Project by default**: the human kept the current rule (#1283).

## Impact

- Code: `src/lado/server/models.py` (`Where`, `FolderInfo.project`, `ProjectPlace`,
  `ProjectLaunch`), `src/lado/server/app.py` (`POST /api/sessions`, `GET
  /api/project-launch`), `src/lado/server/launch.py`, `src/lado/projects.py` (`place`),
  `web/src/Launch.tsx` (the Project way, possibly in a file of its own), `web/src/api.ts`,
  `web/src/Projects.tsx`, `web/src/styles.css`, `web/openapi.json`, `web/src/api.gen.ts`.
- No schema migration; no change to the agents' protocol, `mcp_server.py`, `hooks.py` or
  `providers/`.
- Version: minor (an API change), already `0.43.0 (unreleased)`.
