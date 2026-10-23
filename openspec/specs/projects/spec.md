# projects Specification

## Purpose
The human's projects: a project is an id, a title and a record in `lado.db`, with its folder
`<workspace>/projects/<id>` derived from the id and made by LADO; `lado project` makes,
lists, shows, renames and deletes them, agents only read them, and `lado doctor` checks
them.

## Requirements

### Requirement: A project is an id, a title and a record in lado.db

LADO SHALL keep a project as a record of the table `projects` in `lado.db` (schema 32): its
id, its title or none, and when it was made. The id SHALL match `[a-z0-9][a-z0-9-]*` and
be 1 to 40 characters long, and SHALL never change. The title SHALL follow the session
title's rule (`runtime.check_title`): trimmed, none when empty or equal to the id, at most
80 characters, one line of visible text; two projects MAY have the same title. Where a
project has no title, LADO SHALL show its id.

#### Scenario: A project with a title
- **WHEN** the human runs `lado project create shop --title "  Shop  "`
- **THEN** `lado.db` has the project `shop` with the title `Shop`

#### Scenario: A title equal to the id
- **WHEN** the human runs `lado project create acme --title acme`
- **THEN** the project `acme` has no title, and `lado project list` shows `acme` in its
  title's place

### Requirement: A project's folder is derived from its id

A project's folder SHALL be `<workspace>/projects/<id>` (`projects.workspace`), computed
each time and stored nowhere; another folder SHALL NOT be accepted. A project whose folder
does not exist (the workspace changed, or the folder was deleted by hand) SHALL be shown
with `(folder not found)` and SHALL keep its record.

#### Scenario: Another workspace
- **WHEN** the project `shop` was made with `LADO_REPOS=/srv/a` and `lado project list`
  runs with `LADO_REPOS=/srv/b`, where `/srv/b/projects/shop` does not exist
- **THEN** the line of `shop` names `/srv/b/projects/shop  (folder not found)`

### Requirement: lado project create makes the record and the folder

`lado project create <id> [--title TEXT]` SHALL make the record and the folder
`<workspace>/projects/<id>`, making the workspace and `projects/` when they are missing,
and SHALL print `Made project <id> "<title>": <folder>` (without `"<title>"` when there is
none). When the folder cannot be made, the record SHALL NOT stay.

#### Scenario: The first project in a new workspace
- **WHEN** `~/workspace` does not exist, `LADO_REPOS` is unset and the human runs
  `lado project create shop --title Shop`
- **THEN** `~/workspace/projects/shop` exists, the project `shop` is in `lado.db`, and the
  output is `Made project shop "Shop": /Users/ann/workspace/projects/shop`

### Requirement: lado project create refuses with its reason and makes nothing

`lado project create` SHALL refuse, exit 1 with `lado: <reason>`, and make no record and
no folder, when the id breaks the id rule, a project of that id exists,
`<workspace>/projects/<id>` exists, `<LADO_HOME>/projects/<id>` exists (left by a project
of that id whose deletion failed), `projects/` is the human's own folder, or the
workspace is not a folder LADO can make or write in (`lado doctor`'s reason).

#### Scenario: A bad id
- **WHEN** the human runs `lado project create Shop`
- **THEN** it exits 1 with `lado: the project id Shop is not valid: lowercase Latin
  letters, digits and -, starting with a letter or digit, at most 40 characters`, and
  nothing is made

#### Scenario: A taken id
- **WHEN** LADO has the project `shop` and the human runs `lado project create shop`
- **THEN** it exits 1 with `lado: project shop exists`

#### Scenario: The folder exists
- **WHEN** `~/workspace/projects/shop` exists with no project `shop` in LADO and the human
  runs `lado project create shop`
- **THEN** it exits 1 with `lado: <folder> already exists: LADO makes a project's folder
  itself; choose another id or move that folder away`, and LADO has no project `shop`

#### Scenario: The data folder is left
- **WHEN** `<LADO_HOME>/projects/shop` exists with no project `shop` in LADO and the human
  runs `lado project create shop`
- **THEN** it exits 1 with `lado: <LADO_HOME>/projects/shop is left from a project shop:
  remove it or choose another id`, and LADO has no project `shop`

#### Scenario: A workspace that is a file
- **WHEN** `LADO_REPOS=/srv/notes`, a regular file, and the human runs `lado project create
  shop`
- **THEN** it exits 1 with `lado: LADO_REPOS is not a folder: /srv/notes`

### Requirement: projects/ is the human's own folder when no project of LADO is in it

`<workspace>/projects` SHALL be the human's own folder when it exists, holds an entry
whose name does not start with `.`, and none of its entries is the folder of a project in
`lado.db`; then `create` SHALL refuse. Entries whose names start with `.` SHALL NOT
count, and once a project's folder is in `projects/`, another entry SHALL NOT block a new
project.

#### Scenario: The human's own projects folder
- **WHEN** `~/workspace/projects` holds `notes` and `drafts` and LADO has no project
- **THEN** `lado project create shop` exits 1 with `lado: <ws>/projects is your own folder
  (it holds drafts, notes): LADO keeps projects there only; move it away or set
  LADO_REPOS to another workspace`, naming at most three entries

#### Scenario: Only Finder's file
- **WHEN** `~/workspace/projects` holds only `.DS_Store`
- **THEN** `lado project create shop` makes the project

#### Scenario: A foreign folder beside a project
- **WHEN** `~/workspace/projects` holds `shop` (project `shop`) and `old`
- **THEN** `lado project create acme` makes the project, `old` stays as it is, and
  `lado doctor` names `old` as foreign

### Requirement: lado project list and show print projects with their folders

`lado project list` SHALL print one line per project, by id: the id, the title (the id
when none) and the folder, with `  (folder not found)` when the folder does not exist; with
no project it SHALL print `No projects. Make one with: lado project create <id>`.
`lado project show <id>` SHALL print `<id> "<title>"` (the id alone without a title), then
`  folder:  <folder>` (with the same mark) and `  made:    <local date and time>`; an
unknown id SHALL exit 1 with `lado: unknown project "<id>"`.

#### Scenario: Two projects
- **WHEN** LADO has `shop` titled `Shop` with its folder and `acme` without a title whose
  folder is gone
- **THEN** `lado project list` prints `acme  acme  <ws>/projects/acme  (folder not
  found)` and `shop  Shop  <ws>/projects/shop`

### Requirement: lado project rename changes only the title

`lado project rename <id> <title>` SHALL set the title by the title rule (an empty text
clears it) and print `<id>: title "<title>"` or `<id>: no title`; the id, the folder and
everything in it SHALL stay as they are. An unknown id SHALL exit 1.

#### Scenario: Rename
- **WHEN** the human runs `lado project rename shop "Shop EU"`
- **THEN** `lado project show shop` prints `shop "Shop EU"` and the same folder

### Requirement: lado project delete shows unpushed work and needs --yes

`lado project delete <id>` SHALL list the project's sessions it will forget, `Sessions to
forget: <name> (<n> open run[s]), …` (no line without sessions), then the unpushed work of
the project folder: for each git repository directly in it, and each worktree of one, its
uncommitted changes (untracked files included) and each local branch with no upstream or
ahead of it. Without `--yes` it SHALL then refuse, exit 1, changing nothing.

#### Scenario: Unpushed work
- **WHEN** the project folder holds the repository `frontend` with an uncommitted file and
  a branch `feature-x` with no upstream, and the human runs `lado project delete shop`
- **THEN** the output has `Unpushed work in <folder>:` and `  frontend: uncommitted
  changes; branch feature-x not pushed`, then `lado: deleting project shop removes its
  folder <folder> with everything in it; run again with --yes`; it exits 1, and the
  folder and the record stay

#### Scenario: A repository git cannot read
- **WHEN** a subfolder `broken` has a `.git` git cannot read
- **THEN** the list has `  broken: could not check: <git's first line>`

#### Scenario: Nothing unpushed
- **WHEN** every repository of the folder is pushed and clean
- **THEN** no list is printed, and without `--yes` the command still refuses

#### Scenario: Stopped sessions
- **WHEN** `shop-frontend` (one open run) and `fix-login` of project `shop` are stopped and
  the human runs `lado project delete shop`
- **THEN** the output has `Sessions to forget: fix-login, shop-frontend (1 open run)` and
  ends with `… and forgets its 2 sessions; run again with --yes`; nothing changes

### Requirement: lado project delete --yes removes the folder, then the record

`lado project delete <id> --yes` SHALL remove the project folder whole, then forget each
of the sessions it listed (as `lado forget --force` does), then remove its data folder
`<LADO_HOME>/projects/<id>/`, then the record, and print `Deleted project <id>`. A project
whose folder is not found SHALL lose its sessions, data folder and record only. When the
folder or the data folder cannot be removed whole, the record SHALL stay and the command
SHALL exit 1 naming what stayed.

#### Scenario: Confirmed
- **WHEN** the human runs `lado project delete shop --yes`
- **THEN** `<ws>/projects/shop`, `<LADO_HOME>/projects/shop` and the record are gone, and
  `<ws>/projects` and the rest of the workspace are as they were

#### Scenario: The folder already gone
- **WHEN** the folder of `acme` is not found and the human runs `lado project delete acme
  --yes`
- **THEN** the record is gone and no folder is touched

#### Scenario: With stopped sessions
- **WHEN** `shop-frontend` of project `shop` is stopped and the human runs `lado project
  delete shop --yes`
- **THEN** the folder, the session `shop-frontend` with its history, and the record are
  gone, and `lado ls` no longer lists it

### Requirement: lado project delete removes nothing outside the project folder

`lado project delete` SHALL remove only `<workspace>/projects/<id>`, whose real path
SHALL be a direct child of the real path of `<workspace>/projects`, or else refuse. When
`<workspace>/projects/<id>` is a symbolic link, it SHALL remove the link and never its
target.

#### Scenario: A link to a folder elsewhere
- **WHEN** `<ws>/projects/shop` is a symbolic link to `/srv/shop` and the human runs
  `lado project delete shop --yes`
- **THEN** the link is gone, `/srv/shop` and its files stay, and the record is gone

### Requirement: Agents cannot change projects

`lado project create`, `rename`, `delete`, `set` (with `--secret` too), `unset`, `repo
add` and `repo remove` SHALL refuse, exit 1 with `lado: lado project <command> is for the
human; agent "<agent>" cannot use it` and change nothing, when `LADO_AGENT` is set (every
agent of LADO has it). `list` and `show` SHALL work for agents. LADO SHALL offer no MCP
tool that makes, changes or deletes a project, its repositories, its variables or its
secrets.

#### Scenario: From an agent
- **WHEN** a worker runs `lado project create shop` in its shell
- **THEN** it exits 1 with that text, and no project or folder is made

#### Scenario: Adding a repository from an agent
- **WHEN** a worker runs `lado project repo add shop --new site` in its shell
- **THEN** it exits 1 with `lado: lado project repo add is for the human; agent
  "<agent>" cannot use it`, and no folder `site` is made

#### Scenario: Setting a variable from an agent
- **WHEN** a worker runs `lado project set shop MODEL_URL http://evil` in its shell
- **THEN** it exits 1 with `lado: lado project set is for the human; agent "<agent>"
  cannot use it`, and `shop` keeps its variables as they were

#### Scenario: Setting a secret from an agent
- **WHEN** a worker runs `printf x | lado project set shop GH_TOKEN --secret` in its shell
- **THEN** it exits 1 with `lado: lado project set is for the human; agent "<agent>"
  cannot use it`, before reading stdin, and `shop` keeps its secrets as they were

### Requirement: lado doctor checks projects

Once LADO has a project or `<workspace>/projects` exists, `lado doctor` SHALL print one
check `Projects`: `ok` with `<n> in <workspace>/projects` when nothing is wrong, else
`warn` with each finding joined by `; ` (a project whose folder is not found, foreign
folders, `projects/` that is the human's own). With no project and no `projects/` it SHALL
print no such line.

#### Scenario: All well
- **WHEN** LADO has `shop` and `acme`, both with their folders
- **THEN** `lado doctor` prints `[ok  ] Projects: 2 in <ws>/projects`

#### Scenario: A foreign folder and a missing one
- **WHEN** LADO has `shop` (folder there) and `acme` (folder gone), and `projects/` also
  holds `old`
- **THEN** `lado doctor` prints `[warn] Projects: acme: folder not found <ws>/projects/acme;
  foreign folder in projects/: old`

#### Scenario: The human's own folder
- **WHEN** LADO has no project and `<ws>/projects` holds `notes`
- **THEN** `lado doctor` prints `[warn] Projects: <ws>/projects is your own folder (it holds
  notes): LADO cannot make projects there`

#### Scenario: Nothing yet
- **WHEN** LADO has no project and `<ws>/projects` does not exist
- **THEN** `lado doctor` prints no Projects line

### Requirement: A session refers to its project in lado.db

LADO SHALL keep a session's project as a reference in its record (`sessions.project`,
schema 33, referring to `projects(id)`), set when the session is made and never changed
while it exists; a session without a project SHALL have none. LADO SHALL NOT take a
session's project from its folder's path. A session made before schema 33 SHALL have no
project.

#### Scenario: The upgrade
- **WHEN** an `lado.db` of schema 32 with the session `site` in
  `<ws>/projects/shop/site` is upgraded
- **THEN** it is backed up, its schema is 33, and `site` has no project

#### Scenario: A resume with other settings
- **WHEN** the stopped session `shop-frontend` of project `shop` is resumed with another
  provider
- **THEN** its project is still `shop`

### Requirement: A project's repositories are read from the disk

A project's repositories SHALL be the entries of its folder whose names do not start with
`.`, that are folders and not symbolic links, and that are each the root of a git
repository (`git rev-parse --show-toplevel` gives the entry's own real path). The list
SHALL be read each time and stored nowhere; the project folder itself SHALL never be one
of them, and a project whose folder is not found SHALL have none.

#### Scenario: Repositories made by hand
- **WHEN** the folder of `shop` holds `frontend` (a `git clone`) and `backend` (`git init`)
- **THEN** its repositories are `backend` and `frontend`, by name

#### Scenario: What is not a repository
- **WHEN** the folder of `shop` holds `notes` (a folder without git), `.web.clone-x1y2` (a
  clone's temporary folder), `docs` (a symbolic link to a repository elsewhere) and the
  project folder itself is a git repository
- **THEN** none of them is a repository of `shop`

#### Scenario: A repository deleted by hand
- **WHEN** the human removes `<ws>/projects/shop/backend`
- **THEN** the next list has no `backend`

### Requirement: A project's repository shows its branch and remote from git

Each repository of a project SHALL have its name, its path, its current branch (none on a
detached HEAD) and its `origin` remote without a secret (`runtime.public_remote`; none
without one), read from git when asked.

#### Scenario: Repositories cloned by hand
- **WHEN** the folder of `shop` holds `frontend` (a clone of
  `https://github.com/shop/frontend` on `main`) and `backend` (`git init` with a commit
  on `dev`, no remote)
- **THEN** `backend` has the branch `dev` and no remote, and `frontend` the branch `main`
  and the remote `https://github.com/shop/frontend`

### Requirement: lado start --project --repo starts a session in a project's repository

`lado start --project <id> --repo <name>` SHALL start a session in the repository `<name>`
of the project `<id>`, refer to the project in its record, and print `Started session
"<session>" in <folder> (project <id>)`. Without `--name` the session SHALL be named the
slug of `<id>-<name>`. Its other options SHALL work as for a folder. A session of that
name in the same project SHALL be resumed.

#### Scenario: A first session in a project
- **WHEN** the project `shop` has the repository `frontend` and the human runs
  `lado start --project shop --repo frontend --no-attach`
- **THEN** the session `shop-frontend` runs in `<ws>/projects/shop/frontend`, its record
  has the project `shop`, and the output has `Started session "shop-frontend" in
  <ws>/projects/shop/frontend (project shop)`

#### Scenario: Started again
- **WHEN** `shop-frontend` is stopped and the human runs the same command
- **THEN** it is resumed, with its history and project

### Requirement: lado start --project --repo refuses what is no repository of the project

`lado start --project <id> --repo <name>` SHALL refuse, exit 1, starting nothing, an
unknown project (`lado: unknown project "<id>"`) and a name that is not one of the
project's repositories: `lado: project <id> has no repository <name>; its repositories:
<names>`, or `lado: project <id> has no repositories yet: add one with lado project repo
add <id> <git-url> or --new <name>` when it has none.

#### Scenario: A name that is not there
- **WHEN** the project `shop` has `backend` and `frontend`, and the human runs
  `lado start --project shop --repo web`
- **THEN** it exits 1 with `lado: project shop has no repository web; its repositories:
  backend, frontend`

#### Scenario: No repositories yet
- **WHEN** the folder of `acme` is empty and the human runs `lado start --project acme
  --repo crm`
- **THEN** it exits 1 with `lado: project acme has no repositories yet: add one with lado
  project repo add acme <git-url> or --new <name>`

### Requirement: lado start --project --repo names a link as one

`lado start --project <id> --repo <name>` SHALL refuse, exit 1, starting nothing, a name
that is a symbolic link in the project's folder, saying so: `lado: <name> in project <id>
is a link to <target>: clone it into <folder> instead`.

#### Scenario: A link
- **WHEN** `<ws>/projects/shop/docs` is a symbolic link to a repository and the human runs
  `lado start --project shop --repo docs`
- **THEN** it exits 1 with `lado: docs in project shop is a link to <target>: clone it
  into <ws>/projects/shop instead`, and no session starts

### Requirement: A session's project never changes

`lado start` SHALL refuse, exit 1, a session name that a session of another project or of
no project has: `lado: session "<session>" is in project <other>` (or `is not in a
project`) followed by `; a session's project never changes: give another name with
--name`.

#### Scenario: The name of a session without a project
- **WHEN** the stopped session `site` has no project and the human runs `lado start
  --project shop --repo frontend --name site`
- **THEN** it exits 1 with `lado: session "site" is not in a project; a session's project
  never changes: give another name with --name`

### Requirement: lado start --project and --repo go together, without a folder

`lado start` SHALL exit 2 with a usage error for `--project` without `--repo`, `--repo`
without `--project`, and `--project` with a folder, a git URL, `--new`, `--branch` or a
second folder.

#### Scenario: A folder given with the project
- **WHEN** the human runs `lado start ~/code/app --project shop --repo frontend`
- **THEN** it exits 2 with a usage error, and no session starts

#### Scenario: The project without its repository
- **WHEN** the human runs `lado start --project shop`
- **THEN** it exits 2 with a usage error naming `--repo`

### Requirement: A session started from a session in a project is in the same project

A session the supervisor starts with `start_session` SHALL be in its parent's project and
in its parent's repository, as a new session of that project; a session without a
project SHALL start one without a project. `start_session`'s arguments SHALL stay
`name` and `question`. A resume, from the CLI, the UI or the container's start, SHALL keep
the session's project.

#### Scenario: The supervisor proposes a session
- **WHEN** the supervisor of `shop-frontend` (project `shop`, repository `frontend`) calls
  `start_session` with the name `fix-login` after the human's approval
- **THEN** `fix-login` runs in `<ws>/projects/shop/frontend` and its record has the project
  `shop`

#### Scenario: A resume from the UI
- **WHEN** the human resumes the stopped `fix-login` from its page
- **THEN** its project is still `shop`

### Requirement: No new session without a project starts inside projects/

When `<workspace>/projects` is LADO's (a folder that is not the human's own), a new session
without a project whose folder, by its real path, is inside it SHALL be refused with kind
`in_project`, starting, cloning and making nothing. A resume of an existing session SHALL
NOT be refused by this rule. When `projects/` is the human's own folder, nothing SHALL be
refused by it.

#### Scenario: lado start in a project's repository
- **WHEN** the project `shop` titled `Shop` has the repository `frontend` and the human runs
  `lado start ~/workspace/projects/shop/frontend`
- **THEN** it exits 1 with `lado: /Users/ann/workspace/projects/shop/frontend belongs to
  the project Shop: start a session in the project` and `lado: Start a session in the
  project: lado start --project shop --repo frontend`, and no session starts

#### Scenario: A folder without git in a project
- **WHEN** the human runs `lado start ~/workspace/projects/shop/notes`, a folder without
  git
- **THEN** the refusal is the project's, not the `git init` hint

#### Scenario: Through a link
- **WHEN** `~/code/front` is a symbolic link to `~/workspace/projects/shop/frontend` and
  the human runs `lado start ~/code/front`
- **THEN** it is refused the same way

#### Scenario: start_session from a session without a project
- **WHEN** a session without a project whose folder is in `<ws>/projects/shop/frontend`
  (started before schema 33) has its supervisor call `start_session`
- **THEN** the tool answers with the refusal of the project `Shop`, and no session starts

#### Scenario: A session from before schema 33 is resumed
- **WHEN** that session is stopped and the human resumes it
- **THEN** it resumes, still without a project

#### Scenario: The human's own projects folder
- **WHEN** LADO has no project and `<ws>/projects` holds the human's repository `app`
- **THEN** `lado start <ws>/projects/app` starts a session as before

### Requirement: The refusal inside projects/ names the project and offers its session

The refusal of a new session inside LADO's `projects/` SHALL read, for a folder below a
project's folder (`<ws>/projects/<id>/<name>/…`), `<path> belongs to the project <title>:
start a session in the project` (the id when it has no title), with the hint `Start a
session in the project:` and `lado start --project <id> --repo <name>` when `<name>` is a
repository of the project, else `See the project's repositories:` and `lado project show
<id>`, as for the project's folder itself.

#### Scenario: The project's folder itself
- **WHEN** the human runs `lado start ~/workspace/projects/shop`, a git repository
- **THEN** it exits 1 with the text naming the project `Shop` and `lado: See the project's
  repositories: lado project show shop`

#### Scenario: A plain folder in a project
- **WHEN** `<ws>/projects/shop/notes` is a folder without git and the human runs `lado
  start <ws>/projects/shop/notes`
- **THEN** it exits 1 with the text naming the project `Shop` and `lado: See the project's
  repositories: lado project show shop`

### Requirement: The refusal inside projects/ for a folder of no project points at the projects

The refusal of a new session in `<ws>/projects` itself or in a folder of it that is no
project's SHALL read `<path> is in <ws>/projects, which holds LADO's projects only: start
a session in a project, or move the folder out of projects/`, with the hint `See the
projects:` and the command `lado project list`.

#### Scenario: A foreign folder
- **WHEN** `<ws>/projects/old` is a repository with no project `old` in LADO, and the human
  runs `lado start <ws>/projects/old`
- **THEN** it exits 1 with `lado: <ws>/projects/old is in <ws>/projects, which holds LADO's
  projects only: start a session in a project, or move the folder out of projects/`

### Requirement: Clones and fresh starts into projects/ are refused before anything is made

`lado start <git-url> <folder>`, `lado start --new <folder>`, `GET /api/clone-target`,
`POST /api/clones`, `GET /api/scratch-target` and `POST /api/sessions` (scratch) SHALL give
a target inside LADO's `projects/` the state `in_project` with the refusal's text and
hint, and clone or make nothing. The CLI SHALL print `lado: <text>` and `lado: <hint>
<command>` and exit 1; `CloneTarget` and `ScratchTarget` SHALL carry the `hint` (null for
the other states).

#### Scenario: A clone into a project's folder
- **WHEN** the human runs `lado start https://github.com/shop/web
  ~/workspace/projects/shop/web`
- **THEN** it exits 1 with the refusal naming the project `Shop` and `lado: Add a
  repository to the project: lado project repo add shop https://github.com/shop/web`, and
  no folder `web` is made

#### Scenario: The server's clone
- **WHEN** `POST /api/clones` asks for a clone into `<ws>/projects/shop/web` by its `path`
- **THEN** it answers 400 with that text, and no clone job starts

### Requirement: The server's folder check refuses a folder inside projects/

`GET /api/folders` SHALL answer for a folder inside LADO's `projects/` with `ok: false`,
`problem_kind: "in_project"`, the refusal's `problem` and `hint`, `scratch: false` and no
subfolders, checked before git; `POST /api/sessions` with `where.kind` `folder` SHALL
answer 400 with the refusal's text. The New session window SHALL show it in its refusal box
(`field-note bad`) with the hint's sentence, its command and Copy, and keep Start off.

#### Scenario: The window's Where in a project's repository
- **WHEN** the human types `/Users/ann/workspace/projects/shop/frontend` in Where
- **THEN** the refusal box reads `/Users/ann/workspace/projects/shop/frontend belongs to the
  project Shop: start a session in the project`, then `Start a session in the project:`
  and `lado start --project shop --repo frontend` with Copy, and Start is off

### Requirement: lado project show lists the project's repositories

`lado project show <id>` SHALL print, after its `made:` line, `  repositories:` and one
line per repository, by name: `    <name>  <branch>  <remote>`, the names and branches
padded to one width, `(detached)` for no branch and `(no remote)` for no remote; with
none, `  repositories: none`. A symbolic link in the project's folder SHALL be listed
among them by name, marked `(a link to <target>: clone it into <folder> instead)`. The
project's variables follow.

#### Scenario: Two repositories
- **WHEN** the project `shop` has `frontend` (branch `main`, remote
  `https://github.com/shop/frontend`) and `backend` (branch `dev`, no remote)
- **THEN** `lado project show shop` prints `  repositories:`, `    backend   dev
  (no remote)` and `    frontend  main  https://github.com/shop/frontend`, then its
  variables

#### Scenario: A link in the project's folder
- **WHEN** `<ws>/projects/shop/docs` is a symbolic link to `/srv/docs`
- **THEN** `lado project show shop` lists `    docs      (a link to /srv/docs: clone it into
  <ws>/projects/shop instead)` between `backend` and `frontend`

#### Scenario: A project whose folder is gone
- **WHEN** the folder of `acme` is gone and the human runs `lado project show acme`
- **THEN** it prints `  folder:  <ws>/projects/acme  (folder not found)` and
  `  repositories: none`

### Requirement: The server gives a project with its repositories

`GET /api/projects/{id}` SHALL answer `{id, title, folder, found, repos, variables,
secrets}`, `repos` the project's repositories as `{name, path, remote, branch}`,
`variables` its variables as `{name, value}` by name, `secrets` the names of its secrets
(as `lado project show` lists them, never a value), and 404 for an unknown id.

#### Scenario: A project
- **WHEN** the UI asks `GET /api/projects/shop`
- **THEN** the answer has `id: "shop"`, its title, its folder, `found: true`, its
  repositories as `lado project show` lists them, its variables and its secrets' names

### Requirement: lado ls prints a session's project

`lado ls` SHALL print `  project <id>` after a session's folder (before its status, such as
`  (stopped)`) for a session in a project, and nothing more for one without.

#### Scenario: A session in a project
- **WHEN** `shop-frontend` of project `shop` runs and the human runs `lado ls`
- **THEN** its line reads `shop-frontend  <ws>/projects/shop/frontend  project shop`

### Requirement: The session's API and head show its project

`SessionInfo` SHALL carry `project`, the project's id or null. `SessionAbout` SHALL carry
`project`, `{id, title}` read when asked, or null. The session's head SHALL show, for a
session in a project, as the first of its facts before the folder, the word `project` and
the project's title (its id when it has none), with the tooltip `Project <id>`; on a phone
the session's details SHALL show `Project <title>` above the folder. A session without a
project SHALL show nothing new.

#### Scenario: The head of a session in a project
- **WHEN** the human opens `shop-frontend` of project `shop` titled `Shop`
- **THEN** the head's facts begin with `project Shop`, whose tooltip is `Project shop`,
  then the folder

#### Scenario: Renamed project
- **WHEN** the project is renamed `Shop EU` and the human opens the session again
- **THEN** the head shows `project Shop EU`

### Requirement: lado project delete refuses while a session in the project's folder runs

`lado project delete <id>`, with `--yes` or without, SHALL refuse, exit 1, changing
nothing, while any session of the project, or any session whose folder is, by its real
path, inside the project's folder (a session with no project, started there before schema
33), is not stopped: `lado: project <id> has sessions not stopped: <names>; stop them first
with lado stop <name>`.

#### Scenario: A running session
- **WHEN** `shop-frontend` of project `shop` runs and the human runs `lado project delete
  shop --yes`
- **THEN** it exits 1 with `lado: project shop has sessions not stopped: shop-frontend;
  stop them first with lado stop <name>`, and the sessions, the folder and the record stay

#### Scenario: A running session from before projects
- **WHEN** `site`, with no project, runs in `<ws>/projects/shop/site` and the human runs
  `lado project delete shop --yes`
- **THEN** it exits 1 with `lado: project shop has sessions not stopped: site; stop them
  first with lado stop <name>`, and the folder and the record stay

### Requirement: lado project delete --yes keeps the record while a session stays

When a session of the project cannot be forgotten, `lado project delete <id> --yes` SHALL
keep the record and exit 1 naming that session: `lado: could not forget session <name>:
<error>; the project stays: run lado project delete <id> --yes again`.

#### Scenario: A session that cannot be forgotten
- **WHEN** the folder of `shop` is removed and forgetting `shop-frontend` fails
- **THEN** the command exits 1 naming `shop-frontend`, the record stays, and running it
  again goes on

### Requirement: lado project repo add clones a repository into the project's folder

`lado project repo add <id> <git-url> [--name NAME] [--branch BRANCH]` SHALL clone the URL
(its default branch, or `BRANCH`) into `<workspace>/projects/<id>/<name>`, where `<name>` is
`NAME` or the URL's repository name, with the progress and cancellation of `lado start
<git-url>`, and print `Added repository <name> to project <id>: <folder>` and `Start a
session in it: lado start --project <id> --repo <name>`.

#### Scenario: A clone from a local bare repository
- **WHEN** the project `shop` exists and the human runs `lado project repo add shop
  file:///srv/git/frontend.git`
- **THEN** `<ws>/projects/shop/frontend` is a clone of it, the output has `Added repository
  frontend to project shop: <ws>/projects/shop/frontend` and `Start a session in it: lado
  start --project shop --repo frontend`, and `lado project show shop` lists `frontend` with
  its branch and remote

#### Scenario: Another name and branch
- **WHEN** the human runs `lado project repo add shop https://github.com/shop/web --name
  site --branch dev`
- **THEN** the branch `dev` is cloned into `<ws>/projects/shop/site`

#### Scenario: A session in the new repository
- **WHEN** `frontend` was added and the human runs `lado start --project shop --repo
  frontend`
- **THEN** the session `shop-frontend` starts in `<ws>/projects/shop/frontend`

### Requirement: lado project repo add --new makes a repository from scratch

`lado project repo add <id> --new <name>` SHALL make `<workspace>/projects/<id>/<name>` a
git repository with one empty commit, as `lado start --new` does (git's author checked
first), print `Made <folder> a git repository with an empty first commit`, then the
`Added repository` and `Start a session in it` lines.

#### Scenario: From scratch
- **WHEN** the human runs `lado project repo add shop --new site`
- **THEN** `<ws>/projects/shop/site` is a git repository with one empty commit, and `lado
  project show shop` lists `site`

#### Scenario: No author
- **WHEN** git has no `user.name` and the human runs `lado project repo add shop --new
  site`
- **THEN** it exits 1 with the fresh start's text and hint, and no folder `site` is made

### Requirement: A repository's name follows the name rule and is free

A repository's name SHALL be 1 to 100 characters of Latin letters, digits, `.`, `_` and
`-`, not starting with `.` or `-`, else exit 1 with `lado: the repository name <name> is
not valid: Latin letters, digits, ., _ and -, not starting with . or -, at most 100
characters`. A name an entry of the project's folder has (any kind) SHALL exit 1 with
`lado: <folder> already exists in project <id>: choose another name with --name`.

#### Scenario: A taken name
- **WHEN** `<ws>/projects/shop/frontend` exists and the human runs `lado project repo add
  shop https://github.com/shop/frontend`
- **THEN** it exits 1 with `lado: <ws>/projects/shop/frontend already exists in project
  shop: choose another name with --name`, and nothing is cloned

#### Scenario: A name that is not valid
- **WHEN** the human runs `lado project repo add shop --new .hidden`
- **THEN** it exits 1 with the name rule's text, and nothing is made

#### Scenario: A URL that gives no name
- **WHEN** the URL's repository name breaks the name rule or is empty and no `--name` is
  given
- **THEN** it exits 1 with the name rule's text or the clone's `names no repository` text,
  and nothing is cloned

### Requirement: lado project repo add refuses what is no project to add to

`lado project repo add` SHALL exit 1, cloning and making nothing, for an unknown project
(`lado: unknown project "<id>"`), for a project whose folder is not found (`lado: the
folder of project <id> is not found: <folder>`) and for one whose folder is a link or not
at its place (the text of a removal's). It SHALL exit 2 with a usage error for
both a URL and `--new`, for neither, and for `--name` or `--branch` with `--new`.

#### Scenario: An unknown project
- **WHEN** the human runs `lado project repo add acme --new crm` and LADO has no project
  `acme`
- **THEN** it exits 1 with `lado: unknown project "acme"`

#### Scenario: Both ways at once
- **WHEN** the human runs `lado project repo add shop https://github.com/shop/web --new
  web`
- **THEN** it exits 2 with a usage error

### Requirement: A clone into a project is listed only once it is done

A clone into a project's folder SHALL go to a hidden temporary folder beside its target
and be renamed to `<name>` only once git succeeded; a failed or ended clone (Ctrl-C,
SIGTERM, a cancelled job) SHALL leave neither folder, so the project's repositories never
list it.

#### Scenario: Ctrl-C during the clone
- **WHEN** the human presses Ctrl-C while `lado project repo add shop <url>` clones
- **THEN** it exits 130 with `lado: clone cancelled`, `<ws>/projects/shop` holds neither
  `frontend` nor a temporary folder, and `lado project show shop` lists no `frontend`

#### Scenario: A clone that fails
- **WHEN** the URL names no repository git can read
- **THEN** it exits 1 with the clone's failure text, and nothing is left in the project's
  folder

### Requirement: lado project repo remove shows what goes and needs --yes

`lado project repo remove <id> <name>` SHALL print `Sessions to forget: <name> (<n> open
run[s]), …` for the project's stopped sessions in the repository (no line without any),
then `Unpushed work in <folder>:` with the repository's lines as `lado project delete`
gives them, its workers' worktrees included; without `--yes` it SHALL then exit 1,
changing nothing.

#### Scenario: Unpushed work in a worker's worktree
- **WHEN** the stopped session `shop-frontend` had a worker whose branch `lado/shop-frontend/dev-1`
  has a commit not pushed, and the human runs `lado project repo remove shop frontend`
- **THEN** the output has `Sessions to forget: shop-frontend`, `Unpushed work in
  <ws>/projects/shop/frontend:` and `  frontend: branch lado/shop-frontend/dev-1 not
  pushed`, then `lado: removing repository frontend of project shop deletes its folder
  <folder> with everything in it and forgets its 1 session; run again with --yes`; it
  exits 1, and the folder and the session stay

#### Scenario: Nothing unpushed
- **WHEN** the repository is clean and pushed and has no sessions
- **THEN** no list is printed, and without `--yes` it still refuses with `lado: removing
  repository frontend of project shop deletes its folder <folder> with everything in it;
  run again with --yes`

### Requirement: lado project repo remove refuses while a session in the repository runs

`lado project repo remove` SHALL exit 1, changing nothing, while any session whose
folder's real path is inside the repository's (one with a project or without) is not
stopped: `lado: repository <name> of project <id> has sessions not stopped: <names>; stop
them first with lado stop <name>`.

#### Scenario: A running session
- **WHEN** `shop-frontend` runs and the human runs `lado project repo remove shop frontend
  --yes`
- **THEN** it exits 1 with `lado: repository frontend of project shop has sessions not
  stopped: shop-frontend; stop them first with lado stop <name>`, and nothing is removed

### Requirement: lado project repo remove --yes removes the folder, then forgets its sessions

`lado project repo remove <id> <name> --yes` SHALL remove the repository's folder whole,
then forget each session it listed (as `lado forget --force` does), and print `Removed
repository <name> from project <id>`. The project's record, its other entries and its
other sessions SHALL stay. A folder not removed whole SHALL keep the sessions; a session
not forgotten SHALL be named.

#### Scenario: Confirmed
- **WHEN** the project `shop` has `frontend` and `backend`, `shop-frontend` is stopped,
  and the human runs `lado project repo remove shop frontend --yes`
- **THEN** `<ws>/projects/shop/frontend` and the session `shop-frontend` are gone, and
  `backend`, its sessions, the project's record and folder stay

### Requirement: lado project repo remove removes nothing outside the repository's folder

`lado project repo remove` SHALL remove only `<workspace>/projects/<id>/<name>`, whose real
path SHALL be a direct child of the project folder's real path, which SHALL be
`<workspace>/projects`'s real path joined with `<id>`, the folder no link, or else refuse,
removing nothing. A symbolic link of that name SHALL lose the link only, never its
target, with no session forgotten.

#### Scenario: A project folder that is a link to another project's
- **WHEN** `<ws>/projects/shop` is a symbolic link to `<ws>/projects/acme`, which holds the
  repository `x`, and the human runs `lado project repo remove shop x --yes`
- **THEN** it exits 1 with `lado: <ws>/projects/shop is a link or not where project shop's
  folder belongs: LADO adds and removes repositories only in the project's own folder`, and
  `acme`'s `x` and its sessions stay

#### Scenario: A link to a repository elsewhere
- **WHEN** `<ws>/projects/shop/docs` is a symbolic link to `/srv/docs` and the human runs
  `lado project repo remove shop docs --yes`
- **THEN** the link is gone, `/srv/docs` and its files stay, and the output is `Removed
  the link docs from project shop`

#### Scenario: Without --yes
- **WHEN** the human runs `lado project repo remove shop docs`
- **THEN** it exits 1 with `lado: removing docs of project shop deletes the link only,
  not its target /srv/docs; run again with --yes`

### Requirement: lado project repo remove refuses what is no repository

`lado project repo remove <id> <name>` SHALL exit 1, removing nothing, for an unknown
project, for a name no entry of the project's folder has (`lado: project <id> has no
repository <name>; its repositories: <names>`, or the `no repositories yet` text), and for
a folder that is no repository or a file (`lado: <name> in project <id> is not a
repository: LADO removes only repositories and links`).

#### Scenario: A plain folder
- **WHEN** `<ws>/projects/shop/notes` is a folder without git and the human runs `lado
  project repo remove shop notes --yes`
- **THEN** it exits 1 with `lado: notes in project shop is not a repository: LADO removes
  only repositories and links`, and `notes` stays

#### Scenario: An unknown name
- **WHEN** the project `shop` has `backend` and `frontend`, and the human runs `lado
  project repo remove shop web`
- **THEN** it exits 1 with `lado: project shop has no repository web; its repositories:
  backend, frontend`

### Requirement: The server adds a project's repository

`POST /api/clones` SHALL take `project` and `name` (with no `path`) and clone into the
project as `lado project repo add` does, as a job; `POST /api/projects/{id}/repos` with
`{name}` SHALL make one from scratch and answer the `ProjectRepo`. An unknown project SHALL
be 404, a refusal 400 with its reason, a `path` with `project` 400.

#### Scenario: A clone job into a project
- **WHEN** `POST /api/clones` has `{url: "file:///srv/git/frontend.git", project: "shop"}`
- **THEN** the job ends `done` with `path` `<ws>/projects/shop/frontend`, and `GET
  /api/projects/shop` lists `frontend`

#### Scenario: A taken name from scratch
- **WHEN** `<ws>/projects/shop/site` exists and `POST /api/projects/shop/repos` has
  `{name: "site"}`
- **THEN** it answers 400 with the taken name's text, and nothing is made

### Requirement: The server removes a project's repository

`GET /api/projects/{id}/repos/{name}/removal` SHALL give what removing it does: its kind
(`repository` or `link`), folder, link target, the sessions it forgets with their open runs
and the unpushed lines. `DELETE /api/projects/{id}/repos/{name}` SHALL remove it as `lado
project repo remove --yes` does and answer the project as `GET /api/projects/{id}`. An
unknown project or name SHALL be 404, a refusal 400.

#### Scenario: The preview
- **WHEN** the human's page asks `GET /api/projects/shop/repos/frontend/removal`
- **THEN** it gets `kind: "repository"`, the folder, `sessions` and `unpushed`, and
  nothing changes

#### Scenario: A running session
- **WHEN** `shop-frontend` runs and `DELETE /api/projects/shop/repos/frontend` is sent
- **THEN** it answers 400 with the `sessions not stopped` text, and nothing is removed

#### Scenario: An unknown name
- **WHEN** `DELETE /api/projects/shop/repos/web` is sent and `shop` has no entry `web`
- **THEN** it answers 404

### Requirement: A refused clone or fresh start into a new folder of a project offers to add it

When the target of a refused clone or fresh start is a folder that does not exist yet,
directly in a project's folder (`<ws>/projects/<id>/<name>`), with a name the name rule
takes, its hint SHALL be `Add a repository to the project:` and `lado project repo add <id>
<git-url>` (with ` --name <name>` when it is not the URL's name) for a clone, `lado project
repo add <id> --new <name>` for a fresh start and the server's folder check.

#### Scenario: A fresh start
- **WHEN** the human runs `lado start --new ~/workspace/projects/shop/web` and `shop` is a
  project without `web`
- **THEN** it exits 1 with the refusal naming the project and `lado: Add a repository to
  the project: lado project repo add shop --new web`, and nothing is made

#### Scenario: A clone under another name
- **WHEN** the human runs `lado start https://github.com/shop/web
  ~/workspace/projects/shop/site`
- **THEN** the hint is `lado project repo add shop https://github.com/shop/web --name site`

#### Scenario: A folder deeper down
- **WHEN** the target is `<ws>/projects/shop/frontend/sub`, `frontend` a repository
- **THEN** the hint is the session's, `lado start --project shop --repo frontend`

### Requirement: A project keeps plain variables in lado.db

LADO SHALL keep a project's plain variables in `lado.db`, one name and one value each, a
name at most once per project; deleting the project (`lado project delete --yes`, or its
record otherwise) SHALL remove its variables with it.

#### Scenario: Deleted with the project
- **WHEN** project `shop` has `BOARD_URL`, the human runs `lado project delete shop --yes`
  and then `lado project create shop`
- **THEN** `lado project show shop` prints `  variables: none`

### Requirement: lado project set sets a plain variable

`lado project set <id> NAME VALUE` SHALL store `VALUE` as the project's variable `NAME`,
over the old value when there is one, and print `Set <NAME> in project <id>.` and then
`Agents started from now on get it; running sessions of <id> keep the old environment
until restarted: <names>`, or `Agents started from now on get it.` when no session of the
project runs (a session runs when it is not stopped).

#### Scenario: Set while a session runs
- **WHEN** session `shop-frontend` of project `shop` runs and the human runs `lado project
  set shop BOARD_URL https://a`
- **THEN** it prints `Set BOARD_URL in project shop.` and `Agents started from now on get
  it; running sessions of shop keep the old environment until restarted: shop-frontend`

#### Scenario: Set again
- **WHEN** `shop` has `BOARD_URL=https://a` and the human runs `lado project set shop
  BOARD_URL https://b`
- **THEN** `lado project show shop` lists `BOARD_URL  https://b`

### Requirement: A project variable's value is a short text

A project variable's value SHALL be at most 64 KiB of UTF-8 text without NUL, else the
command exits 1 with `lado: the value of <NAME> is <why>` and stores nothing. An empty
value SHALL be a value.

#### Scenario: Too large
- **WHEN** the human sets a value of 70 000 bytes
- **THEN** it exits 1 with `lado: the value of <NAME> is larger than 64 KiB`, and nothing
  is stored

### Requirement: lado project unset removes a plain variable

`lado project unset <id> NAME` SHALL remove the project's plain variable or secret `NAME`
and print `Removed <NAME> from project <id>.` and then `Agents started from now on do not
get it; running sessions of <id> keep the old environment until restarted: <names>`, or
`Agents started from now on do not get it.` when no session of the project runs. A name
the project lacks SHALL exit 1 with `lado: project <id> has no variable or secret <NAME>;
its variables: <names>; its secrets: <names>`.

#### Scenario: Unset
- **WHEN** `shop` has `BOARD_URL` and no session of it runs, and the human runs `lado
  project unset shop BOARD_URL`
- **THEN** it prints `Removed BOARD_URL from project shop.` and `Agents started from now
  on do not get it.`, and `lado project show shop` prints `  variables: none`

#### Scenario: A name the project lacks
- **WHEN** `shop` has only `BOARD_URL` and the human runs `lado project unset shop MODEL_URL`
- **THEN** it exits 1 with `lado: project shop has no variable or secret MODEL_URL; its
  variables: BOARD_URL; its secrets: none`

#### Scenario: Unset a secret
- **WHEN** `shop` has the secret `GH_TOKEN` and the human runs `lado project unset shop
  GH_TOKEN`
- **THEN** `<LADO_HOME>/projects/shop/secrets/GH_TOKEN` is gone and it prints `Removed
  GH_TOKEN from project shop.`

### Requirement: A project variable's name is checked by one rule

LADO SHALL check a project variable's name by one rule in the core, for the CLI and the
server alike, and refuse a name that is no variable name (`[A-Za-z_][A-Za-z0-9_]*`) with
`the name <NAME> is not a variable name: Latin letters, digits and _, not starting with a
digit`, storing nothing.

#### Scenario: No variable name
- **WHEN** the human runs `lado project set shop A-B x`
- **THEN** it exits 1 with `lado: the name A-B is not a variable name: …`

### Requirement: A reserved name is no project variable

The rule SHALL refuse a reserved name with `<NAME> is reserved: LADO or the agent CLIs set
it`: each name the outside folder reserves (see `agent-variables`), any name starting
with `LADO_`, and each name LADO sets for an agent CLI (`CLAUDE_CONFIG_DIR`,
`CODEX_HOME`, the `OPENCODE_*` and `KILO_*` names of their launches).

#### Scenario: The shell's name
- **WHEN** the human runs `lado project set shop PATH /tmp`
- **THEN** it exits 1 with `lado: PATH is reserved: LADO or the agent CLIs set it`

#### Scenario: A reserved name
- **WHEN** the human runs `lado project set shop CLAUDE_CONFIG_DIR /tmp/c`
- **THEN** it exits 1 with `lado: CLAUDE_CONFIG_DIR is reserved: LADO or the agent CLIs set it`

#### Scenario: A provider's config
- **WHEN** the human runs `lado project set shop CODEX_HOME /tmp/c` or `OPENCODE_CONFIG_CONTENT {}`
- **THEN** it exits 1 naming the name as reserved

#### Scenario: LADO's own
- **WHEN** the human runs `lado project set shop LADO_HOME /tmp/h`
- **THEN** it exits 1 naming `LADO_HOME` as reserved

### Requirement: Every name a provider sets is reserved

Every name a provider sets in the environment of its agent's launch SHALL be in the
reserved list of project variables.

#### Scenario: A provider's launch
- **WHEN** any of the four providers builds an agent's launch
- **THEN** each name of its launch environment is refused as a project variable

### Requirement: A name that looks like a secret is no plain variable

The rule SHALL refuse a name with `TOKEN`, `KEY`, `SECRET` or `PASSWORD` in it, in any
case, as a plain variable, with `<NAME> looks like a secret (<word>): a plain variable
takes no name with TOKEN, KEY, SECRET or PASSWORD; set it as a secret with lado project
set <id> <NAME> --secret`.

#### Scenario: A secret's name
- **WHEN** the human runs `lado project set shop GH_TOKEN x`
- **THEN** it exits 1 with `lado: GH_TOKEN looks like a secret (TOKEN): …` and `shop` has no
  `GH_TOKEN`

#### Scenario: Lowercase is a secret's name too
- **WHEN** the human runs `lado project set shop yougile_api_key x`
- **THEN** it exits 1 naming `KEY`

### Requirement: lado project show lists the project's variables

`lado project show <id>` SHALL print, after the repositories, `  variables:` and one line
per variable, by name: `    <NAME>  <value>`, the names padded to one width; with none,
`  variables: none`. A value SHALL be shown on one line, each line break in it shown as
`\n`.

#### Scenario: Two variables
- **WHEN** `shop` has `MODEL_URL=http://localhost:11434` and `BOARD_URL=https://a`
- **THEN** `lado project show shop` ends with `  variables:`, `    BOARD_URL  https://a` and
  `    MODEL_URL  http://localhost:11434`

### Requirement: The server sets and removes a project's variables

`PUT /api/projects/{id}/variables/{name}` with `{value}` SHALL set a variable and `DELETE
/api/projects/{id}/variables/{name}` remove one, both with the token for changes
(`guard.changes`), by the same rules as the CLI, answering `{project, running}`: the
project as `GET /api/projects/{id}` gives it after the change and the names of its
sessions that run.

#### Scenario: Set through the API
- **WHEN** the UI sends `PUT /api/projects/shop/variables/BOARD_URL` with `{"value":
  "https://a"}` while `shop-frontend` runs
- **THEN** the answer's `project.variables` has `{name: "BOARD_URL", value: "https://a"}`
  and `running` is `["shop-frontend"]`

### Requirement: The server refuses a variable as the CLI does

An unknown project SHALL be 404, an unknown variable on `DELETE` 404, and a refused name
or value 400 with the refusal's text, nothing stored.

#### Scenario: A secret's name through the API
- **WHEN** the UI sends `PUT /api/projects/shop/variables/GH_TOKEN`
- **THEN** the answer is 400 with `GH_TOKEN looks like a secret (TOKEN): …` and nothing is
  stored

#### Scenario: An unknown project
- **WHEN** the UI sends `DELETE /api/projects/nope/variables/BOARD_URL`
- **THEN** the answer is 404

### Requirement: lado project set --secret stores a secret in its own file

`lado project set <id> NAME --secret` SHALL store the value as the project's secret
`NAME` in the file `<LADO_HOME>/projects/<id>/secrets/NAME`, the file's content being the
value, making the folders it lacks; each folder of `<LADO_HOME>/projects/<id>/secrets`
SHALL have the mode 700 and the file 600. It SHALL print `Set secret <NAME> in project
<id>.` and then the agents' line of `lado project set`. No value of a secret SHALL be
stored in `lado.db`.

#### Scenario: First secret
- **WHEN** project `shop` has no secret and the human runs `lado project set shop GH_TOKEN
  --secret` and types `ghp_1`
- **THEN** `<LADO_HOME>/projects/shop/secrets/GH_TOKEN` holds `ghp_1`, its mode is 600, the
  folders `projects/shop`, `shop` and `secrets` are 700, and it prints `Set secret GH_TOKEN
  in project shop.` and `Agents started from now on get it.`

### Requirement: The secret's value is asked without echo, or read from stdin

On a terminal, `lado project set <id> NAME --secret` SHALL ask `Value of <NAME> (not
shown): ` and read one line without echo. When stdin is no terminal it SHALL read the
whole of stdin as the value, one line break at its end (`\n` or `\r\n`) dropped.

#### Scenario: From a pipe
- **WHEN** the human runs `printf 'ghp_2\n' | lado project set shop GH_TOKEN --secret`
- **THEN** the secret `GH_TOKEN` of `shop` is `ghp_2`, and nothing is asked

#### Scenario: Several lines
- **WHEN** stdin holds `line1\nline2\n`
- **THEN** the secret is `line1\nline2`

#### Scenario: Two line breaks at the end
- **WHEN** stdin holds `x\n\n`
- **THEN** the agents of the project's sessions get `x\n`: one line break is dropped, no more

### Requirement: A secret's value is never given on the command line

`lado project set <id> NAME VALUE --secret` SHALL refuse, exit 1 with `lado: a secret's
value is never given on the command line (ps and the shell's history keep it); run lado
project set <id> <NAME> --secret and type it, or pipe it in`, and store nothing.

#### Scenario: The value as an argument
- **WHEN** the human runs `lado project set shop GH_TOKEN ghp_3 --secret`
- **THEN** it exits 1 with that text and `shop` keeps its secrets as they were

### Requirement: A secret is a non-empty short text

A secret's value SHALL be at most 64 KiB of UTF-8 text without NUL, by the rule of a
plain variable's value, and SHALL NOT be empty: an empty value SHALL exit 1 with `lado:
the secret <NAME> is empty; to remove it: lado project unset <id> <NAME>`, storing
nothing.

#### Scenario: Enter only
- **WHEN** the human runs `lado project set shop GH_TOKEN --secret` and presses Enter
- **THEN** it exits 1 with `lado: the secret GH_TOKEN is empty; to remove it: lado project
  unset shop GH_TOKEN`

#### Scenario: Too large
- **WHEN** stdin holds 70 000 bytes
- **THEN** it exits 1 with `lado: the value of GH_TOKEN is larger than 64 KiB`, and nothing
  is stored

### Requirement: Setting a secret again replaces it atomically

A secret set again SHALL replace the old value: the new value SHALL be written to a new
file in the same folder and renamed over the old one, so that a reader finds the old
value or the new one, never a part, and no temporary file stays, also when the write
fails. Secrets set at once by the CLI and the server SHALL not overwrite each other's
names.

#### Scenario: Replace
- **WHEN** `shop` has `GH_TOKEN=ghp_1` and the human sets it again to `ghp_4`
- **THEN** the file holds `ghp_4`, its mode is 600, and `secrets/` holds no other file

#### Scenario: A failed write
- **WHEN** writing the new value fails (the disk is full)
- **THEN** the command exits 1 naming the failure, the file still holds `ghp_1`, and no
  temporary file stays

### Requirement: A secret's name is checked by the variables' rule

A secret's name SHALL be checked by the rule of a project variable's name: a name that is
no variable name, or a reserved one, SHALL be refused with that rule's text. Any other
name SHALL be accepted, also one that does not look like a secret.

#### Scenario: A reserved name
- **WHEN** the human runs `printf x | lado project set shop LADO_HOME --secret`
- **THEN** it exits 1 with `lado: LADO_HOME is reserved: LADO or the agent CLIs set it`,
  and nothing is stored

#### Scenario: A name that does not look like a secret
- **WHEN** the human runs `printf 'postgres://u:p@db/x' | lado project set shop
  DATABASE_URL --secret`
- **THEN** `DATABASE_URL` is a secret of `shop`

### Requirement: A name is a plain variable or a secret, never both

A project SHALL hold one value per name. Setting a secret whose name is a plain variable
of the project SHALL exit 1 with `lado: <NAME> is a plain variable of <id>; remove it
first with lado project unset <id> <NAME>`, and setting a plain variable whose name is a
secret of the project SHALL exit 1 with `lado: <NAME> is a secret of <id>; remove it
first with lado project unset <id> <NAME>`; neither stores anything.

#### Scenario: A plain variable made a secret
- **WHEN** `shop` has the plain variable `DATABASE_URL` and the human runs `lado project
  set shop DATABASE_URL --secret`
- **THEN** it exits 1 with `lado: DATABASE_URL is a plain variable of shop; remove it first
  with lado project unset shop DATABASE_URL`, and the plain variable stays

#### Scenario: A secret set as a plain variable
- **WHEN** `shop` has the secret `DATABASE_URL` and the human runs `lado project set shop
  DATABASE_URL postgres://x`
- **THEN** it exits 1 with `lado: DATABASE_URL is a secret of shop; remove it first with
  lado project unset shop DATABASE_URL`

### Requirement: lado project show lists the project's secrets by name

`lado project show <id>` SHALL print, after the variables, `  secrets:` and one line per
secret, `    <NAME>`, by name; with none, `  secrets: none`. It SHALL list them without
opening any file: each file of the secrets folder that is no link, has a variable name and
is not reserved (a file the agents still cannot take, for its size or content, is named
by `lado doctor`).

#### Scenario: Two secrets
- **WHEN** `shop` has the secrets `YOUGILE_API_KEY` and `GH_TOKEN`
- **THEN** `lado project show shop` ends with `  secrets:`, `    GH_TOKEN` and
  `    YOUGILE_API_KEY`, and no value

### Requirement: No secret is written or removed through a symbolic link

Writing or removing a secret SHALL refuse, exit 1 with `lado: <path> is a symbolic link:
LADO writes and removes a project's secrets only in its own folders`, and touch nothing,
when `<LADO_HOME>/projects`, `<LADO_HOME>/projects/<id>`, its `secrets` or the secret's
file is a symbolic link; no link SHALL be followed on the way.

#### Scenario: secrets/ is a link
- **WHEN** `<LADO_HOME>/projects/shop/secrets` is a link to `/tmp/elsewhere` and the human
  sets a secret of `shop`
- **THEN** it exits 1 naming `<LADO_HOME>/projects/shop/secrets`, and `/tmp/elsewhere`
  holds no new file

#### Scenario: projects/ or the project's folder is a link
- **WHEN** `<LADO_HOME>/projects` or `<LADO_HOME>/projects/shop` is a link
- **THEN** setting and removing a secret of `shop` exit 1 naming that link

#### Scenario: The secret's file is a link
- **WHEN** `<LADO_HOME>/projects/shop/secrets/GH_TOKEN` is a link to `/tmp/t`, and the human
  sets or unsets `GH_TOKEN`
- **THEN** it exits 1 naming the file, and the link and `/tmp/t` stay as they were

### Requirement: The server sets and removes a project's secrets

`PUT /api/projects/{id}/secrets/{name}` with `{value}` SHALL set or replace a secret and
`DELETE /api/projects/{id}/secrets/{name}` remove one, both with the token for changes
(`guard.changes`), by the same rules as the CLI, answering `{project, running}` as the
variables' endpoints do. No endpoint SHALL return a secret's value.

#### Scenario: Set through the API
- **WHEN** the LADO manager sends `PUT /api/projects/shop/secrets/GH_TOKEN` with
  `{"value": "ghp_5"}`
- **THEN** the secret is stored, and the answer's `project.secrets` holds `"GH_TOKEN"` and
  no `ghp_5` anywhere

### Requirement: The server refuses a secret as the CLI does

An unknown project SHALL be 404, an unknown secret on `DELETE` 404, and a refused name or
value or a name held by a plain variable 400 with the refusal's text, nothing stored. A
request on these routes the server cannot read (422) SHALL answer without the input it
was given.

#### Scenario: An empty value through the API
- **WHEN** the UI sends `PUT /api/projects/shop/secrets/GH_TOKEN` with `{"value": ""}`
- **THEN** the answer is 400 with `the secret GH_TOKEN is empty; …`

#### Scenario: A body the server cannot read
- **WHEN** a client sends `PUT /api/projects/shop/secrets/GH_TOKEN` with `{"secret":
  "ghp_6"}`
- **THEN** the answer is 422 and holds no `ghp_6`

#### Scenario: A secret through the variables' route
- **WHEN** `shop` has the secret `GH_TOKEN` and the UI sends `DELETE
  /api/projects/shop/variables/GH_TOKEN`
- **THEN** the answer is 404 and the secret stays

### Requirement: Deleting a project removes its data folder

`lado project delete <id> --yes` SHALL remove `<LADO_HOME>/projects/<id>/` with its
secrets after the project folder and the sessions and before the record. When
`<LADO_HOME>/projects`, `<LADO_HOME>/projects/<id>`, its `secrets` or a file in it is a
symbolic link, it SHALL refuse before removing anything, exit 1 naming the link, and keep
the project.

#### Scenario: Delete, then create again
- **WHEN** `shop` has the secret `GH_TOKEN`, the human runs `lado project delete shop
  --yes` and then `lado project create shop`
- **THEN** `<LADO_HOME>/projects/shop` was removed, and `lado project show shop` prints
  `  secrets: none`

#### Scenario: A link in the data folder
- **WHEN** `<LADO_HOME>/projects/shop/secrets` is a link and the human runs `lado project
  delete shop --yes`
- **THEN** it exits 1 naming the link, and the project, its folder and the link's target
  stay
