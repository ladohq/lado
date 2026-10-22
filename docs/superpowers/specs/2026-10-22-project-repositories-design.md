# Adding and removing a project's repositories (LAD-128)

Change: `openspec/changes/project-repositories/` (proposal with AC-1..AC-10, delta specs of
`projects`, `session-clone` and `session-scratch`, `design.md` with the decisions
D1-D12). Step S4 of the epic LAD-116 (`docs/epics/lad-116/plan.md`); the model is
`docs/design/projects.md`. This document is the human's view: what a user gets, what was
decided with the human, and how the human checks it. No mockup: no screen changes.

## What a user gets

- **A repository added by a clone**, without going to the host:
  ```
  $ lado project repo add shop https://github.com/shop/frontend
  Cloning the default branch of https://github.com/shop/frontend into /Users/ann/workspace/projects/shop/frontend
  Receiving objects: 100% (1200/1200), 3.10 MiB | 4.20 MiB/s
  Added repository frontend to project shop: /Users/ann/workspace/projects/shop/frontend
  Start a session in it: lado start --project shop --repo frontend
  ```
  `--name` gives another folder name, `--branch` another branch. The clone goes to a
  hidden temporary folder renamed only at the end: a clone still running, failed or
  cancelled (Ctrl-C) is never in `lado project show`.
- **A repository from scratch**:
  ```
  $ lado project repo add shop --new site
  Made /Users/ann/workspace/projects/shop/site a git repository with an empty first commit
  Added repository site to project shop: /Users/ann/workspace/projects/shop/site
  Start a session in it: lado start --project shop --repo site
  ```
- **The name**: Latin letters, digits, `.`, `_`, `-`, not starting with `.` or `-`, at most
  100 characters; a name already in the project's folder is refused.
- **Removing a repository**, with what it loses shown first:
  ```
  $ lado project repo remove shop frontend
  Sessions to forget: shop-frontend (1 open run)
  Unpushed work in /Users/ann/workspace/projects/shop/frontend:
    frontend: uncommitted changes; branch lado/shop-frontend/dev-1 not pushed
  lado: removing repository frontend of project shop deletes its folder /Users/ann/workspace/projects/shop/frontend with everything in it and forgets its 1 session; run again with --yes
  $ lado project repo remove shop frontend --yes
  …
  Removed repository frontend from project shop
  ```
  Refused while any session in that folder is not stopped. A symbolic link loses the link
  only; a plain folder is refused. Nothing outside the repository's folder is removed.
- **From an agent** both commands refuse, as `lado project create` does.
- **The server's API** for the UI to come: a clone job into a project (`POST /api/clones`
  with `project`, `name`), `POST /api/projects/{id}/repos` from scratch,
  `GET /api/projects/{id}/repos/{name}/removal`, `DELETE /api/projects/{id}/repos/{name}`.
- **Better hints** (S3's remnant E3): `lado start --new ~/workspace/projects/shop/web` now
  offers `lado project repo add shop --new web`; a clone there offers `lado project repo
  add shop <url>`; a plain folder in a project offers `lado project show shop`; a project
  with no repositories says how to add one.

## Decided with the human

Question #892 of this step (all three as recommended):
- the CLI is `lado project repo add|remove` only; no `lado start --project <id> <url>` or
  `--new` that starts a session at once;
- `remove` removes only a repository of the project and a symbolic link (the link alone);
  a plain folder or a file is refused;
- the name rule above, the name taken from the URL by default, no transliteration in the
  CLI.

The scale (full) and the engineering decisions are in `design.md` (D1-D12) and the
artifact `design`.

## Manual check

On the pull request's branch `feature/lad-128-project-repositories`, from the run's
worktree (or a fresh clone checked out on that branch), never with the human's own LADO:

```bash
env | grep LADO_                       # nothing a past test left
unset LADO_HOME LADO_REPOS LADO_TMUX_SOCKET LADO_AGENT LADO_SESSION
export T=$(mktemp -d)
export LADO_HOME=$T/home LADO_REPOS=$T/ws LADO_TMUX_SOCKET=lado-check-$$
git init -q --bare -b main $T/frontend.git
git clone -q $T/frontend.git $T/seed && git -C $T/seed commit -q --allow-empty -m init \
  && git -C $T/seed push -q origin HEAD:main
uv run lado project create shop --title Shop
uv run lado project repo add shop file://$T/frontend.git   # Added repository frontend …
uv run lado project repo add shop --new site               # Made … Added repository site …
uv run lado project repo add shop --new site               # exit 1: already exists
uv run lado project show shop                              # frontend main <remote>, site main (no remote)
git -C $LADO_REPOS/projects/shop/frontend switch -q -c feature-x
git -C $LADO_REPOS/projects/shop/frontend commit -q --allow-empty -m wip
uv run lado project repo remove shop frontend              # Unpushed work: branch feature-x not pushed; exit 1
ls $LADO_REPOS/projects/shop                               # frontend site: nothing removed
uv run lado project repo remove shop frontend --yes        # Removed repository frontend from project shop
ls $LADO_REPOS/projects/shop                               # site
uv run lado start --new $LADO_REPOS/projects/shop/web --no-attach  # hint: lado project repo add shop --new web
tmux -L $LADO_TMUX_SOCKET kill-server 2>/dev/null; rm -rf $T
```

Expected: each command prints what its comment says; `$T/frontend.git` and `$T/seed` stay
untouched by the removal.
