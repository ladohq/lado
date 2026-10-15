## Context

`state.migrate` is the only code that applies `MIGRATIONS`, in one `BEGIN IMMEDIATE`
transaction. Its callers: `runtime.migrate_if_safe` (the CLI before each command but
`doctor`, `mcp`, `hook`, `loop`, `stop`, `telemetry`, `uninstall`, `bug-report`) and
`runtime.stop_all` / `stop_session`'s migration path (`lado stop`, `lado uninstall`).
`self_update._back_up` copies `lado.db` with SQLite's backup API (`self_update.restore`) to
`backups/lado.db.<old LADO version>` and deletes every other file there.

## Decisions

**D1. The backup is taken in `state.migrate`.** It is the one place that applies the
migrations, so every path gets it with no caller to forget (one source of truth). It is
taken only when there is something to migrate (the version read inside the write lock is
in `MIGRATIONS`), before the first step; a `lado.db` at the current schema, or none, makes
no backup. The copy goes by SQLite's backup API (as `self_update.restore`; the function
moves to `state.py` or a small shared helper, `self_update` keeps using it), never a file
copy: `lado.db` runs in WAL mode.

**D2. Name and kept files.** `backups/lado.db.schema-<N>`, N the version before. Written
to `<name>.tmp` and renamed, as `_back_up` does. After the rename every other
`lado.db.schema-*` is removed (one that cannot be removed stays: the backup is written, so
it does not stop the migration); `lado.db.<version>` files of `lado update` are left alone
(its rollback and `scripts/rc_check.py` read them). `self_update._back_up` keeps deleting
every other file, as today.

**D3. A backup that fails stops the migration.** Nothing is migrated; `state.migrate`
raises an error that names the backup's path and the reason; the caller turns it into a
`LadoError` (exit 1).

**D4. The result.** `state.migrate` returns what it did (versions before and after, the
backup's path) instead of the new version alone; `runtime` prints the line on stderr. A
migration that fails (any exception of a step; the transaction rolls back) is raised as an
error carrying both versions and the backup; `runtime` gives the message, with the way
back chosen by `update.in_container()` (`LADO_IMAGE=lado:previous docker compose up -d`
there, naming the compose header that keeps that name, D5; `install the LADO you had
before` elsewhere), and `lado bug-report`. The underlying exception is kept in the error
journal (`telemetry.record`, `where` the command's) by `cli.main`, which knows the command,
since it is LADO's own bug; the terminal gets no traceback.

**D5. The way back in the compose header.** `docker compose pull` gives the image's name to
the new image, and Docker's containerd image store (Docker Desktop's default) then removes
the old one: no `docker image ls` finds it afterwards (checked with a local registry, a
pulled image as well as a built one). So the header first says to keep a name before the
update: `docker tag "$(docker compose images -q lado)" lado:previous`, then `docker compose
pull && docker compose up -d`. The way back uses that name: `docker compose down`;
`LADO_IMAGE=lado:previous docker compose run --rm lado sh -c 'cd ~/.lado && rm -f
lado.db-wal lado.db-shm && cp backups/lado.db.schema-<N> lado.db'`; `LADO_IMAGE=lado:previous
docker compose up -d` (after a failed migration the last alone), and says to keep
`LADO_IMAGE=lado:previous` set (in `.env`) until the next update, removed before it.
LADO's own update hint in a container, `update.CONTAINER_UPDATE` (`lado ls`, `lado
doctor`, `lado update`'s refusal, the System panel's `by_hand`), is the header's two update
commands joined by `&&`, so whoever updates by LADO's word keeps `lado:previous` too; a
test holds both the same. The container test runs
these commands, the tag of this run's prefix in place of `lado:previous` and the image
under test as the one kept, and checks the schema of `lado.db` and the image that runs.

**D6. Container tests prepare the old database on the host.** The test makes a `lado.db`
with a stopped session in a temporary `LADO_HOME` by the host's own `lado.state`, takes it
back one schema with `tests/agent_helpers.previous_schema`, and copies it into a fresh home
volume before the container starts (a helper in `container_helpers.py`). A migration that
fails is made by a database at the schema before whose last step's change is there
already (e.g. `sessions.title` present at schema 27: `ADD COLUMN` fails). No image of an
earlier version is pulled: none is published.

## Risks

- A large `lado.db` makes the first start after an update slower by one copy. Accepted.
- `previous_schema` asserts the last migration's shape: the container test follows it,
  as the other tests of migrations do.
