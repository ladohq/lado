Task: LAD-71

## Why

A container of LADO's image is updated by `docker compose pull && docker compose up -d`:
the new image starts on the old home volume, and its `lado server` upgrades `lado.db` to
the new schema before it serves (`cli.main` calls `runtime.migrate_if_safe` before every
command; after a container restart tmux is empty, so nothing holds the migration back).
Only `lado update` backs `lado.db` up first (`backups/lado.db.<old version>`), and it is
refused in a container. So when the migration fails, `docker logs` has a traceback and the
container restarts into it again and again; and when the migration succeeds but the new
version is bad, the old image refuses the newer database and there is nothing to go back
to. A LADO upgraded by hand (`uv tool upgrade lado`) has the same gap. Nothing tests it.
This is step T6a of the Docker install plan.

Root cause: the backup belongs to `lado update`, not to the migration; the one place that
applies `MIGRATIONS` (`state.migrate`) neither keeps a copy nor says how to go back.

## What Changes

- **A backup before every migration.** Before `lado.db` is upgraded to a newer schema,
  wherever LADO runs (a container, a uv or pipx install upgraded by hand, `lado update`'s
  new version, `lado stop`'s and `lado uninstall`'s migration), LADO copies it by SQLite's
  backup API to `LADO_HOME/backups/lado.db.schema-<N>`, N the schema before the
  migration, replacing an earlier `lado.db.schema-*`; `lado update`'s own
  `lado.db.<version>` stays as it is. The command says so on stderr: `lado: upgraded
  lado.db from schema N to M; its backup is <path>` (in a container: in `docker logs`).
- **No backup, no migration.** When the backup cannot be written, LADO changes nothing and
  the command exits 1 naming why.
- **A failed migration is named.** The migration is one transaction, so `lado.db` stays as
  it was. The command exits 1 with one message: what failed, that `lado.db` is unchanged,
  where its backup is, and the way back: in a container the image you had before
  (`LADO_IMAGE=lado:previous docker compose up -d`, the name the compose header has you
  keep), elsewhere the LADO you had before; and
  `lado bug-report` to report it. No traceback on the terminal or in `docker logs`; the
  error is kept in the error journal as before.
- **The way back after a migration that succeeded.** `docker/compose.yaml`'s header says
  to keep the running image as `lado:previous` before an update (`docker compose pull`
  moves its name, and Docker may then remove it), and gives the steps that put the backup
  in place with `lado:previous` and start it.
- **Container tests** (layer 7): a home volume with a database of the schema before starts
  on the new image, which migrates it, keeps the backup, serves `/api/health` and lists the
  old session in `lado ls`; a database whose migration fails leaves the message in
  `docker logs` and the database as it was; the compose header's steps put the backup back.

## Scope

Changed: `src/lado/state.py` (`migrate`: the backup and the result), `src/lado/runtime.py`
(`migrate_if_safe` and `stop_all`'s migration: the line, the failure's message),
`docker/compose.yaml` (header); tests `tests/test_state.py` / `tests/test_runtime.py` (or
the files that test `migrate` and `migrate_if_safe`), `tests/container/` (a new test file);
AGENTS.md (Layout: `state.py`'s schema changes, `docker/`), CHANGELOG.md. Capabilities:
new `schema-migration`; `container` gains a requirement. No schema change, no MCP tool, no
CLI option. Version: a feature, so a minor; 0.39.0 is unreleased and a minor already, so
it goes into 0.39.0's notes with no further bump.

## Out of scope

- The old LADO's version in the backup's name (as `lado update` does): a new LADO on an old
  database cannot know which LADO wrote it, only its schema. The human's decision.
- A `lado restore` command: the older image, which needs it, would not have it; the
  compose header's steps do it. The human's decision.
- Migrating without a backup when the backup fails: that is the case this change guards
  against. The human's decision.
- Keeping more than one migration backup: one per schema step taken last is enough to go
  back one image; `lado update` keeps its own as before.
- Stopping and resuming the container's sessions (T6b), publishing the image (T7).
- `docs/research/docker-install-plan.md`: updated by another session's supervisor.

## Impact

- Every LADO that upgrades `lado.db`: one more file in `LADO_HOME/backups/` and one line on
  stderr per migration; a failed migration is a clean exit 1, not a traceback.
- Container users: `docker logs` says what happened at the start, and the compose file
  says how to go back.
- Spec: new `schema-migration`; `container` (a new image on an old home volume).
