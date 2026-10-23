## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Agents cannot change projects

`lado project create`, `rename`, `delete`, `repo add` and `repo remove` SHALL refuse, exit
1 with `lado: lado project <command> is for the human; agent "<agent>" cannot use it` and
change nothing, when `LADO_AGENT` is set (every agent of LADO has it). `list` and `show`
SHALL work for agents. LADO SHALL offer no MCP tool that makes, changes or deletes a
project or its repositories.

#### Scenario: From an agent
- **WHEN** a worker runs `lado project create shop` in its shell
- **THEN** it exits 1 with that text, and no project or folder is made

#### Scenario: Adding a repository from an agent
- **WHEN** a worker runs `lado project repo add shop --new site` in its shell
- **THEN** it exits 1 with `lado: lado project repo add is for the human; agent
  "<agent>" cannot use it`, and no folder `site` is made

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
