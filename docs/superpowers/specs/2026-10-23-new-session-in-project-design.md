# A new session in a project from the browser (LAD-137)

Change: `openspec/changes/new-session-in-project/` (proposal with AC-1..AC-12, the delta of
`projects` and `session-clone`, `design.md` with D1-D15). Step S6b of the epic LAD-116; the
model is `docs/design/projects.md`. This document is the human's view: what a user gets,
what was decided with the human, and how the human checks it. Mockup: the run's artifact
`mockup-project-way.html` (version 2, ten frames on LADO's own CSS: desktop and 390 px,
light and dark).

## What was decided with the human

- **#1282: the window only chooses.** New session's Project way chooses a project and one of
  its repositories; a project's repositories are managed on the project's page only. The
  concept's "+ new repository" in the window (a clone or a fresh start, then the start) is
  dropped.
- **#1283: adding a repository on the page stays in S7**, and the recommendations accepted:
  1. Project is the switch's last button: From scratch | Folder | Clone from URL | Project;
     on a phone the four buttons form a 2×2 grid (frames 8, 10).
  2. The window still opens in Folder (From scratch without recent folders).
  3. Project opens on the project of the latest started session in a project, else the
     first by title; the repository of that project's latest session, else the first.
  4. With no project, Project shows `No projects yet…` and a link to the Projects section
     (frame 3); the button is not hidden.
  5. (adding from the window is gone, so) Folder's refusal inside a project gets `Start in
     the project <title>` for a project's repository and `Open the project <title>` for
     another folder of a project (frame 4); Clone into and Create in keep the CLI command.
  6. An empty project shows `No repositories yet. Add one on the project's page:` with a
     link to the page (frame 2).
  7. The project's page gets `New session in this project…` in its not-built line (frame 6).

## What a user gets

- **New session → Project** (frame 1): a select of the projects (`Shop · shop`, a project
  whose folder is missing is off with `folder not found`), the line `2 repositories · 1
  session running · folder …/projects/shop`, and the repositories as a list that is always
  there, even with one item: `frontend  main · github.com/shop/frontend`. Name reads
  `shop-frontend` until edited; Kits and Permission mode come from that repository's last
  session; Provider is suggested as in Folder. **Start session** opens the session, whose
  head shows `project Shop`.
- **A taken name** (frame 5): the note under Name and, after Start, the core's text
  `session "shop-frontend" exists already (stopped, in …); resume it, or give the new
  session another name` with `Resume it`.
- **Folder in a project** (frame 4): typing `…/projects/shop/frontend` shows the core's
  refusal with `Start in the project Shop`, which switches to Project with Shop and
  frontend; the CLI command stays below.
- **The project's page** (frame 6): `New session in this project… Not built yet: the
  repositories on this page (adding, removing), renaming and deleting the project. Plan:
  Projects, step S7. Meanwhile: lado project show shop, lado project repo add shop
  <git-url>.`
- **For other clients** of LADO's API (the future LADO manager): `POST /api/sessions` with
  `where: {kind: "project", project, repo}` starts a session in a project exactly as `lado
  start --project --repo`; `GET /api/project-launch` tells what such a start takes.

## Out of scope

Adding a repository from the window (#1282); the project's page with its repositories,
"+ Add repository", delete, its sessions, rename and delete (S7, #1283); a Project button in
the refusals of Clone into and Create in; "all repositories"; opening the window in Project
by default.

## How the human checks it

From a checkout of the pull request's branch `feature/lad-137-new-session-in-project` in its
own folder (never the working copy you work in):

```bash
git fetch origin && git switch feature/lad-137-new-session-in-project  # in a separate clone/worktree
pwd && git branch --show-current                                         # the folder and the branch
env | grep LADO_                      # what your shell gives LADO; unset each, e.g.:
unset LADO_HOME LADO_REPOS LADO_TMUX_SOCKET LADO_ENV_DIR
export LADO_HOME=$(mktemp -d) LADO_REPOS=$(mktemp -d) LADO_TMUX_SOCKET=lado-check-137
uv run lado project create shop --title Shop
uv run lado project repo add shop --new frontend
uv run lado project repo add shop --new backend
uv run lado project create acme --title "ACME CRM"
make web && uv run lado server        # open the URL it prints
```

1. New session opens in Folder (or From scratch). Click Project: `ACME CRM` would be first
   by title, but no session ran yet, so `ACME CRM · acme` is chosen with `No repositories
   yet…` and Start off; its link opens `/projects/acme` and closes the window.
2. New session → Project → `Shop`: `backend` and `frontend` listed, the first chosen; pick
   `frontend`: Name `shop-frontend`. Start session: the session opens, its head shows
   `project Shop`.
3. Stop it; New session → Project: Shop and frontend are chosen (the last used), the note
   under Name offers `Resume it`. Start session: the core's "exists already" text and
   `Resume it`.
4. Folder: type `$LADO_REPOS/projects/shop/backend`: the refusal and `Start in the project
   Shop`; click it: Project with Shop and backend. Type `$LADO_REPOS/projects/shop`: `Open
   the project Shop`.
5. On `/projects/shop`: `New session in this project…` opens the window in Project with
   Shop.
6. In the browser's device mode at 390 px: the switch is a 2×2 grid inside the window.
7. At the end: `uv run lado stop shop-frontend; tmux -L lado-check-137 kill-server; rm -rf
   "$LADO_HOME" "$LADO_REPOS"; unset LADO_HOME LADO_REPOS LADO_TMUX_SOCKET`.
