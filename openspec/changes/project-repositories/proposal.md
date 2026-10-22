Task: LAD-128

## Why

Step S4 of the epic LAD-116 (`docs/epics/lad-116/plan.md`; the model is
`docs/design/projects.md` and the concept `projects-concept`, sections "The project" (its
last paragraph), "How LADO knows a project's repositories", "The session" (item 3) and
"Deleting"). Step S3 reads a project's repositories from the disk and starts sessions in
them, but LADO cannot put a repository into a project: the human clones or runs `git init`
by hand in `<workspace>/projects/<id>/`, which in LADO's image means going to the host or
into the container. Nor can LADO remove a repository no longer needed: only the whole
project can be deleted.

The root cause: the two ways LADO makes a repository, a clone (`lado.clone`) and a fresh
start (`lado.scratch`), take any folder but `projects/`, which S3 made them refuse (the
state `in_project`), and nothing in `lado.projects` names a repository's folder or removes
one. A remnant of S3 (E3 of its ledger) shows the gap: a refused clone or fresh start into
a folder not made yet under `projects/<id>/` offers `lado start --project <id> --repo
<name>`, which then refuses the name as an unknown repository.

## What Changes

- **Add a repository by a clone.** `lado project repo add <id> <git-url> [--name NAME]
  [--branch BRANCH]` clones into `<workspace>/projects/<id>/<name>` through `clone.clone`
  (a hidden temporary folder renamed at the end, so a clone still running or failed is
  never listed), with the same progress and Ctrl-C as `lado start <git-url>`. The name is
  the URL's (as `git clone` takes it) unless `--name` gives one. It prints `Added
  repository <name> to project <id>: <folder>` and `Start a session in it: lado start
  --project <id> --repo <name>`.
- **Add a repository from scratch.** `lado project repo add <id> --new <name>` makes
  `<workspace>/projects/<id>/<name>` a git repository with an empty first commit through
  `scratch.make`, with its checks (git's author among them).
- **The repository's name.** Latin letters (case kept), digits, `.`, `_` and `-`, not
  starting with `.` or `-`, at most 100 characters; a name taken in the project's folder
  (a repository, a plain folder, a link or a file) is refused, and nothing is cloned or
  made.
- **Remove a repository.** `lado project repo remove <id> <name> [--yes]` works as `lado
  project delete`, within the repository's folder and its sessions: refused while any
  session working in that folder is not stopped (with a project or without, by path, as
  S3's D9); lists the project's stopped sessions in the repository it forgets, then the
  repository's unpushed work (uncommitted changes, branches not pushed, the workers'
  worktrees with changes); without `--yes` it changes nothing; with `--yes` it removes the
  folder, then forgets those sessions as `lado forget --force` does. A symbolic link in the
  project's folder loses the link only, never its target. A plain folder or a file there
  is refused: LADO removes only repositories and links. Nothing outside
  `<workspace>/projects/<id>/` is ever removed.
- **Only the human.** `lado project repo add` and `remove` refuse inside an agent, as
  `lado project create` does; no MCP tool is added.
- **The server's API** (for the UI of steps S6 and S7 and the future LADO manager, with
  the token, in OpenAPI): `POST /api/clones` takes `project` and `name` for a clone job
  into a project; `POST /api/projects/{id}/repos` makes one from scratch;
  `GET /api/projects/{id}/repos/{name}/removal` shows what removing it forgets and loses;
  `DELETE /api/projects/{id}/repos/{name}` removes it. 404 for an unknown project or name.
- **S3's remnant E3.** The refusal inside a project's folder offers a session only for a
  repository of the project; for a name that is none it offers `lado project show <id>`,
  and a clone or fresh start into a folder not made yet directly in a project's folder
  offers `lado project repo add <id> <git-url> [--name <name>]` or `lado project
  repo add <id> --new <name>`; `lado start --project <id> --repo <name>` in a project with
  no repositories says `add one with lado project repo add <id> <git-url> or --new
  <name>`.
- **Docs**: `docs/cli.md`, `docs/design/projects.md` (adding and removing repositories
  built), `docs/design/modules.md`, `docs/design/ui.md` (the clone job's new fields).
- **CHANGELOG**: one line under `## 0.43.0 (unreleased)`.

## Acceptance criteria

- **AC-1** With project `shop` and a bare repository `/srv/git/frontend.git`, `lado
  project repo add shop /srv/git/frontend.git` clones into `<ws>/projects/shop/frontend`,
  prints the `Added repository` and `Start a session in it` lines, `lado project show shop`
  lists `frontend` with its branch and remote, and `lado start --project shop --repo
  frontend` starts in it.
- **AC-2** `lado project repo add shop --new site` makes `<ws>/projects/shop/site` a git
  repository with one empty commit, listed by `lado project show shop` and fit for `lado
  start --project shop --repo site`.
- **AC-3** A clone that fails or is ended (Ctrl-C, SIGTERM) leaves no folder `frontend`
  and no temporary folder in `<ws>/projects/shop`, and `lado project show shop` lists no
  such repository.
- **AC-4** A name taken in the project's folder, a name that breaks the name rule, a URL
  that gives no name, an unknown project and a project whose folder is not found are
  refused, exit 1, with nothing cloned or made; `--new` with a URL, `--name` or `--branch`
  with `--new`, and neither a URL nor `--new` are usage errors (exit 2).
- **AC-5** `lado project repo remove shop frontend` refuses, exit 1, changing nothing,
  while a session working in `<ws>/projects/shop/frontend` is not stopped, naming it and
  `lado stop`.
- **AC-6** With only stopped sessions, `lado project repo remove shop frontend` lists
  `Sessions to forget: …` and the unpushed work, a worker's branch not pushed in its
  worktree included, then refuses without `--yes`, changing nothing; with `--yes` it
  removes the folder, forgets those sessions and prints `Removed repository frontend from
  project shop`.
- **AC-7** The other repositories of the project, the project's record and folder, and
  everything outside `<ws>/projects/shop/frontend` stay as they were; a link `docs` to a
  repository elsewhere loses the link only; a plain folder `notes` is refused; an unknown
  name is refused naming the project's repositories.
- **AC-8** From an agent (`LADO_AGENT` set) `lado project repo add` and `remove` exit 1
  with `lado project repo add is for the human; agent "<agent>" cannot use it` (and
  `remove`), and nothing changes.
- **AC-9** `POST /api/clones` with `project` and `name` clones into the project; `POST
  /api/projects/{id}/repos` makes one from scratch; `GET …/repos/{name}/removal` gives the
  sessions and the unpushed lines; `DELETE …/repos/{name}` removes it; an unknown project
  or name is 404, a refusal 400 with its reason; `web/openapi.json` and `web/src/api.gen.ts`
  are current.
- **AC-10** `lado start --new <ws>/projects/shop/web` refuses with `lado: Add a repository
  to the project: lado project repo add shop --new web`, `lado start
  https://github.com/shop/web <ws>/projects/shop/web` with `lado project repo add shop
  https://github.com/shop/web`, and `lado start <ws>/projects/shop/notes` (a plain folder)
  with `lado project show shop`; `lado start --project acme --repo crm` in a project
  without repositories refuses with `add one with lado project repo add acme <git-url> or
  --new <name>`.

## Out of scope

- The project's variables and secrets: steps S5a, S5b.
- The Projects section, the Project way and "+ new repository" of the New session window:
  step S6; the project's page and removing a repository or a project from the UI: step S7.
  S4 builds only the API they will call.
- `lado start --project <id> <git-url>` or `--new` that starts a session in a new
  repository at once (the human's answer #892): one way to add is enough; the UI's "+ new
  repository" will call the API to add, then start.
- A preview of a clone's target in a project (`GET /api/clone-target` with a project):
  step S6, with the window that shows it; the job itself refuses with the same reasons.
- Removing a plain folder or a file in a project's folder (#892): it cannot be checked for
  unpushed work; the human removes it by hand.
- Transliterating a typed name into a repository's name: the UI does it in S6, as for a
  fresh start today; the CLI takes the folder's name as it is (#892).
- Adding or removing repositories from inside an agent (`start_session`, a clone in a
  session in a project): the concept lets only the human change projects.
- S2's findings about the check before deleting (F2: the project folder's root, a detached
  HEAD, a stash; E3 of S2: a folder LADO cannot read; F3; F5) and G1 of S3: step S7.
  `projects.unpushed` keeps its behaviour; S4 only splits out the check of one checkout.
- Additions to repositories in the database (an order, a role, an address to clone again):
  "Later" in the concept.

## Impact

- Code: `src/lado/projects.py` (the name rule, adding, removing, the check of one
  checkout, the refusal's hints), `clone.py` (a clone into a project's folder, the add
  hint), `scratch.py` (a fresh start into a project's folder, the add hint), `cli.py`
  (`lado project repo add|remove`), `server/app.py`, `server/models.py`,
  `server/clones.py`, `server/launch.py`; `web/openapi.json`, `web/src/api.gen.ts`.
- Not changed: `mcp_server.py`, `hooks.py`, `providers/`, `runtime.py`'s start, the
  schema (repositories stay on the disk), the UI's screens.
- Tests: unit, server, integration with the fake agent.
- Users: new CLI commands and API endpoints. Version: **minor** (0.43.0 is already the
  unreleased minor; one CHANGELOG line).
