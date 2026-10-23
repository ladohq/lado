# Deleting a project (LAD-139)

Change: `openspec/changes/project-delete/` (proposal with AC-1..AC-13, the delta of
`projects`, `design.md` with D1-D13). Step S7b of the epic LAD-116, its last; the model is
`docs/design/projects.md` and the concept `projects-concept` ("Deletion"). This document is
the human's view: what a user gets, what was decided with the human, and how the human
checks it. Mockup: the run's artifact `mockup-project-delete.html` (frames on LADO's own
CSS: desktop and 390 px, light and dark; with unpushed work, without it, refused).

## What was decided with the human

- **#1375, the round on the dialog** (accepted as recommended):
  1. The button lives in a block `Delete project` at the page's bottom, in place of the
     not-built line (layout A, frame 1), not in the head beside `New session…` (frame 1b).
  2. **The project's id is always typed** (frame 3a), as the concept says: the project's
     variables and secrets go with it and are on no remote. Not only with unpushed work, as
     a repository's delete asks (#1352, frame 3b).
  3. The dialog lists three things: `Work that is not on the remote` (every repository,
     S7a's lines), `Sessions that are forgotten` (the project's and those without a project
     in its folder), and `Variables and secrets that are deleted` (names only).
- **The brief of gate #113** (the human's words through the epic's lead): one core
  function for the CLI, the API and the dialog; nothing deleted outside
  `<workspace>/projects/<id>` and `<LADO_HOME>/projects/<id>`, no link followed; the
  leftovers F5/G1, E3, S5a's F5, S7a's F2 and F1; the canary over the delete; a trash or
  an undo would be a new task.

## What a user gets

- **The project's page** (frame 1) ends with the block **Delete project**: `Deletes its
  folder with every repository in it, its sessions, variables and secrets. Refused while a
  session of the project runs.` and the button `Delete project…`.
- **The dialog `Delete project Shop?`** (frame 2): `Its folder …/projects/shop is deleted
  with everything in it, and so are its sessions, variables and secrets. This cannot be
  undone.`; `Work that is not on the remote` — `backend: uncommitted changes; branch
  feature/checkout not pushed; 2 stashes`, `backend (worktree …): uncommitted changes`,
  `notes: … detached HEAD with 3 commits on no branch`; `Sessions that are forgotten` —
  `shop-backend (1 open run)`, `backend-old — no project, started in this folder before
  projects`; `Variables and secrets that are deleted` — `BOARD_URL`, `GH_TOKEN — secret`;
  `Type shop to delete it`; `Delete project` on only once `shop` is typed.
- **A clean project** (frame 3a): `All its work is on the remote.`, and the id is still
  typed.
- **A running session** (frame 4): `project shop has sessions not stopped: shop-frontend;
  stop them first with lado stop <name>` and only Close. The same when a session starts
  while the dialog is open.
- **A project folder that is a link** (frame 5): `Its folder … is a link to /srv/shop:
  only the link is deleted, /srv/shop and everything in it stay.`; no work of `/srv/shop`
  listed; a session working in `/srv/shop` without a project neither blocks nor goes.
- **A project folder that is itself a repository** (frame 6, left): its repositories no
  longer show as its `uncommitted changes`; **an unreadable folder** (frame 6, right):
  `the project's folder: could not check: Permission denied`, never a crash.
- **After the delete** (frame 7): the list of projects, without it.
- **The CLI** says the same: `lado project delete` names `(no project)` sessions, and for a
  link `… removes the link <folder> only, not its target <target>`.
- **Small fixes:** `lado project set` racing a delete says `unknown project "<id>"`
  instead of a crash; leaving the project's page while Add repository clones cancels the
  clone at once.

## Manual check

1. A branch with the change, `env | grep LADO_` and `unset` each found; `export
   LADO_HOME=$(mktemp -d) LADO_REPOS=$(mktemp -d) LADO_TMUX_SOCKET=lado-check-$$
   LADO_TELEMETRY=0`.
2. `uv run lado project create shop --title Shop`; `uv run lado project repo add shop --new
   web`; `uv run lado project set shop BOARD_URL https://a`; `printf x | uv run lado
   project set shop GH_TOKEN --secret`.
3. `uv run lado server` with the fake provider (`tests/integration/fake_provider.py`, as
   `docs/testing.md` says); open the printed URL; Projects → Shop: the block `Delete
   project` at the bottom, no `not built yet`.
4. Start session on `web` → Start in Shop. Back on the page, `Delete project…`: the refusal
   naming the session, Close only.
5. Stop the session; in `web` commit on a new branch. `Delete project…`: the branch's line,
   the session, `BOARD_URL`, `GH_TOKEN — secret`; `Delete project` off for `sho` and
   `Shop`, on for `shop`. Delete: `/projects` without Shop; `$LADO_REPOS/projects/shop`
   and `$LADO_HOME/projects/shop` are gone; `uv run lado ls` has no such session.
6. `uv run lado project create acme`; `rmdir $LADO_REPOS/projects/acme`; `ln -s $(mktemp
   -d) $LADO_REPOS/projects/acme`; the page's dialog: the link sentence; Delete with
   `acme`: the link gone, its target there.
7. `tmux -L $LADO_TMUX_SOCKET kill-server`; `unset LADO_HOME LADO_REPOS LADO_TMUX_SOCKET
   LADO_TELEMETRY`.

## Out of scope

A trash or an undo of a delete (new behaviour: a task of its own if wanted); S7a's minors
F3, F4, X3, X5 (the plan's Later); sessions over several repositories; repository extras in
the database; links in the project's folder on the page; listing the work in a link
folder's target (it is not lost).
