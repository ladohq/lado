# Projects in the core and the default workspace (LAD-123)

Change: `openspec/changes/projects-in-core/` (proposal with AC-1..AC-10, delta specs of
`projects` (new), `repos-folder`, `session-clone` and `session-scratch`, `design.md` with
the decisions D1-D14). Step S2 of the epic LAD-116 (`docs/epics/lad-116/plan.md`); the
model is `docs/design/projects.md`. This document is the human's view: what a user gets,
what was decided with the human, and how the human checks it. Mockup: run artifact
`task/lad-123/mockup-workspace-where.html`.

## What a user gets

- **A workspace on every installation.** Without `LADO_REPOS` the workspace is
  `~/workspace`. A clone by URL or a fresh start with no folder given goes there
  (`~/workspace/<repo>`, was `~/lado/<repo>`); LADO makes the folder the first time it
  needs it. Sessions already in `~/lado/...` keep working where they are.
- **`lado doctor` always names the workspace**:
  `[info] Workspace: /Users/ann/workspace (default), not made yet: the first clone or
  project makes it`, then `[ok  ] Workspace: /Users/ann/workspace (default)` once it
  exists; with `LADO_REPOS` as before. A `LADO_REPOS` that is not a full path is ignored
  with a warning that names the folder used instead.
- **The New session window** shows `/Users/ann/workspace/…` in an empty Where,
  `/Users/ann/workspace/<repo>` in Clone into and `/Users/ann/workspace/<name>` in From
  scratch's Create in. The Workspace row and the subfolder hints appear once the folder
  exists.
- **Projects from the terminal**:
  ```
  $ lado project create shop --title Shop
  Made project shop "Shop": /Users/ann/workspace/projects/shop
  $ lado project list
  acme  acme  /Users/ann/workspace/projects/acme  (folder not found)
  shop  Shop  /Users/ann/workspace/projects/shop
  $ lado project show shop
  shop "Shop"
    folder:  /Users/ann/workspace/projects/shop
    made:    2026-10-21 14:05
  $ lado project rename shop "Shop EU"
  shop: title "Shop EU"
  $ lado project delete shop
  Unpushed work in /Users/ann/workspace/projects/shop:
    frontend: uncommitted changes; branch feature-x not pushed
  lado: deleting project shop removes its folder /Users/ann/workspace/projects/shop with everything in it; run again with --yes
  $ lado project delete shop --yes
  Deleted project shop
  ```
  A project's folder is always `<workspace>/projects/<id>`; LADO makes it, and refuses
  when that folder already exists or when `projects/` is the human's own folder. Agents
  can list and show projects but not make, rename or delete them.
- **`lado doctor`'s Projects line**: how many projects there are, or a project whose
  folder is not found, a foreign folder in `projects/`, `projects/` that is the human's.

Not yet: sessions in a project (S3), repositories of a project (S4), variables and
secrets (S5a, S5b), the Projects section of the UI (S6, S7), compose's `LADO_WORKSPACE`
(S2b).

## Decided with the human

From the step's brief (approved at the epic's step gate #44): the scope above; the id
rule `[a-z0-9][a-z0-9-]*`, 1-40 characters; `delete` without sessions, refusing without
`--yes`; agents refused; one new table; a minor version.

Round 1 (question #613), all as recommended:
1. A `LADO_REPOS` that is not absolute is ignored and `~/workspace` is used, with a
   doctor warning naming it.
2. `projects/` is the human's own folder when it holds visible entries and none of them is
   a project of LADO; hidden entries do not count; no marker file.
3. The CLI's output as shown above; the title follows the session title's rule; `delete`
   always needs `--yes`; a project without its folder is deleted as a record.
4. `lado doctor` shows the full path of the default workspace and one Projects line.
5. The New session window as in the mockup.

Question #615: the container spec's "project" meaning a repository goes to step S2b.

## Decisions for the record

The engineering decisions are in `openspec/changes/projects-in-core/design.md` (D1-D14):
one function `projects.workspace()` in a new module `projects.py`; the old names
(`repos_folder`, `DEFAULT_PARENT`, `check_repos_folder`, `OUTSIDE_REPOS`, `ReposFolder`)
renamed, the API path and the capability `repos-folder` kept; the table `projects` at
schema 32 without journal triggers; create's order with the insert and the mkdir in one
transaction; delete's scan without network; `_human_only` as the agent rule.

## Manual check

Do it in temporary folders only: never in your own `~/workspace` or `LADO_HOME`.

1. Check out the pull request's branch in a separate clone or worktree (never switch your
   working copy): `git fetch origin && git worktree add /tmp/lado-s2 <branch>`;
   `cd /tmp/lado-s2 && uv sync`.
2. Clear what an earlier test may have left: `env | grep LADO_`, then `unset LADO_REPOS
   LADO_HOME LADO_TMUX_SOCKET` (and any other `LADO_` name listed).
3. A throwaway home: `export TMP=$(mktemp -d) HOME_SAVE=$HOME; export HOME=$TMP/home
   LADO_HOME=$TMP/lado LADO_TMUX_SOCKET=lado-s2; mkdir -p $HOME`. (`HOME` moves so that
   `~/workspace` is `$TMP/home/workspace`; set `GIT_CONFIG_GLOBAL=$HOME_SAVE/.gitconfig`
   so git still knows you.)
4. `uv run lado doctor`: expect `[info] Workspace: $TMP/home/workspace (default), not
   made yet: the first clone or project makes it` and no Projects line.
5. `uv run lado project create shop --title Shop`: expect `Made project shop "Shop":
   $TMP/home/workspace/projects/shop`; the folder exists. `uv run lado doctor`: Workspace
   `ok … (default)`, `[ok  ] Projects: 1 in …/projects`.
6. `uv run lado project create Shop` → refused (the id rule); `create shop` → `project
   shop exists`; `mkdir $HOME/workspace/projects/acme && uv run lado project create acme`
   → refused, the folder exists; `uv run lado doctor` → `foreign folder in projects/:
   acme`.
7. `uv run lado project list`, `show shop`, `rename shop "Shop EU"`, `show shop`.
8. Unpushed work: `git init -q $HOME/workspace/projects/shop/frontend && cd $_ && git
   commit -q --allow-empty -m init && git switch -q -c feature-x && touch a && cd -`;
   `uv run lado project delete shop` → lists `frontend: uncommitted changes; branch
   master not pushed; branch feature-x not pushed` (or `main`), exits 1, the folder
   stays.
9. `LADO_AGENT=x uv run lado project create other` → refused for an agent;
   `LADO_AGENT=x uv run lado project list` works.
10. `uv run lado project delete shop --yes` → `Deleted project shop`; the folder is gone,
    `$HOME/workspace/projects/acme` stays.
11. `LADO_REPOS=code uv run lado doctor` → `[warn] Workspace: LADO_REPOS is not an
    absolute path: code; LADO uses $TMP/home/workspace`.
12. The window: `uv run lado ui` with this `HOME`; New session: Where shows
    `$TMP/home/workspace/…`, the Workspace row shows (the folder exists now). Clone from
    URL with any URL: Clone into proposes `$TMP/home/workspace/<repo>`. Then stop the
    server, `rm -rf $HOME/workspace`, start it again: no Workspace row and no hints in an
    empty Where.
13. Clean up: `uv run lado stop --all`; `export HOME=$HOME_SAVE`; `rm -rf $TMP`;
    `git worktree remove /tmp/lado-s2`.
