# The project's page (LAD-138)

Change: `openspec/changes/project-page/` (proposal with AC-1..AC-16, the delta of
`projects`, `design.md` with D1-D17). Step S7a of the epic LAD-116; the model is
`docs/design/projects.md`. This document is the human's view: what a user gets, what was
decided with the human, and how the human checks it. Mockup: the run's artifact
`mockup-project-page.html` (14 frames on LADO's own CSS: desktop and 390 px, light and
dark).

## What was decided with the human

- **#1347: S7 is split.** S7a (this change): the project's page with its repositories and
  sessions, adding and deleting a repository, renaming the project. S7b (a task of its own,
  derived from LAD-138): deleting the project, with the leftovers that live in that path.
- **#1350 and #1352, the round on the page** (accepted as recommended but 2, 6 and 8):
  1. Sessions in a block of their own under the repositories (variant A, frame 1), not
     under each repository (frame 2): from the change feed, no new API.
  2. Rename in place, as a session's title, **with Tab taking the project's id** as Tab
     takes a session's name (#1352; frame 3).
  3. Add repository: a dialog with Clone from URL (URL, Name from the URL, Branch) or From
     scratch (Name); it closes after the add and starts no session (frames 4–6, 9).
  4. Removing a repository names and forgets the stopped sessions without a project in its
     folder (X3), in the CLI too, one core function (frame 7).
  5. New session opened for a project or repository that is gone says so (E1, frame 10).
  6. Deleting a repository **with work not on the remote asks for its name typed**; a clean
     one is deleted by the button alone (#1352: "deleting a repository works the same way"
     as a project, and unpushed commits or stashes are lost for good; frames 7, 7b). A
     running session's refusal shows with Close only (frame 8).
  7. Links in the project's folder are not shown on the page.
  8. S7b created as LAD-139 (derived from LAD-138, relates to LAD-116), **without F2 and
     F3**: the shared unpushed check is fixed here, S7b only checks that its dialog shows
     them (#1352).

## What a user gets

- **The project's page** (frame 1): `Shop` with Rename, `shop`, `New session…`; `3
  repositories · 1 session running · folder …/projects/shop`; **Repositories**: `frontend`
  `branch main · github.com/shop/frontend`, `notes` `detached HEAD · no remote`, each with
  Start session and Delete, and `+ Add repository`; **Sessions**: `Checkout redesign
  shop-frontend · frontend running 2 h`, `shop-backend backend stopped 3 days ago`; then
  the warning, who gets new values, Variables, Secrets, and at the bottom `Deleting the
  project: not built yet (Projects, step S7b). Meanwhile: lado project delete shop.`
- **Add a repository** (frames 4–6): Clone from URL lists the remote's branches and fills
  Name; Clone shows git's progress, and Cancel clone stops it and leaves nothing; From
  scratch makes a repository with one empty commit; a taken name shows the core's text.
- **Delete a repository** (frame 7): the folder, the work not on the remote (also commits
  on a detached HEAD, stashes, workers' worktrees), and the sessions that are forgotten;
  with such work the name is typed first, then Delete repository removes it. With a session running there, the refusal and Close
  (frame 8).
- **Rename** (frame 3): the title becomes a field; Enter saves, Esc cancels, empty shows
  the id, Tab takes the id; the list and the sessions' heads show the new title.
- **Fixes:** New project says `The title gives no id: type one.` (frame 12); a narrow
  desktop window shows Projects as Sessions, without `Select a project`; New session tells
  when the project asked is gone (frame 10); Clone into and Create in inside a project offer
  `Open the project <title>` (frame 11); `lado project repo remove` and `project delete`
  name commits on a detached HEAD and stashes, `project delete` a project folder that is
  itself a repository and a worktree inside it once, and the repository's removal names
  `(no project)` sessions.

## Manual check

1. A branch with the change, `env | grep LADO_` and `unset` each found; `export
   LADO_HOME=$(mktemp -d) LADO_REPOS=$(mktemp -d) LADO_TMUX_SOCKET=lado-check-$$`.
2. A bare repository to clone: `git init --bare $LADO_REPOS/../admin.git` with one pushed
   commit, or any `file://` URL.
3. `uv run lado project create shop --title Shop`; `uv run lado server` with the fake
   provider (`tests/integration/fake_provider.py`, as `docs/testing.md` says); open the
   printed URL.
4. Projects → Shop: the empty Repositories block. `+ Add repository` → From scratch → `web`
   → Create: the row `web` with `branch main · no remote`.
5. `+ Add repository` → Clone from URL → the `file://` URL: Name fills, branches list;
   Clone: the progress, then the row with its branch. Again with a large remote and Cancel
   clone: `the clone was cancelled`, no folder under `$LADO_REPOS/projects/shop/`.
6. Start session on `web` → Start in Shop: the session's head reads `project Shop`; back on
   the page the Sessions block lists it running. Delete on `web`: the refusal and Close.
7. Stop the session; in `web` make a commit on a new branch, and `git stash` a change; Delete
   on `web`: the dialog names the branch, `1 stash` and the session, and Delete repository is
   off until `web` is typed; then the row and the folder are gone, `lado ls` has no such
   session. Delete on a clean repository: no name asked.
8. Rename to `Shop EU`: the head and the list; open a session of the project: its head.
   In an untitled project, Rename then Tab: the field holds the id.
9. New project with the title `!!!`: the note under Id.
10. A desktop window 390 px wide: Projects shows the list, no `Select a project`.
11. `tmux -L $LADO_TMUX_SOCKET kill-server`; `unset LADO_HOME LADO_REPOS LADO_TMUX_SOCKET`.

## Out of scope

Deleting the project and its leftovers (S7b, LAD-139: F5, G1, E3, S5a's F5, X3 for the
project, the canary over the delete); links on
the page; starting a session from Add repository; a name check while typing; sessions over
several repositories; repository extras in the database.
