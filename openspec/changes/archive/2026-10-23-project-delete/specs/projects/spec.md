## RENAMED Requirements

- FROM: `### Requirement: The project's page shows the project and what is not built yet`
- TO: `### Requirement: The project's page shows the project and its delete`

## MODIFIED Requirements

### Requirement: lado project delete shows unpushed work and needs --yes

`lado project delete <id>` SHALL print the core's preview (`projects.deletion`): the
sessions it will forget, `Sessions to forget: <name> (<n> open run[s]), …` (` (no project)`
after one without a project; no line without sessions), then the unpushed work of the
project folder: itself when a repository's root, each repository directly in it, each
worktree of one, once. Without `--yes` it SHALL then refuse, exit 1, changing nothing.

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

#### Scenario: A stopped session from before projects
- **WHEN** `old-site` has no project, was started in `<ws>/projects/shop/site` and is
  stopped, and the human runs `lado project delete shop`
- **THEN** the output has `Sessions to forget: old-site (no project)`

#### Scenario: The project folder is a repository
- **WHEN** `<ws>/projects/shop` itself is a git repository with a commit on a branch with
  no upstream, and the human runs `lado project delete shop`
- **THEN** the list has `  the project's folder: …; branch main not pushed`

#### Scenario: A worktree inside the project folder
- **WHEN** `<ws>/projects/shop/frontend-fix` is a worktree of `<ws>/projects/shop/frontend`
  with uncommitted changes
- **THEN** the list has the line `  frontend (worktree frontend-fix): uncommitted changes`
  once and no line of its own for `frontend-fix`

#### Scenario: An unreadable project folder
- **WHEN** `<ws>/projects/shop` cannot be listed (no read permission) and the human runs
  `lado project delete shop`
- **THEN** the list has `  the project's folder: could not check: Permission denied`, it
  exits 1 with a `lado: …` line, and no traceback is printed

### Requirement: lado project delete --yes removes the folder, then the record

`lado project delete <id> --yes` SHALL remove the project folder whole, then forget each
session the preview named (as `lado forget --force` does), then remove its data folder
`<LADO_HOME>/projects/<id>/`, then the record, and print `Deleted project <id>`. A project
whose folder is not found SHALL lose its sessions, data folder and record only. When the
folder or the data folder cannot be removed whole, the record SHALL stay, exit 1.

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

#### Scenario: With a stopped session from before projects
- **WHEN** `old-site` has no project, was started in `<ws>/projects/shop/site` and is
  stopped, and the human runs `lado project delete shop --yes`
- **THEN** the folder and the session `old-site` are gone

#### Scenario: A folder that cannot be removed
- **WHEN** a file in `<ws>/projects/shop` cannot be removed and the human runs `lado
  project delete shop --yes`
- **THEN** it exits 1 with `lado: could not remove <folder> whole: …; the project stays`,
  and the sessions and the record stay

### Requirement: lado project delete removes nothing outside the project folder

`lado project delete` SHALL remove only `<workspace>/projects/<id>`, whose real path
SHALL be a direct child of the real path of `<workspace>/projects`, or else refuse. When
`<workspace>/projects/<id>` is a symbolic link, it SHALL remove the link and never its
target, list no work of the target, and match no session by a path through the link.

#### Scenario: A link to a folder elsewhere
- **WHEN** `<ws>/projects/shop` is a symbolic link to `/srv/shop` and the human runs
  `lado project delete shop --yes`
- **THEN** the link is gone, `/srv/shop` and its files stay, and the record is gone

#### Scenario: The link is announced as a link
- **WHEN** `<ws>/projects/shop` is a symbolic link to `/srv/shop` holding a repository with
  unpushed work, and the human runs `lado project delete shop`
- **THEN** no unpushed list is printed, and it exits 1 with `lado: deleting project shop
  removes the link <ws>/projects/shop only, not its target /srv/shop; run again with
  --yes`

#### Scenario: A session in the link's target
- **WHEN** `<ws>/projects/shop` is a link to `/srv/shop`, and `srv`, with no project, runs
  in `/srv/shop/app`
- **THEN** `lado project delete shop --yes` is not refused for `srv`, removes the link, and
  `srv` stays

### Requirement: lado project delete refuses while a session in the project's folder runs

`lado project delete <id>`, with `--yes` or without, SHALL refuse, exit 1, changing
nothing, while any session of the project, or any session whose folder's real path is
inside the real path of a project folder that is no link (one with no project, from
before schema 33), is not stopped: `lado: project <id> has sessions not stopped: <names>;
stop them first with lado stop <name>`.

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

### Requirement: The project's page shows the project and its delete

The project's page SHALL show the title (the id without one) with its Rename, the id, the
button `New session…`, the line `<N> repositories · <N> sessions running · folder
<folder>` (`folder not found` after it when it is missing), and, at its bottom, the block
`Delete project`: one sentence on what goes and the button `Delete project…`.

#### Scenario: The head of the page
- **WHEN** the human opens `/projects/shop`
- **THEN** the page shows `Shop`, `shop`, `New session…`, `2 repositories · 2 sessions
  running · folder <workspace>/projects/shop`, the block `Delete project` with `Delete
  project…` at its bottom, and no line `not built yet`

## ADDED Requirements

### Requirement: The unpushed check does not count a project's repositories as its folder's changes

When the project's folder is itself a repository's root, its line SHALL NOT name
`uncommitted changes` for the entries directly in it that are git repositories or
worktrees (the project's repositories); a change of the root repository's own files SHALL
still be named.

#### Scenario: A clean root around the project's repositories
- **WHEN** `<ws>/projects/shop` is a clean repository holding the repositories `frontend`
  and `backend`, all pushed
- **THEN** `lado project delete shop` prints no unpushed list

#### Scenario: A change of the root's own file
- **WHEN** the root repository has an uncommitted `README.md`
- **THEN** the list has `  the project's folder: uncommitted changes`

### Requirement: A change to a project deleted meanwhile is refused as unknown

`lado project set` (with `--secret` too) and `PUT /api/projects/{id}/variables/{name}` and
`…/secrets/{name}` SHALL refuse a project deleted between their check and their write as
an unknown project, `unknown project "<id>"` (exit 1, 404), and leave no variable row and
no secret file of it.

#### Scenario: A set racing a delete
- **WHEN** the record of `shop` is deleted after `lado project set shop BOARD_URL https://a`
  checked it and before it writes
- **THEN** it exits 1 with `lado: unknown project "shop"`, with no traceback, and no row of
  `shop` is stored

#### Scenario: A secret racing a delete
- **WHEN** the record of `shop` is deleted while `PUT /api/projects/shop/secrets/GH_TOKEN`
  writes
- **THEN** the answer is 404, and `<LADO_HOME>/projects/shop/secrets/GH_TOKEN` does not
  exist

### Requirement: The server previews and deletes a project

`GET /api/projects/{id}/deletion` SHALL answer the core's preview `projects.deletion`
(`ProjectDeletion`: the folder, its kind `folder`, `link` or `missing`, a link's target,
the sessions forgotten, the unpushed lines, the variables' and secrets' names) and change
nothing; `DELETE /api/projects/{id}` with the change token SHALL delete it by
`projects.delete`, the CLI's. Unknown is 404, a refusal 400 with the core's text.

#### Scenario: The preview
- **WHEN** `shop` has the stopped session `shop-backend`, the unpushed branch
  `feature/checkout` in `backend`, the variable `BOARD_URL` and the secret `GH_TOKEN`, and
  the UI sends `GET /api/projects/shop/deletion`
- **THEN** the answer has `kind: "folder"`, the session `shop-backend`, the line `backend:
  branch feature/checkout not pushed`, `variables: ["BOARD_URL"]` and `secrets:
  ["GH_TOKEN"]`, and no value of either

#### Scenario: The delete
- **WHEN** no session of `shop` runs and the UI sends `DELETE /api/projects/shop` with the
  change token
- **THEN** the folder, `<LADO_HOME>/projects/shop`, the sessions and the record are gone,
  as after `lado project delete shop --yes`

#### Scenario: A running session
- **WHEN** `shop-frontend` runs and the UI sends either request
- **THEN** the answer is 400 with `project shop has sessions not stopped: shop-frontend;
  stop them first with lado stop <name>`, and nothing changes

#### Scenario: Unknown or without the token
- **WHEN** the UI sends `DELETE /api/projects/nope`, or `DELETE /api/projects/shop`
  without the change token
- **THEN** the first answer is 404, the second is refused, and nothing changes

### Requirement: The UI deletes a project after showing what goes

`Delete project…` SHALL open `Delete project <title>?` from the preview: the folder and
what goes with it, `Work that is not on the remote`, `Sessions that are forgotten`,
`Variables and secrets that are deleted` (names, a secret marked so). `Delete project`
SHALL stay off until the id is typed exactly, then send `DELETE` and open `/projects`. A
refusal SHALL show verbatim with only `Close`.

#### Scenario: Unpushed work and what else goes
- **WHEN** `shop` has the branch `feature/checkout` not pushed in `backend`, the stopped
  session `shop-backend`, `BOARD_URL` and the secret `GH_TOKEN`, and the human clicks
  `Delete project…`
- **THEN** the dialog shows `backend: branch feature/checkout not pushed`, `shop-backend`,
  `BOARD_URL` and `GH_TOKEN — secret`, and `Delete project` is off

#### Scenario: The id typed
- **WHEN** the human types `shop` and clicks `Delete project`
- **THEN** the browser shows `/projects`, the list has no `Shop`, and the folder, its
  sessions and its secrets are gone

#### Scenario: A clean project still asks the id
- **WHEN** every repository of `acme` is pushed and clean
- **THEN** the dialog says `All its work is on the remote.`, and `Delete project` stays off
  until `acme` is typed

#### Scenario: A running session
- **WHEN** `shop-frontend` runs and the human clicks `Delete project…`
- **THEN** the dialog shows `project shop has sessions not stopped: shop-frontend; stop
  them first with lado stop <name>` and only `Close`

#### Scenario: A project folder that is a link
- **WHEN** `<ws>/projects/shop` is a link to `/srv/shop`
- **THEN** the dialog says `Its folder <ws>/projects/shop is a link to /srv/shop: only the
  link is deleted, /srv/shop and everything in it stay.` and lists no work of `/srv/shop`

### Requirement: Leaving the page cancels Add repository's clone

When the Add repository dialog unmounts while its clone job runs (the human goes Back or to
another section), the UI SHALL cancel the job at once (`DELETE /api/clones/{id}`), as
`Cancel clone` does, so no folder is left.

#### Scenario: Back during a clone
- **WHEN** a clone of Add repository runs and the human presses the browser's Back
- **THEN** the UI sends `DELETE /api/clones/<id>` at once, and the project's folder gets no
  new repository
