Task: LAD-123

## Why

The human settled the model of projects (the session artifact `projects-concept`,
2026-10-21; the epic LAD-116, `docs/epics/lad-116/plan.md`, step S2): a project is a
folder `<workspace>/projects/<id>` and its environment variables, so that sessions for
different clients get different keys. Step S1 named the folder LADO keeps code in the
**workspace** and wrote the model down in `docs/design/projects.md`; nothing of it is built.

Today the workspace exists only when `LADO_REPOS` is set (`clone.repos_folder`); without
it a clone or a fresh start goes to `~/lado/<repo>` (`clone.DEFAULT_PARENT`), the New
session window has no workspace and `lado doctor` no Workspace line. Projects need a
workspace on every installation, and LADO has no record of a project.

This step builds the project in the core and its CLI, and makes the workspace one
function with a default (decision D3 of the epic: `~/workspace`). Sessions in a project,
repositories, variables and the UI of projects are later steps.

## What Changes

- **The workspace is one function of the core** (`projects.workspace`): `LADO_REPOS` when
  it is an absolute path after `~` is expanded, else `~/workspace`. A `LADO_REPOS` that is
  set but not absolute is ignored and `lado doctor` warns. The clone's default folder, a
  fresh start's default folder, the UI server (`GET /api/repos-folder`), the container's
  "Outside the workspace" warning, `lado doctor` and projects all take it.
  - Without `LADO_REPOS` a clone or a fresh start with no folder given goes to
    `~/workspace/<repo>` (was `~/lado/<repo>`). Sessions in `~/lado/...` keep working;
    CHANGELOG says so.
  - LADO makes `~/workspace` on first need (the first clone, fresh start or project).
  - `lado doctor` always prints the Workspace line: `<path> (LADO_REPOS)` or
    `<path> (default)`, with `, not made yet: the first clone or project makes it` while
    the folder does not exist.
  - The New session window: the Where placeholder is `<workspace>/…` (was
    `~/projects/app` without `LADO_REPOS`), Clone into's `<workspace>/<repo>` and From
    scratch's `<workspace>/<name>` (were `~/lado/…`). The Workspace row and the
    subfolder hints of an empty Where show only once the folder exists.
    `GET /api/repos-folder` answers `{path, made}`; the path stays the API's.
- **A project**: an id that never changes (`[a-z0-9][a-z0-9-]*`, 1–40 characters,
  lowercase only so the folder does not depend on the file system's case), a title that
  can change (shown as the id while unset; the session title's rule), and a record in
  `lado.db` (a new table `projects`, schema 32). Its folder `<workspace>/projects/<id>` is
  stored nowhere: it is derived from the id. LADO makes it.
- **`lado project`** with `list`, `create <id> [--title TEXT]`, `show <id>`,
  `rename <id> <title>` and `delete <id> [--yes]`:
  - `create` refuses, naming why: a bad id; a project of that id; a folder of that name in
    `projects/`; `projects/` that is the human's own folder (it exists, holds visible
    entries and none of them is a project's folder); a workspace LADO cannot make or
    write in.
  - `list` and `show` give the title and the folder; a project whose folder is missing
    (another workspace, or deleted by hand) is marked `(folder not found)`.
  - `delete` lists the repositories of the folder (and their worktrees) with uncommitted
    changes or branches not pushed, and refuses without `--yes`; with `--yes` it removes
    the folder whole and the record. It never removes anything outside `projects/`; a
    project folder that is a symbolic link loses the link only.
  - `create`, `rename` and `delete` refuse inside an agent of LADO (`LADO_AGENT` set);
    `list` and `show` work there. No MCP tool for projects.
- **`lado doctor`, check `Projects`**: one line once LADO has a project or `projects/`
  exists: how many projects, a project whose folder is not found, a foreign folder in
  `projects/` (no project of LADO), and `projects/` that is the human's own.
- **Code names** built around the workspace function: `clone.repos_folder`,
  `clone.REPOS`, `clone.DEFAULT_PARENT` and `clone.default_parent` give way to
  `projects.workspace` and `projects.WORKSPACE_VAR`; `doctor.check_repos_folder` becomes
  `check_workspace`; `runtime.OUTSIDE_REPOS` / `outside_repos` become
  `OUTSIDE_WORKSPACE` / `outside_workspace`; the API model `ReposFolder` becomes
  `Workspace` (the path `/api/repos-folder` and the capability `repos-folder` keep their
  names).
- **S1's leftover**: "the projects' toolchains" meaning the code in general becomes "the
  repositories' toolchains" in `docker/Dockerfile`, `docs/install.md` (heading),
  `docs/design/modules.md` and the docstring of `tests/container/test_toolchains.py`.
- **Docs**: `docs/cli.md` (`lado project`, the clone's and fresh start's default),
  `docs/design/modules.md` (`projects.py`, the renames), `docs/design/projects.md` (the
  project, its CLI and the workspace default marked built), `docs/design/ui.md` (Where,
  Clone into, Create in), `docs/install.md` (`~/lado` defaults), AGENTS.md (one layout
  line for `projects.py`).
- **CHANGELOG**: the heading `## 0.42.1 (unreleased)` becomes `## 0.43.0 (unreleased)`
  (0.42.1 is not released); two lines: projects in the CLI, and the workspace default
  `~/workspace` with existing `~/lado` sessions kept.

## Acceptance criteria

- **AC-1** Without `LADO_REPOS`, `lado start <git-url>` and the window's Clone from URL
  clone into `~/workspace/<repo>`, and From scratch makes `~/workspace/<name>`, making
  `~/workspace` when it is missing; with `LADO_REPOS=/srv/code` they use `/srv/code/…`.
- **AC-2** `lado doctor` prints the Workspace line with and without `LADO_REPOS`, `not made
  yet` while the folder is missing, and warns for a `LADO_REPOS` that is not absolute,
  naming `~/workspace` as used.
- **AC-3** The window's Where shows `<workspace>/…` as its placeholder; no Workspace row
  and no hints while the workspace does not exist; the row and the hints once it does.
- **AC-4** `lado project create shop --title Shop` makes the record and
  `<workspace>/projects/shop`; `list`, `show` and `rename` print and change it as
  `docs/cli.md` says; a project whose folder is gone shows `(folder not found)`.
- **AC-5** `create` refuses with its reason a bad id, a taken id, an existing folder of
  that name, and `projects/` that is the human's own folder; nothing is made.
- **AC-6** `delete` without `--yes` lists uncommitted changes and unpushed branches of the
  folder's repositories and refuses; with `--yes` the folder and the record are gone, and
  nothing outside `<workspace>/projects/<id>` is touched.
- **AC-7** `create`, `rename` and `delete` refuse inside a LADO agent; `list` and `show`
  work.
- **AC-8** `lado doctor`'s Projects line names a foreign folder, a project without its
  folder, and `projects/` that is the human's own.
- **AC-9** An older `lado.db` (schema 31) upgrades to 32 with its backup, and the table
  `projects` exists.
- **AC-10** No document outside the historical ones (`openspec/changes/archive/`,
  `docs/superpowers/`, `docs/research/`, `docs/epics/`, CHANGELOG's released sections)
  says that the default clone folder is `~/lado` or that there is no workspace without
  `LADO_REPOS`.

## Out of scope

- Sessions in a project, `lado start --project/--repo`, refusing a session without a
  project inside `projects/`, the hints leaving out `projects/`, a project's repositories
  read from disk: step S3 (the concept's phase 3).
- Adding and removing a project's repositories: step S4.
- A project's variables and secrets, and deleting its secrets: steps S5a, S5b.
- The UI of projects (section, page, the window's Project way): steps S6, S7.
- Compose's `LADO_WORKSPACE`: step S2b.
- The container spec's scenarios and requirements that say "project" for a repository
  under `LADO_REPOS`: step S2b, which changes that spec anyway (the human, #615).
- Renaming the capability `repos-folder` or the API path `/api/repos-folder`: openspec
  has no rename of a capability, and the path is part of an installation's API.
- An MCP tool for projects: the concept forbids agents to change projects.
- Moving existing `~/lado/...` folders: LADO never moves the human's folders; their
  sessions keep working where they are.

## Impact

- Code: new `src/lado/projects.py`; `clone.py`, `scratch.py`, `runtime.py`, `doctor.py`,
  `cli.py`, `state.py` (schema 32), `server/app.py`, `server/models.py`,
  `server/launch.py`, `server/clones.py`; `web/src/Launch.tsx`, `web/src/api.ts`,
  `web/openapi.json`, `web/src/api.gen.ts`.
- Tests: unit, integration (`tests/integration/test_projects.py`), UI e2e for Where.
- Users: a new CLI command, a schema migration, a new default folder. Version: **minor**.
