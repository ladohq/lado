## ADDED Requirements

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
<names>`, or `lado: project <id> has no repositories yet: a repository is a git folder in
<folder>` when it has none.

#### Scenario: A name that is not there
- **WHEN** the project `shop` has `backend` and `frontend`, and the human runs
  `lado start --project shop --repo web`
- **THEN** it exits 1 with `lado: project shop has no repository web; its repositories:
  backend, frontend`

#### Scenario: A link
- **WHEN** `<ws>/projects/shop/docs` is a symbolic link to a repository and the human runs
  `lado start --project shop --repo docs`
- **THEN** it exits 1 naming the repositories of `shop`, and no session starts

#### Scenario: No repositories yet
- **WHEN** the folder of `acme` is empty and the human runs `lado start --project acme
  --repo crm`
- **THEN** it exits 1 with `lado: project acme has no repositories yet: a repository is a
  git folder in <ws>/projects/acme`

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
session in the project:` and the command `lado start --project <id> --repo <name>`; for
the project's folder itself the same text with the hint `See the project's
repositories:` and `lado project show <id>`.

#### Scenario: The project's folder itself
- **WHEN** the human runs `lado start ~/workspace/projects/shop`, a git repository
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
- **THEN** it exits 1 with the refusal naming the project `Shop` and `lado start --project
  shop --repo web`, and no folder `web` is made

#### Scenario: The server's clone
- **WHEN** `POST /api/clones` asks for a clone into `<ws>/projects/shop/web`
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
none, `  repositories: none`.

#### Scenario: Two repositories
- **WHEN** the project `shop` has `frontend` (branch `main`, remote
  `https://github.com/shop/frontend`) and `backend` (branch `dev`, no remote)
- **THEN** `lado project show shop` ends with `  repositories:`, `    backend   dev
  (no remote)` and `    frontend  main  https://github.com/shop/frontend`

### Requirement: The server gives a project with its repositories

`GET /api/projects/{id}` SHALL answer `{id, title, folder, found, repos}`, `repos` the
project's repositories as `{name, path, remote, branch}`, and 404 for an unknown id.

#### Scenario: A project
- **WHEN** the UI asks `GET /api/projects/shop`
- **THEN** the answer has `id: "shop"`, its title, its folder, `found: true` and its
  repositories as `lado project show` lists them

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

## MODIFIED Requirements

### Requirement: lado project list and show print projects with their folders

`lado project list` SHALL print one line per project, by id: the id, the title (the id
when none) and the folder, with `  (folder not found)` when the folder does not exist; with
no project it SHALL print `No projects. Make one with: lado project create <id>`.
`lado project show <id>` SHALL print `<id> "<title>"` (the id alone without a title), then
`  folder:  <folder>` (with the same mark), `  made:    <local date and time>` and the
project's repositories (lado project show lists the project's repositories); an unknown
id SHALL exit 1 with `lado: unknown project "<id>"`.

#### Scenario: Two projects
- **WHEN** LADO has `shop` titled `Shop` with its folder and `acme` without a title whose
  folder is gone
- **THEN** `lado project list` prints `acme  acme  <ws>/projects/acme  (folder not
  found)` and `shop  Shop  <ws>/projects/shop`

#### Scenario: A project whose folder is gone
- **WHEN** the folder of `acme` is gone and the human runs `lado project show acme`
- **THEN** it prints `  folder:  <ws>/projects/acme  (folder not found)` and
  `  repositories: none`

### Requirement: lado project delete shows unpushed work and needs --yes

`lado project delete <id>` SHALL refuse, exit 1, changing nothing, while any session of
the project is not stopped: `lado: project <id> has sessions not stopped: <names>; stop
them first with lado stop <name>`. Otherwise it SHALL list the stopped sessions it will
forget, `Sessions to forget: <name> (<n> open run[s]), …` (the count only for a session
with open runs; no line without sessions), then the unpushed work of the project folder:
for each git repository directly in it, and each worktree of one, its uncommitted changes
(untracked files included) and each local branch with no upstream or ahead of it. Without
`--yes` it SHALL then refuse, exit 1, changing nothing, with `lado: deleting project <id>
removes its folder <folder> with everything in it; run again with --yes`, or, with
sessions, `… with everything in it and forgets its <n> session[s]; run again with --yes`.

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

#### Scenario: A running session
- **WHEN** `shop-frontend` of project `shop` runs and the human runs `lado project delete
  shop --yes`
- **THEN** it exits 1 with `lado: project shop has sessions not stopped: shop-frontend;
  stop them first with lado stop <name>`, and the sessions, the folder and the record stay

#### Scenario: Stopped sessions
- **WHEN** `shop-frontend` (one open run) and `fix-login` of project `shop` are stopped and
  the human runs `lado project delete shop`
- **THEN** the output has `Sessions to forget: fix-login, shop-frontend (1 open run)` and
  ends with `… and forgets its 2 sessions; run again with --yes`; nothing changes

### Requirement: lado project delete --yes removes the folder, then the record

`lado project delete <id> --yes` SHALL remove the project folder whole, then forget each
of the project's sessions with its history, runs, gates and artifacts (as `lado forget
--force` does), then remove the record, and print `Deleted project <id>`. A project whose
folder is not found SHALL lose its sessions and record only. When the folder cannot be
removed whole, the sessions and the record SHALL stay and the command SHALL exit 1 naming
what stayed; when a session cannot be forgotten, the record SHALL stay and the command
SHALL exit 1 naming that session.

#### Scenario: Confirmed
- **WHEN** the human runs `lado project delete shop --yes`
- **THEN** `<ws>/projects/shop` and the record are gone, and `<ws>/projects` and the rest
  of the workspace are as they were

#### Scenario: The folder already gone
- **WHEN** the folder of `acme` is not found and the human runs `lado project delete acme
  --yes`
- **THEN** the record is gone and no folder is touched

#### Scenario: With stopped sessions
- **WHEN** `shop-frontend` of project `shop` is stopped and the human runs `lado project
  delete shop --yes`
- **THEN** the folder, the session `shop-frontend` with its history, and the record are
  gone, and `lado ls` no longer lists it
