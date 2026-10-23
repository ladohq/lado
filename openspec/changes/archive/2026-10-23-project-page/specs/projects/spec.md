## MODIFIED Requirements

### Requirement: The project's page shows the project and what is not built yet

The project's page SHALL show the title (the id without one) with its Rename, the id, the
button `New session…`, the line `<N> repositories · <N> sessions running · folder
<folder>` (`folder not found` after it when it is missing), and, at its bottom, the line
`Deleting the project: not built yet (Projects, step S7b). Meanwhile: lado project delete
<id>.`

#### Scenario: The head of the page
- **WHEN** the human opens `/projects/shop`
- **THEN** the page shows `Shop`, `shop`, `New session…`, `2 repositories · 2 sessions
  running · folder <workspace>/projects/shop`, and the line naming `lado project delete
  shop` at its bottom

### Requirement: The project's page opens New session on its project

The button `New session…` in the head of the project's page SHALL open the New session
window in Project with this project chosen.

#### Scenario: A new session from the page
- **WHEN** the human clicks `New session…` on `/projects/shop`
- **THEN** the New session window opens in Project with `Shop` chosen

### Requirement: Folder's refusal inside a project leads to the project

When Folder's check refuses a folder with `project` set, the refusal SHALL show, above the
core's hint and its command, the button `Start in the project <title>` when `project.repo`
is set, which switches the window to Project with that project and repository chosen, else
the button `Open the project <title>`, which closes the window and opens `/projects/<id>`.
The refusals of Clone into and Create in inside a project SHALL show `Open the project
<title>` the same way.

#### Scenario: A project's repository in Folder
- **WHEN** the human types `<workspace>/projects/shop/frontend` in Folder and clicks `Start
  in the project Shop`
- **THEN** the window shows Project with `Shop` and `frontend` chosen and the name
  `shop-frontend`

#### Scenario: A folder of a project that is no repository
- **WHEN** the human types `<workspace>/projects/shop/notes`, a folder without git
- **THEN** the refusal offers `Open the project Shop`, which opens `/projects/shop`

#### Scenario: Clone into a new folder of a project
- **WHEN** the human chooses Clone from URL and types `<workspace>/projects/shop/admin` in
  Clone into
- **THEN** the refusal names the project, offers `Open the project Shop` above the hint
  `lado project repo add shop <git-url>`, and the button closes the window and opens
  `/projects/shop`

#### Scenario: Create in a new folder of a project
- **WHEN** the human chooses From scratch with Create in `<workspace>/projects/shop`
- **THEN** the refusal offers `Open the project Shop`

### Requirement: New project's id follows the title until edited

Until the human edits Id, Id SHALL follow the title by `GET /api/project-id?title=`; an
edited Id SHALL be checked by `?id=`. Under Id the dialog SHALL show `Its folder: <workspace>/projects/<id>. The id never changes.`, or the
core's refusal of the id in its place, with `Create project` disabled while a refusal holds.
When the title is not empty and gives no id, Id stays empty and the note SHALL say `The
title gives no id: type one.`

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

#### Scenario: A title that gives no id
- **WHEN** the human types the title `!!!` and leaves Id alone
- **THEN** Id stays empty, `The title gives no id: type one.` shows under it, and `Create
  project` is disabled

### Requirement: lado project repo remove shows what goes and needs --yes

`lado project repo remove <id> <name>` SHALL print `Sessions to forget: <name> (<n> open
run[s]), …` for the stopped sessions it forgets (no line without any), one without a
project marked ` (no project)`; then `Unpushed work in <folder>:` with the repository's
lines as `lado project delete` gives them, its workers' worktrees included; without
`--yes` it SHALL then exit 1, changing nothing.

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

#### Scenario: A session from before projects
- **WHEN** the stopped session `old-backend` has no project and was started in
  `<ws>/projects/shop/backend`, and the human runs `lado project repo remove shop backend`
- **THEN** the output has `Sessions to forget: old-backend (no project)` and ends with `…
  and forgets its 1 session; run again with --yes`; nothing changes

### Requirement: The server removes a project's repository

`GET /api/projects/{id}/repos/{name}/removal` SHALL give what removing it does: its kind
(`repository` or `link`), folder, link target, the sessions it forgets with their open runs
and their project (null for one without a project) and the unpushed lines. `DELETE
/api/projects/{id}/repos/{name}` SHALL remove it as `lado project repo remove --yes` does
and answer the project as `GET /api/projects/{id}`. An unknown project or name SHALL be
404, a refusal 400.

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

#### Scenario: A session without a project in the preview
- **WHEN** the stopped session `old-backend` without a project was started in
  `<ws>/projects/shop/backend` and the page asks its removal
- **THEN** `sessions` holds `{name: "old-backend", open_runs: 0, project: null}`

### Requirement: lado project delete shows unpushed work and needs --yes

`lado project delete <id>` SHALL list the project's sessions it will forget, `Sessions to
forget: <name> (<n> open run[s]), …` (no line without sessions), then the unpushed work of
the project folder (itself when a repository's root, each repository directly in it, each
worktree of one, once): its uncommitted changes (untracked files included) and each local
branch with no upstream or ahead of it. Without `--yes` it SHALL then refuse, exit 1, changing nothing.

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

#### Scenario: The project folder is a repository
- **WHEN** `<ws>/projects/shop` itself is a git repository with a commit on a branch with
  no upstream, and the human runs `lado project delete shop`
- **THEN** the list has `  the project's folder: …; branch main not pushed`

#### Scenario: A worktree inside the project folder
- **WHEN** `<ws>/projects/shop/frontend-fix` is a worktree of `<ws>/projects/shop/frontend`
  with uncommitted changes
- **THEN** the list has the line `  frontend (worktree frontend-fix): uncommitted changes`
  once and no line of its own for `frontend-fix`

## ADDED Requirements

### Requirement: The unpushed check names commits on a detached HEAD and stashes

The unpushed lines of a repository (`lado project delete`, `lado project repo remove` and
their API previews) SHALL also name, in the repository's line, `detached HEAD with <n>
commit[s] on no branch` when its HEAD is detached and `<n>` commits reachable from it are
on no local branch and no remote-tracking branch, and `<n> stash[es]` when it has stashes;
and for a worktree whose HEAD is detached the same `detached HEAD …` finding in the
worktree's line.

#### Scenario: Commits on a detached HEAD
- **WHEN** the repository `notes` has its HEAD detached with two commits no branch holds,
  and the human runs `lado project repo remove shop notes`
- **THEN** the list has `  notes: detached HEAD with 2 commits on no branch`

#### Scenario: A stash
- **WHEN** the repository `backend` is clean and pushed but has one stash
- **THEN** the list has `  backend: 1 stash`

#### Scenario: A detached HEAD on a pushed commit
- **WHEN** the HEAD of `frontend` is detached on a commit `origin/main` holds
- **THEN** no line names `frontend`

### Requirement: Removing a repository forgets its sessions without a project

`lado project repo remove <id> <name> --yes` and `DELETE /api/projects/{id}/repos/{name}`
SHALL forget, after removing the folder, the stopped sessions without a project whose
folder's real path is inside the repository's (sessions from before projects), as they
forget the project's own; a session of another project is never matched by its path.

#### Scenario: Confirmed with a session from before projects
- **WHEN** `old-backend` has no project, was started in `<ws>/projects/shop/backend` and is
  stopped, and the human runs `lado project repo remove shop backend --yes`
- **THEN** the folder and the session `old-backend` are gone

### Requirement: The server renames a project

`PATCH /api/projects/{id}` with `{title}` and the change token SHALL store the title as
`lado project rename <id> <title>` does, through the same core function, and answer the
project as `GET /api/projects/{id}`; a null or empty title SHALL clear it. An unknown
project SHALL be 404, a title the core refuses 400 with its text; the id and the folder
SHALL stay.

#### Scenario: A new title
- **WHEN** `PATCH /api/projects/shop` has `{title: "Shop EU"}`
- **THEN** it answers the project with `title: "Shop EU"`, and `lado project show shop`
  prints `shop "Shop EU"`

#### Scenario: Cleared
- **WHEN** `PATCH /api/projects/shop` has `{title: ""}`
- **THEN** the answer's `title` is null

#### Scenario: Refused
- **WHEN** the title is longer than the title rule allows, or the project is unknown
- **THEN** it answers 400 with the core's text, or 404, and nothing changes

### Requirement: The project's page renames the project in place

The title in the head of the project's page and its `Rename` button SHALL open a field in
the title's place holding the title; Enter or leaving the field SHALL save it through
`PATCH /api/projects/{id}`, Esc SHALL cancel, an empty field SHALL clear the title (the id
then shows), and the same text as stored SHALL send nothing. A refusal SHALL show under the
field verbatim, the field kept open with the text. After a save the head and the project
list SHALL show the new title.

#### Scenario: Renamed
- **WHEN** the human clicks `Rename` on `/projects/shop`, types `Shop EU` and presses Enter
- **THEN** the head and the list's row read `Shop EU`, and the session `shop-frontend`'s
  head reads `project Shop EU` when it is next opened

#### Scenario: Tab takes the id
- **WHEN** the project `shop` has no title, the human clicks `Rename` and presses Tab
- **THEN** the field holds `shop`, nothing is sent, and the focus stays in the field

#### Scenario: Cancelled
- **WHEN** the human types in the field and presses Esc
- **THEN** the title stays as it was and nothing is sent

### Requirement: Tab takes the project's id into the title field

The project's title field SHALL offer the project's id as a suggestion as the session's
title field offers the session's name: shown grey while the text is a proper start of the
id with the caret at its end, taken by Tab or → without modifiers, the focus kept and
nothing sent; the hint SHALL read `Tab takes the id · Enter to save · Esc to cancel` while
it shows, else `Enter to save · Esc to cancel`. A project with a title SHALL open the field
with the title selected and no suggestion.

#### Scenario: A start of the id
- **WHEN** the project `shop-eu` has no title and the human types `sh` in its field
- **THEN** `op-eu` shows grey after `sh`, the hint names Tab, and → makes the text `shop-eu`

### Requirement: The project's page lists its repositories

The project's page SHALL have a block `Repositories` listing the project's repositories of
`GET /api/projects/{id}` by name, each with `branch <branch>` (`detached HEAD` without one)
and its remote (`no remote` without one), and the buttons `Start session` and `Delete`;
`+ Add repository` in the block's head. With none the block SHALL say `No repositories
yet. …` with a primary `+ Add repository`. On a phone a row's buttons go under its name.

#### Scenario: The list
- **WHEN** `shop` has `frontend` on `main` with remote `github.com/shop/frontend` and
  `notes` on a detached HEAD without a remote
- **THEN** the block shows `frontend` with `branch main · github.com/shop/frontend` and
  `notes` with `detached HEAD · no remote`, each with `Start session` and `Delete`

#### Scenario: An empty project
- **WHEN** the human opens a project with no repository
- **THEN** the block says `No repositories yet…` and shows `+ Add repository`

### Requirement: Start session opens New session on the repository

`Start session` on a repository's row SHALL open the New session window in Project with the
project and that repository chosen (`GET /api/project-launch?project=<id>&repo=<name>`).

#### Scenario: Started from the row
- **WHEN** the human clicks `Start session` on `backend` of `shop` and then `Start in Shop`
- **THEN** a session of project `shop` starts in `<ws>/projects/shop/backend`

### Requirement: The project's page lists its sessions

The project's page SHALL have a block `Sessions` listing the sessions of the change feed
whose project is the page's, running ones first (the latest started first), then stopped
ones (the latest stopped first): each its
status mark, its title (its name without one) as a link to the session, its name beside a
title, the name of its folder (the repository), and `running <time>` or `stopped <time>
ago`. With none it SHALL say `No sessions in this project yet.`

#### Scenario: Running and stopped
- **WHEN** `shop-frontend` (titled `Checkout redesign`) runs and `shop-backend` is stopped
- **THEN** the block lists `Checkout redesign` with `shop-frontend · frontend` first, then
  `shop-backend` with `backend`, each a link

#### Scenario: A session starts
- **WHEN** the page is open and a session of the project starts
- **THEN** it shows in the block without a reload

### Requirement: The UI adds a repository by a clone or from scratch

`+ Add repository` SHALL open the dialog `Add a repository to <title>` with the switch
`Clone from URL | From scratch`. From scratch SHALL take Name and send `POST
/api/projects/{id}/repos`; Clone from URL is the requirement on adding by a clone. A
refusal SHALL show verbatim under its field, the fields kept. On success the dialog SHALL
close and the page show the new repository.

#### Scenario: From scratch
- **WHEN** the human adds `web` from scratch to `shop`
- **THEN** `<ws>/projects/shop/web` is a repository with one empty commit, the dialog
  closes and the row `web` shows

#### Scenario: A taken name
- **WHEN** the human adds `notes` from scratch and `<ws>/projects/shop/notes` exists
- **THEN** the core's text `… already exists in project shop …` shows under Name, the dialog
  stays and nothing is made

### Requirement: Add repository clones a URL into the project

Clone from URL SHALL take Git URL, Name and Branch. The remote's branches SHALL be listed by
`POST /api/remote-branches` as in New session, whose answer gives the URL's repository name
(`repo_name`), which Name takes until the human edits it. `Clone` SHALL be on once the
branches are listed and Name is not empty, and send `POST /api/clones` with `url`,
`project`, `name` and `branch`.

#### Scenario: A clone
- **WHEN** the human types a reachable URL whose repository is `admin` and clicks `Clone`
- **THEN** Name reads `admin`, the clone goes to `<ws>/projects/shop/admin`, the dialog
  closes and the row `admin` shows with the branch chosen

### Requirement: Add repository shows a running clone and can cancel it

While its clone runs the dialog SHALL show git's progress as the New session window does,
keep its fields off, and not close by Esc, Cancel or ×; `Cancel clone` SHALL send `DELETE
/api/clones/{id}`, after which no folder is left and the dialog says `the clone was
cancelled` with its fields on again. A page that goes away during the clone SHALL cancel
it with the beacon. A failed clone SHALL show its text and hint, the dialog kept.

#### Scenario: Cancelled
- **WHEN** a clone runs and the human clicks `Cancel clone`
- **THEN** the dialog says `the clone was cancelled`, and `<ws>/projects/shop/<name>` does
  not exist

### Requirement: The UI deletes a repository after showing what goes

`Delete` on a repository's row SHALL open the dialog `Delete repository <name>?` from `GET
/api/projects/{id}/repos/{name}/removal`: its folder, under `Work that is not on the
remote` each unpushed line, under `Sessions that are forgotten` each session (one without a
project marked so). With unpushed lines `Delete repository` SHALL stay off until the
repository's name is typed; then, or with none, it SHALL send `DELETE` and close the
dialog. A refusal SHALL show verbatim with only `Close`.

#### Scenario: Unpushed work shown
- **WHEN** `backend` has the branch `feature/checkout` not pushed and the stopped session
  `shop-backend`, and the human clicks `Delete` on it
- **THEN** the dialog shows `backend: branch feature/checkout not pushed` and
  `shop-backend`, and `Delete repository` is off; once `backend` is typed it removes the
  folder, the row goes, and the session is forgotten

#### Scenario: Clean work
- **WHEN** `web` is clean and pushed and has no sessions, and the human clicks `Delete`
- **THEN** the dialog asks no name, and `Delete repository` removes it

#### Scenario: A running session
- **WHEN** `shop-frontend` runs and the human clicks `Delete` on `frontend`
- **THEN** the dialog shows `repository frontend of project shop has sessions not stopped:
  shop-frontend; stop them first with lado stop <name>` and only `Close`

### Requirement: The Project way says when the project or repository asked is gone

`GET /api/project-launch` SHALL answer `gone` as `"project"` when the project asked is no
project, `"repo"` when the repository asked is none of the chosen project's, else null;
the Project way SHALL then show under its field `⚠ No project <id> any more: choose one.`
or `⚠ No repository <name> in <title> any more: choose one.`, with the server's choice
below it.

#### Scenario: A project gone
- **WHEN** the page of `shop` is open, `shop` is deleted from the CLI, and the human clicks
  `New session…`
- **THEN** the window shows `⚠ No project shop any more: choose one.` and another project
  chosen

#### Scenario: Nothing gone
- **WHEN** the window asks for `shop` and `frontend`, which exist
- **THEN** `gone` is null and no warning shows

### Requirement: A narrow desktop window stacks the Projects section

In a window of at most 900 px that is not a phone, the Projects section SHALL show the
project list over the project, as Sessions does, and SHALL show no `Select a project` pane
beside the list.

#### Scenario: A narrow window
- **WHEN** the human opens `/projects` in a desktop window 390 px wide
- **THEN** the list fills the width and no `Select a project` pane shows
