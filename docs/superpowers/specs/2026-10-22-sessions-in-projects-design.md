# Sessions in projects (LAD-125)

Change: `openspec/changes/sessions-in-projects/` (proposal with AC-1..AC-9, delta specs of
`projects`, `repos-folder`, `session-clone` and `session-scratch`, `design.md` with the
decisions D1-D13). Step S3 of the epic LAD-116 (`docs/epics/lad-116/plan.md`); the model is
`docs/design/projects.md`. This document is the human's view: what a user gets, what was
decided with the human, and how the human checks it. Mockup: run artifact
`task/lad-125/mockup-session-project.html` (variant A chosen).

## What a user gets

- **A session in a project** from the terminal:
  ```
  $ git clone https://github.com/shop/frontend ~/workspace/projects/shop/frontend
  $ lado start --project shop --repo frontend
  Started session "shop-frontend" in /Users/ann/workspace/projects/shop/frontend (project shop)
  ```
  The session is named `<project>-<repository>` unless `--name` says otherwise. It refers
  to its project in `lado.db`; the project never changes while the session exists.
- **The project's repositories, read from the disk**:
  ```
  $ lado project show shop
  shop "Shop"
    folder:  /Users/ann/workspace/projects/shop
    made:    2026-10-21 14:05
    repositories:
      backend   dev   (no remote)
      frontend  main  https://github.com/shop/frontend
  ```
  A repository is a git folder directly in the project's folder; a plain folder, a hidden
  one (a clone still running), a symbolic link and the project's folder itself are not.
  `--repo` with another name refuses and lists the repositories.
- **A session the supervisor proposes** (`start_session`) starts in the same project and
  repository; a resume keeps the project.
- **No ordinary session inside `projects/`**:
  ```
  $ lado start ~/workspace/projects/shop/frontend
  lado: /Users/ann/workspace/projects/shop/frontend belongs to the project Shop: start a session in the project
  lado: Start a session in the project: lado start --project shop --repo frontend
  ```
  The same refusal comes from a clone or a fresh start into `projects/`, before anything
  is cloned or made, from the server's API and from a supervisor's `start_session` in a
  session without a project. The New session window shows it in its refusal box with the
  command and Copy; its Where hints do not offer `projects/`.
- **Where the project shows**: `lado ls` (`shop-frontend  /…/projects/shop/frontend
  project shop`), the session's API, and the session's head: the first of its facts,
  `project Shop` (tooltip `Project shop`); on a phone a line in the session's details.
- **Deleting a project** refuses while any of its sessions is not stopped, lists the
  stopped sessions it will forget, and with `--yes` forgets them with the folder and the
  record.

## Decided with the human

Questions #802–#810 of this step:
- #802 — a session in a project is named `<project>-<repository>` by default.
- #804 — `--repo` is always required, even with one repository.
- #806 — a symbolic link in a project's folder is not a repository of it.
- #808 — sessions started under `projects/<id>/` before this step are not bound to the
  project; they resume as before; only new sessions are refused.
- #810 — the head shows the project as its first fact (variant A).

## Decisions for the record

- A column `sessions.project` with a foreign key to `projects(id)`, schema 33: one source
  of truth, and a project with sessions cannot lose its record by mistake (D1).
- One core function `projects.refusal(path)` for every start path; clones and fresh
  starts get a target state `in_project` from it, so nothing is cloned or made (D5, D6).
- The refusal holds only once `projects/` is LADO's (S2's rule): a `projects/` that is the
  human's own folder is not refused and stays in the Where hints (D5, D8).
- `start_session` keeps its arguments; the core passes the parent's project (D7): no
  change of the agents' protocol.
- `lado ls` prints the project after the folder, so `session-title`'s line rule (title,
  then folder) holds (D10).
- `GET /api/projects/{id}` only; the list of projects comes with S6 (D11).
- The head reads the project's title with the session's facts (`SessionAbout`), not from
  the change feed: a rename shows on the next look, and the feed carries only the id that
  never changes (D11, D12).

## Manual check

On the pull request's branch, from a checkout of it (never the human's working copy
switched):

```bash
git fetch origin && git switch --detach origin/<the pull request's branch>
env | grep LADO_                       # unset whatever a past test left:
unset LADO_HOME LADO_REPOS LADO_TMUX_SOCKET LADO_AGENT
export LADO_HOME=$(mktemp -d) LADO_REPOS=$(mktemp -d) LADO_TMUX_SOCKET=lado-check-125
uv run lado project create shop --title Shop
git init -q "$LADO_REPOS/projects/shop/frontend" \
  && git -C "$LADO_REPOS/projects/shop/frontend" commit -q --allow-empty -m first
uv run lado project show shop              # repositories: frontend
uv run lado start --project shop --repo frontend --provider claude --no-attach
uv run lado ls                             # shop-frontend … project shop
uv run lado start "$LADO_REPOS/projects/shop/frontend" --no-attach
                                           # refused: belongs to the project Shop …
uv run lado start --new "$LADO_REPOS/projects/shop/site"     # refused, no folder made
uv run lado project delete shop --yes      # refused: shop-frontend not stopped
uv run lado ui                             # the head shows "project Shop"; New session
                                           # with Where …/projects/shop/frontend: refusal box
uv run lado stop shop-frontend
uv run lado project delete shop --yes      # Sessions to forget: shop-frontend; Deleted
uv run lado ls                             # No sessions
tmux -L lado-check-125 kill-server; rm -rf "$LADO_HOME" "$LADO_REPOS"
```

Expected: each command as its comment says; nothing is made by the refused starts; after
the delete the session, the folder and the record are gone.
