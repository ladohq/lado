# One database backup: the migration's (LAD-143)

Change: `openspec/changes/one-database-backup/` (proposal with AC-1..AC-9, delta specs
`update-database` (new), `schema-migration` and `release-candidates`, `design.md` with
the decisions D1-D13). Step S9 of the epic LAD-116 (`docs/epics/lad-116/plan.md`). This
document is the human's view: what a user gets, what was decided with the human, and how
the human checks it. No mockup: no screen changes (the web UI only updates forward).

## What a user gets

- **`~/.lado/backups/` has one kind of copy**: `lado.db.schema-<N>`, written by the
  migration that moved the database from schema N. `lado update` writes nothing there and
  deletes nothing there.
- **A failed update still rolls back with the database**, from that copy:
  ```
  Rolling back to LADO 0.43.0: the UI server did not come up on LADO 0.44.0: /api/health says nothing
  Reinstalling: uv tool install lado==0.43.0
  Restored lado.db from /home/me/.lado/backups/lado.db.schema-35
  Resuming on LADO 0.43.0:
  ```
  Without the copy (removed by hand) it stays on the new version and says so in the
  result (`rollback_failed`), instead of installing a version that cannot open the
  database.
- **Going back to a version with an older schema is one command**:
  ```
  $ lado update 0.42.0
  LADO 0.43.0 -> 0.42.0 (PyPI, released 2026-10-15)
  Installed with uv: uv tool install lado==0.42.0
  lado: WARNING: LADO 0.42.0 knows lado.db up to schema 31; lado.db has schema 35.
    lado.db goes back to /home/me/.lado/backups/lado.db.schema-31, made 2026-10-20 14:03
    by the upgrade from schema 31. Everything LADO recorded since then is lost: sessions,
    runs, gates, messages, projects. Repositories, worktrees and project folders stay on disk.
    Sessions not in that copy are not started again: web2
  Restarts:
    session app  (/home/me/workspace/app)  supervisor idle; no open runs
    session web2  (/home/me/workspace/web2)  supervisor idle; no open runs
  ...
  Update? [y/N] y
  Stopping session app... stopped
  Stopping session web2... stopped
  Upgrading: uv tool install lado==0.42.0
  Restored lado.db from /home/me/.lado/backups/lado.db.schema-31 (schema 31)
  Resuming on LADO 0.42.0:
  LADO 0.42.0 is ready.
  ```
- **It refuses before stopping anything** when it cannot go back:
  ```
  lado: LADO 0.42.0 needs lado.db at schema 31, and lado.db has schema 36; /home/me/.lado/backups holds no lado.db.schema-31 to go back to (docs/install.md, Going back to an older version); nothing was stopped
  lado: cannot learn which lado.db schema LADO 0.42.0 needs: <urlopen error ...>; nothing was stopped
  ```
- **An older version of the same schema** (0.43.1 → 0.43.0) goes as before, no warning.

## How LADO knows the old version's schema

From the old version's own wheel on PyPI: `lado update` downloads
`lado-X-py3-none-any.whl` (about 1.2 MB, its sha256 from PyPI's index) and reads
`SCHEMA_VERSION` from its `lado/state.py`. There is no table "version → schema" in the
code: the release is the only source of truth. It happens only when going back to an
older version, with a database.

## What was decided with the human

- #1434: one copy, the migration's; `lado update` makes none and cleans nothing; its
  rollback uses `schema-<N>`; an update to an older schema puts the copy back itself,
  warning before the install.
- #1457 (all five recommendations accepted):
  1. the schema of X from X's wheel on PyPI; a failure refuses before anything stops;
  2. the warning is part of the plan; one `Update? [y/N]` (or `--yes`) is the consent;
  3. sessions the copy lacks are not started again on X, and are named; when X itself
     then fails, LADO returns to the version before, which migrates the restored copy
     again (the loss already agreed to);
  4. no copy of X's schema: a refusal before anything stops; no `--force`;
  5. a rollback that needs the copy and lacks it keeps the new version installed and
     ends `rollback_failed`.
- Out of scope: two schema hops (one copy is kept), Docker's way back (manual, as
  before), the web UI (it never goes back), deleting old `lado.db.<version>` files.

## Release candidates (`scripts/rc_check.py`)

`upgrade` keeps in `~/.lado-rc/lado.db.<final>` a copy of the migration's
`backups/lado.db.schema-<the final's schema>`, only when the RC moved the schema (it
runs `lado ls` once after the update so the migration has happened). `rollback` puts it
back into `backups/` and runs `lado update <final>`, which warns, asks and restores.

## Manual check (the lead, on a test home)

Before anything: in the run's worktree on its branch; `env | grep LADO_` and `unset`
every variable found. The branch still says version 0.42.0, so it runs from a scratch
clone whose `pyproject.toml` says `0.43.0.dev0` (never committed); `LADO_UPDATE_PREFIX`
points the branch's `lado update` at the uv tool install of 0.42.0, whose installer it
then uses.

```bash
export LADO_HOME=$(mktemp -d) LADO_REPOS=$(mktemp -d) LADO_TMUX_SOCKET=lado-s9 LADO_TELEMETRY=0
export UV_TOOL_DIR=$(mktemp -d) UV_TOOL_BIN_DIR=$(mktemp -d)
B=$(mktemp -d)/lado && git clone -q . "$B" && git -C "$B" checkout -q <the branch's commit>
sed -i.bak 's/^version = "0.42.0"/version = "0.43.0.dev0"/' "$B/pyproject.toml"
uv tool install lado==0.42.0
OLD="$UV_TOOL_BIN_DIR/lado"; NEW="uv run --project $B lado"
git init -q "$LADO_REPOS/app" && git -C "$LADO_REPOS/app" commit -q --allow-empty -m init
$OLD start "$LADO_REPOS/app" --name app --no-attach; ls "$LADO_HOME/backups" 2>/dev/null
#   expected: no backups/ (or an empty one)
$OLD stop --all
$NEW ls; ls "$LADO_HOME/backups"
#   expected: "upgraded lado.db from schema 31 to 35"; backups/ holds lado.db.schema-31 only
$NEW start "$LADO_REPOS/app" --name app --no-attach
git init -q "$LADO_REPOS/web2" && git -C "$LADO_REPOS/web2" commit -q --allow-empty -m init
$NEW start "$LADO_REPOS/web2" --name web2 --no-attach
LADO_UPDATE_PREFIX="$UV_TOOL_DIR/lado" $NEW update 0.42.0
#   expected: the warning names lado.db.schema-31 and its time, and web2 as not started
#   again; answer y; "Restored lado.db from .../lado.db.schema-31 (schema 31)";
#   "LADO 0.42.0 is ready."
$OLD --version; $OLD ls; ls "$LADO_HOME/backups"
#   expected: lado 0.42.0; session app listed and running, no web2;
#   backups/ holds lado.db.schema-31 only
$OLD stop --all; $NEW ls
#   expected: the branch migrates 31 -> 35 again and writes lado.db.schema-31 anew
$NEW start "$LADO_REPOS/app" --name app --no-attach
rm "$LADO_HOME/backups/lado.db.schema-31"; LADO_UPDATE_PREFIX="$UV_TOOL_DIR/lado" $NEW update 0.42.0
#   expected: refused, "holds no lado.db.schema-31 to go back to"; nothing was stopped
#   ($NEW ls shows app running)
tmux -L lado-s9 kill-server
unset LADO_HOME LADO_REPOS LADO_TMUX_SOCKET LADO_TELEMETRY UV_TOOL_DIR UV_TOOL_BIN_DIR B OLD NEW
```
