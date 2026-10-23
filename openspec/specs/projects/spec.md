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
secrets, running, overrides, unused}`, `repos` the project's repositories as `{name, path,
remote, branch}`, `variables` its variables as `{name, value}` by name, `secrets` the names
of its secrets (as `lado project show` lists them, never a value), `running` the names of
its sessions that are not stopped, and 404 for an unknown id. The routes that change a
project SHALL answer it in this form.

#### Scenario: A project
- **WHEN** the UI asks `GET /api/projects/shop`
- **THEN** the answer has `id: "shop"`, its title, its folder, `found: true`, its
  repositories as `lado project show` lists them, its variables and its secrets' names

#### Scenario: Running sessions
- **WHEN** `shop-frontend` of `shop` runs and `shop-backend` is stopped
- **THEN** `running` is `["shop-frontend"]`

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

### Requirement: The server's project names what overrides and what its agents do not get

A project's `overrides` SHALL be the names of its variables, and of its secrets its agents
get, that the outside folder (`LADO_ENV_DIR`) gives too, sorted; its `unused` the entries
of its secrets folder its agents do not get as `{name, reason}` (`name` null for the folder
itself), as `lado doctor` names them. No field SHALL hold a value of a secret or of the
outside folder.

#### Scenario: A name the outside folder gives too
- **WHEN** `LADO_ENV_DIR` holds `YOUGILE_API_KEY` with `yk-out`, `shop` has the secret
  `YOUGILE_API_KEY` and the UI asks `GET /api/projects/shop`
- **THEN** `overrides` is `["YOUGILE_API_KEY"]` and the answer holds no `yk-out` and no
  value of the secret

#### Scenario: A secret file the agents do not get
- **WHEN** `<LADO_HOME>/projects/shop/secrets/SENTRY_DSN` has mode 644
- **THEN** `secrets` holds `SENTRY_DSN` and `unused` holds `{name: "SENTRY_DSN", reason:
  "readable or writable by others: chmod 600 it"}`, and `overrides` does not name it

### Requirement: The session's project links to the project's page

In the session's head and in a phone's session details, the project's title SHALL be a
link to the project's page `/projects/<id>`, its tooltip kept.

#### Scenario: From the head to the project
- **WHEN** the human clicks `Shop` in the head of `shop-frontend`
- **THEN** the Projects section opens at `/projects/shop`

### Requirement: The server lists the projects

`GET /api/projects` SHALL answer every project by id as `{id, title, folder, found, repos,
running}`: `repos` the number of its repositories read from the disk as `lado project show`
reads them (0 when its folder is not found), `running` the names of its sessions that are
not stopped. Without `lado.db` it SHALL answer an empty list and make no `lado.db`.

#### Scenario: Two projects
- **WHEN** `acme` has one repository and `shop` two, with `shop-frontend` running
- **THEN** the answer is `acme` with `repos: 1, running: []`, then `shop` with `repos: 2,
  running: ["shop-frontend"]`

#### Scenario: A folder not found
- **WHEN** the folder of `sandbox` was deleted by hand
- **THEN** its entry has `found: false` and `repos: 0`

### Requirement: The server makes a project

`POST /api/projects` with `{id, title}` (`title` optional) and the token for changes
(`guard.changes`) SHALL make the project as `lado project create` does and answer it as `GET
/api/projects/{id}` does. Each refusal of the core SHALL be 400 with the core's text, with
nothing made.

#### Scenario: Made
- **WHEN** the UI sends `POST /api/projects` with `{"id": "shop-eu", "title": "Shop EU"}`
- **THEN** the project `shop-eu` titled `Shop EU` and its folder `<workspace>/projects/shop-eu`
  exist, and the answer is the project with `repos: []`

#### Scenario: A folder of the name exists
- **WHEN** `<workspace>/projects/shop-eu` exists and is no project's
- **THEN** the answer is 400 with `<workspace>/projects/shop-eu already exists: LADO makes a
  project's folder itself; choose another id or move that folder away`, and no record is
  made

#### Scenario: Without the token
- **WHEN** a client sends `POST /api/projects` without the token for changes
- **THEN** it is refused as every change is, and nothing is made

### Requirement: The server suggests a project's id from a title

`GET /api/project-id?title=<text>` SHALL answer `{id, folder, problem}` and make nothing:
`id` the name a fresh start makes of the text, with `_` made `-`, cut to 40 characters and
trimmed of `-`, or null when nothing is left; `folder` the id's folder; `problem` the core's
refusal of `lado project create <id>` (`projects.check_new`), the reason there is no id, or
null. `?id=<id>` SHALL answer the same for that id as typed.

#### Scenario: A Cyrillic title
- **WHEN** the UI asks `GET /api/project-id?title=Магазин EU`
- **THEN** the answer is `{id: "magazin-eu", folder: "<workspace>/projects/magazin-eu",
  problem: null}`

#### Scenario: A taken id
- **WHEN** `shop` exists and the UI asks `GET /api/project-id?title=Shop`
- **THEN** `id` is `shop` and `problem` is `project shop exists`

#### Scenario: A typed id
- **WHEN** the UI asks `GET /api/project-id?id=Shop`
- **THEN** `problem` is the core's `the project id Shop is not valid: …`

#### Scenario: No Latin letter
- **WHEN** the UI asks `GET /api/project-id?title=日本`
- **THEN** `id` is null and `problem` is the fresh start's `the name needs a Latin letter or
  digit for its folder: type one`

### Requirement: The Projects section lists the projects

The Projects section (`/projects`) SHALL list the projects of `GET /api/projects` at the
left, as Sessions lists sessions: each row the title (the id without one), then `<id> · <N>
repositories · <N> running` (`no sessions running` when none runs) and the mark `folder not
found` when its folder is missing; a search by title and id; a `+` labelled `New project`. A
row SHALL open the project at `/projects/<id>` at the right; an unknown id SHALL show `No
project <id>`.

#### Scenario: The list
- **WHEN** the human opens Projects with `acme` (titled `ACME CRM`, one repository) and
  `shop` (titled `Shop`, two repositories, two sessions running)
- **THEN** the rows read `ACME CRM` `acme · 1 repository · no sessions running` and `Shop`
  `shop · 2 repositories · 2 running`

### Requirement: The project list follows the sessions

The project list SHALL be read anew when the section opens and when a session starts or
stops.

#### Scenario: A session starts
- **WHEN** the section is open and a session of `acme` starts
- **THEN** the row of `acme` reads `1 running` without a reload

### Requirement: The Projects section has an empty state

With no project the Projects section SHALL show `No projects yet`, a sentence on what a
project is, and one button `New project…`.

#### Scenario: No project
- **WHEN** the human opens Projects and LADO has no project
- **THEN** the section shows `No projects yet` and the button `New project…`

### Requirement: The Projects section takes the phone's screen in turns

On a phone the project list SHALL fill the screen and a project SHALL open in its place,
with a link `← All projects` above it.

#### Scenario: On a phone
- **WHEN** the human opens `/projects/shop` on a phone
- **THEN** only the project shows, with `← All projects` above it, which opens the list

### Requirement: The UI makes a project

`New project…` and the list's `+` SHALL open a dialog with Title (optional), Id, the
warning `⚠ Projects of one LADO are not isolated from each other. For clients that must not
mix, run a separate LADO.`, Cancel and `Create project`. `Create project` SHALL send `POST
/api/projects`, show a refusal under Id, and on success close the dialog and open
`/projects/<id>`.

#### Scenario: Made from the dialog
- **WHEN** the human types the title `Shop EU` and clicks `Create project`
- **THEN** the dialog closes and `/projects/shop-eu` shows `Shop EU`

### Requirement: New project's id follows the title until edited

Until the human edits Id, Id SHALL follow the title by `GET /api/project-id?title=`; an
edited Id SHALL be checked by `?id=`. Under Id the dialog SHALL show `Its folder: <workspace>/projects/<id>. The id never changes.`, or the
core's refusal of the id in its place, with `Create project` disabled while a refusal holds.

#### Scenario: The id follows the title
- **WHEN** the human types the title `Shop EU`
- **THEN** Id reads `shop-eu` and the note `Its folder: <workspace>/projects/shop-eu. The id
  never changes.`

#### Scenario: An edited id stays
- **WHEN** the human edits Id to `eu-shop` and then changes the title
- **THEN** Id stays `eu-shop`

#### Scenario: A refused id
- **WHEN** Id is `shop` and `shop` exists
- **THEN** `project shop exists` shows under Id and `Create project` is disabled

### Requirement: The project's page shows the project and what is not built yet

The project's page SHALL show the title (the id without one), the id, the line `<N>
repositories · <N> sessions running · folder <folder>` (`folder not found` after it when
it is missing), and the line `New session in this project… Not built yet: the
repositories on this page (adding, removing), renaming and deleting the project. Plan:
Projects, step S7. Meanwhile: lado project show <id>, lado project repo add <id>
<git-url>.` with its first words a button and the plan a link.

#### Scenario: The head of the page
- **WHEN** the human opens `/projects/shop`
- **THEN** the page shows `Shop`, `shop`, `2 repositories · 2 sessions running · folder
  <workspace>/projects/shop` and the not-built line naming `lado project show shop`

### Requirement: The project's page warns that projects are not isolated

Above the variables the project's page SHALL always show `⚠ Projects of one LADO are not
isolated from each other: an agent of one project can read another's variables and secrets.
For clients that must not mix, run a separate LADO.`

#### Scenario: Always there
- **WHEN** the human opens a project with no variables and no secrets
- **THEN** the warning shows

### Requirement: The project's page says which agents get new values

Under the warning the page SHALL always show, while sessions of the project run, `New values
reach the agents started after a change; running agents keep the environment they started
with. Running now: <sessions> — restart a session to give it the change.`, each session by
its title (its name without one) as a link to the session; with none, `New values reach the
agents started after a change. No session of this project is running.` The line SHALL follow
the sessions' starts and stops.

#### Scenario: Two sessions run
- **WHEN** `shop-frontend` (titled `Checkout redesign`) and `shop-backend` run
- **THEN** the line names `Checkout redesign` and `shop-backend` as links to their sessions

#### Scenario: A session stops
- **WHEN** the page is open and `shop-backend` stops
- **THEN** `shop-backend` leaves the line without a reload

### Requirement: The UI sets, edits and removes a project's plain variables

The page SHALL show a block `Variables` with each plain variable's name and value by name,
`Edit` (in place, `Save` and `Cancel`), `Remove`, and `+ Add variable` (a name and a value).
They SHALL go through `PUT` and `DELETE /api/projects/{id}/variables/{name}`; a refusal
SHALL show the core's text verbatim under the row, the fields kept.

#### Scenario: Add a variable
- **WHEN** the human adds `BOARD_URL` with `https://a`
- **THEN** the block lists `BOARD_URL` `https://a` by name

#### Scenario: Edit in place
- **WHEN** the human edits `BOARD_URL` to `https://b` and saves
- **THEN** the row shows `https://b`

### Requirement: A name that looks like a secret is offered as a secret

For the refusal of a plain variable whose name looks like a secret the UI SHALL offer `Add
<NAME> as a secret instead`, which closes the variable's form and opens the secret's form
with the name and an empty value.

#### Scenario: A name that looks like a secret
- **WHEN** the human adds the variable `STRIPE_KEY` with `sk_test_1`
- **THEN** `STRIPE_KEY looks like a secret (KEY): a plain variable takes no name with TOKEN,
  KEY, SECRET or PASSWORD; set it as a secret with lado project set shop STRIPE_KEY
  --secret` shows with `Add STRIPE_KEY as a secret instead`

#### Scenario: As a secret instead
- **WHEN** the human clicks `Add STRIPE_KEY as a secret instead`
- **THEN** the secret's form opens with the name `STRIPE_KEY` and an empty value, and
  `sk_test_1` is in no field

### Requirement: The UI sets, replaces and removes a project's secrets without showing them

The page SHALL show a block `Secrets` with each secret's name and `set · hidden`, `Replace`,
`Remove` and `+ Add secret`, through `PUT` and `DELETE /api/projects/{id}/secrets/{name}`; a
refusal (an empty value, a reserved or invalid name, a name held by a plain variable) SHALL
show the core's text verbatim under the row. No screen SHALL show a secret's value.

#### Scenario: Add a secret
- **WHEN** the human adds the secret `GH_TOKEN` with `ghp_1`
- **THEN** the block lists `GH_TOKEN` `set · hidden` and the value field is empty

### Requirement: A secret's value is typed into a hidden field emptied after use

A secret's value SHALL be typed into a hidden field (`type="password"`, no autocomplete)
that is empty after a save, after Cancel and after the page is left; Replace SHALL open an
empty field with the placeholder `New value (the old one is not shown)`.

#### Scenario: Replace
- **WHEN** the human replaces `GH_TOKEN` with `ghp_2`
- **THEN** agents started after it get `ghp_2`, and the field is closed and empty

#### Scenario: A name held by a plain variable
- **WHEN** `BOARD_URL` is a plain variable and the human adds the secret `BOARD_URL`
- **THEN** `BOARD_URL is a plain variable of shop; remove it first with lado project unset
  shop BOARD_URL` shows

### Requirement: A secret's value leaves the browser only in the body of its request

The UI SHALL send a secret's value only as the JSON body of one `PUT
/api/projects/{id}/secrets/{name}`: never in a URL, a query or a header, never in
`localStorage`, `sessionStorage` or a cookie, never in a field the browser keeps in its form
history; the server SHALL write it in no log. Nothing the UI or the change feed receives
SHALL hold it.

#### Scenario: After a replace
- **WHEN** the human replaces `GH_TOKEN` with a unique value in the browser
- **THEN** the value is in no URL the page visited, in neither storage of the page, and in no
  file under `LADO_HOME` but the secret's own

### Requirement: The project's page marks a name that overrides the outside folder

A variable or secret whose name is in `overrides` SHALL carry the mark `overrides outside
value` with the tooltip `The outside folder (LADO_ENV_DIR) also gives <NAME>. This
project's sessions get the project's value; its outside value is not shown.`

#### Scenario: An overridden key
- **WHEN** `LADO_ENV_DIR` gives `YOUGILE_API_KEY` and `shop` has it as a secret
- **THEN** its row carries `overrides outside value`, and no outside value is on the page

### Requirement: The project's page names a secret file its agents do not get

A secret in `unused` SHALL show `⚠ Agents do not get it: <reason>` in its row, keeping
Replace and Remove; an entry of `unused` that is no secret's name (a link, a bad name) SHALL
show as `⚠ <name>: agents do not get it: <reason>` under the block, and one for the folder
as `⚠ The secrets folder is not used: <reason>`.

#### Scenario: A loose file
- **WHEN** `SENTRY_DSN`'s file has mode 644
- **THEN** its row shows `⚠ Agents do not get it: readable or writable by others: chmod 600
  it`

#### Scenario: A replace mends it
- **WHEN** the human replaces `SENTRY_DSN`
- **THEN** its file has mode 600 and the row shows no warning

### Requirement: Removing a variable or a secret asks in its row

`Remove` SHALL turn the row into `Remove <NAME>? Remove · Cancel`; only the second `Remove`
SHALL send the `DELETE`.

#### Scenario: Cancelled
- **WHEN** the human clicks `Remove` on `GH_TOKEN`, then `Cancel`
- **THEN** no request is sent and `GH_TOKEN` stays

### Requirement: The project's page opens New session on its project

The button `New session in this project…` of the project's page SHALL open the New session
window in Project with this project chosen.

#### Scenario: A new session from the page
- **WHEN** the human clicks `New session in this project…` on `/projects/shop`
- **THEN** the New session window opens in Project with `Shop` chosen

### Requirement: The server starts a session in a project's repository

`POST /api/sessions` with `where: {kind: "project", project: <id>, repo: <name>}` and the
change token SHALL start a new session as `lado start --project <id> --repo <name>` does,
by the same core function (`runtime.start_session` with `project` and `repo_name`, no
path), never a resume: its folder the repository, its default name `<id>-<name>`, its
project `<id>`.

#### Scenario: A start in a project
- **WHEN** the UI posts `where: {kind: "project", project: "shop", repo: "frontend"}`
- **THEN** the session `shop-frontend` starts in `<workspace>/projects/shop/frontend` with
  project `shop`, and the answer is `Started` with `session.project: "shop"`

### Requirement: The server refuses a start in a project as the core does

A start of kind `project` SHALL answer 404 with the core's text for an unknown project or
repository, 409 `Taken` for a name a session has, as for a folder, and 400 with the core's
text for any other refusal of the core. `where` of kind `project` with a `path` or without
`project` or `repo`, and of kind `folder` or `scratch` with `project` or `repo`, SHALL be
400. Nothing SHALL start on a refusal.

#### Scenario: An unknown repository
- **WHEN** the UI posts `where: {kind: "project", project: "shop", repo: "docs"}` and
  `shop` has `frontend` and `backend`
- **THEN** the answer is 404 with `project shop has no repository docs; its repositories:
  backend, frontend`, and nothing starts

#### Scenario: A taken name
- **WHEN** a stopped session `shop-frontend` exists and the UI posts the same start
- **THEN** the answer is 409 `Taken` with its status and folder

#### Scenario: A path with a project
- **WHEN** the UI posts `where: {kind: "project", project: "shop", repo: "frontend",
  path: "/tmp/x"}`
- **THEN** the answer is 400, and nothing starts

### Requirement: The server tells the New session window what a start in a project takes

`GET /api/project-launch` with the optional `project` and `repo` SHALL answer, making
nothing, `projects` (as `GET /api/projects` gives them, sorted by title, the id without
one, case aside; none without `lado.db`), the chosen `project`, its `repos`, the chosen
`repo`, and for that repository `default_name` (`<project>-<repo>` as the core makes it),
`name_state`, `provider` (as the folder check gives it) and `last`, the repository's latest
started session of this project or null.

#### Scenario: The window opens on Project
- **WHEN** the latest started session in a project is `shop-backend` of `shop`, and the UI
  asks `GET /api/project-launch`
- **THEN** `project` is `shop`, `repo` is `backend`, `default_name` is `shop-backend` and
  `last` is that session

### Requirement: The Project way chooses the project and repository last used

`GET /api/project-launch` SHALL choose as `project` the id asked when it is a project, else
that of the latest started session in a project whose folder is found, else the first of
`projects` whose folder is found, else the first, null without projects; and as `repo` the name asked when it is one of the
project's repositories, else that of the project's latest started session when it is still
one, else the first, null when there are none.

#### Scenario: Another project chosen
- **WHEN** the UI asks `GET /api/project-launch?project=acme` and `acme` has no session but
  the repository `crm`
- **THEN** `project` is `acme`, `repo` is `crm`, `name_state` is `free` and `last` is null

#### Scenario: An empty project
- **WHEN** the UI asks for a project with no repository
- **THEN** `repos` is empty and `repo`, `default_name` and `last` are null

### Requirement: A name held outside the project is taken elsewhere

`name_state` of `GET /api/project-launch` SHALL be the folder check's, but a session of the
default name that is in another project or in none SHALL count as `taken_elsewhere`.

#### Scenario: A name of another project
- **WHEN** a session `shop-frontend` exists that is not in `shop`
- **THEN** `name_state` for `shop` and `frontend` is `taken_elsewhere`

### Requirement: The folder check names the project a folder is in

`GET /api/folders` for a path inside a project's folder (by its real path, while
`projects/` is LADO's) SHALL carry `project: {id, title, repo}`, `repo` the project's
repository the path is in or null; for any other path, a foreign folder of `projects/`
included, `project` SHALL be null. The refusal's text and hint SHALL stay the core's.

#### Scenario: A project's repository
- **WHEN** the UI checks `<workspace>/projects/shop/frontend/src`
- **THEN** `ok` is false, `problem_kind` is `in_project` and `project` is `{id: "shop",
  title: "Shop", repo: "frontend"}`

#### Scenario: The project's folder itself
- **WHEN** the UI checks `<workspace>/projects/shop`
- **THEN** `project` is `{id: "shop", title: "Shop", repo: null}`

### Requirement: The New session window starts a session in a project

The New session window SHALL have the source **Project** last in its switch. Project SHALL
show a select of the projects (one whose folder is not found off, marked `folder not
found`), the chosen project's line `<N> repositories · <N> sessions running · folder
<folder>`, and its repositories, each with its name, branch and remote, one chosen. Its
start button SHALL start with `where: {kind: "project", project, repo}` and open the
session's page. The window's first source SHALL stay as before.

#### Scenario: Start in a project's repository
- **WHEN** the human picks Project, `Shop`, then `frontend`, and clicks `Start in Shop`
- **THEN** the session `shop-frontend` starts in the project and its page opens, its head
  showing `project Shop`

### Requirement: The Project way's start names the project

In Project the start button SHALL read `Start in <title>` (the id without one) of the
project chosen, so the human sees which project's keys the session gets before it starts;
the other ways keep `Start session`.

#### Scenario: Another project than the one last used
- **WHEN** the window opens on `Shop`, the project last used, and the human picks `ACME CRM`
  and its repository `crm`
- **THEN** the button reads `Start in ACME CRM`, and the session `acme-crm` starts in the
  project `acme`, as its head and `lado ls` show

### Requirement: The Project way only chooses a repository, from a list always shown

Project's list of repositories SHALL show even with one item, and stay with its focus while
the server answers a new choice, the start off until it has. The window SHALL only choose
one of the project's repositories: it SHALL NOT add, clone or make one.

#### Scenario: The list with one repository
- **WHEN** the chosen project has the one repository `crm`
- **THEN** the list shows `crm`, chosen

### Requirement: The Project way takes the session's settings as Folder does

In Project, Name SHALL be the default name until the human edits it, with the folder
check's notes for a taken name; Kits and Permission mode SHALL come from the repository's
last session, as Folder takes them from a folder's, and Provider from the server's
suggestion. A refused start SHALL show the core's text, with `Resume it` or `Open it` as
for a folder, only when the session that has the name is of this project.

#### Scenario: A taken name
- **WHEN** a stopped `shop-frontend` of this repository exists and the human clicks `Start
  in Shop`
- **THEN** the window shows `session "shop-frontend" exists already (stopped, in
  <workspace>/projects/shop/frontend); resume it, or give the new session another name`
  and `Resume it`, also when the workspace's path goes through a link

### Requirement: The Project way sends the human to the project when nothing can be chosen

In Project, a project with no repository SHALL show in the list's place `No repositories
yet. Add one on the project's page:` with a link `Open <title>` to `/projects/<id>`, and
its start button SHALL be off. With no project the field SHALL show `No projects yet. A project
keeps its repositories and the variables its sessions get.` with a link `Make one in
Projects` to `/projects`. Each link SHALL close the window.

#### Scenario: An empty project
- **WHEN** the human picks the project `ACME CRM` without repositories
- **THEN** the field shows the line with `Open ACME CRM`, and `Start in ACME CRM` is off

#### Scenario: No project
- **WHEN** LADO has no project and the human picks Project
- **THEN** the field shows `No projects yet…` with `Make one in Projects`

### Requirement: Folder's refusal inside a project leads to the project

When Folder's check refuses a folder with `project` set, the refusal SHALL show, above the
core's hint and its command, the button `Start in the project <title>` when `project.repo`
is set, which switches the window to Project with that project and repository chosen, else
the button `Open the project <title>`, which closes the window and opens `/projects/<id>`.
The refusals of Clone into and Create in SHALL stay as they are.

#### Scenario: A project's repository in Folder
- **WHEN** the human types `<workspace>/projects/shop/frontend` in Folder and clicks `Start
  in the project Shop`
- **THEN** the window shows Project with `Shop` and `frontend` chosen and the name
  `shop-frontend`

#### Scenario: A folder of a project that is no repository
- **WHEN** the human types `<workspace>/projects/shop/notes`, a folder without git
- **THEN** the refusal offers `Open the project Shop`, which opens `/projects/shop`

### Requirement: The switch of the New session window fits a phone

On a screen of at most 760 px the switch of the New session window SHALL show its four
buttons as a grid of two columns within the window, none cut off.

#### Scenario: A phone
- **WHEN** the human opens New session on a 390 px screen
- **THEN** From scratch and Folder are on the first row, Clone from URL and Project on the
  second, all inside the window
