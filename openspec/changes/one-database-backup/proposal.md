Task: LAD-143

## Why

Step S9 of the epic LAD-116 (`docs/epics/lad-116/plan.md`), the last before the readiness
check and 0.43.0rc1. 0.43.0 moves `lado.db` from schema 31 to 35, so the way back to 0.42.0
must work.

LADO keeps two kinds of database copies in `LADO_HOME/backups/`:

- `lado update` writes `lado.db.<the version before>` before the installer and deletes
  every other file of the folder (`self_update._Update._back_up`);
- a migration writes `lado.db.schema-<N>` before its first step (`state._back_up`,
  LAD-71), the only copy in a container, where `lado update` is refused.

The update's copy is restored only when the schema moved, and the schema moves only by a
migration, which has then already written the same database as `lado.db.schema-<N>`: the
update's copy is redundant. Worse, it deletes the migration's: going back from 0.43.0 to
0.42.0 with `lado update 0.42.0` removes `lado.db.schema-31`, and 0.42.0 then refuses the
database at schema 35. The root cause is that two places own one folder and one of them
deletes what it did not write. The human decided (#1434): one copy, the migration's.

## What Changes

- **No copy of its own.** `lado update` writes no copy of `lado.db` and removes nothing in
  `LADO_HOME/backups/`; it reads `lado.db`'s schema before the installer.
- **Its rollback uses the migration's copy.** When the new version moved the schema, the
  rollback restores `backups/lado.db.schema-<N>`, N the schema before the update. It checks
  the copy before it stops or reinstalls anything: without it the new version stays
  installed, the result is `rollback_failed` and its reason names the schema and the
  missing copy.
- **An update to a version with an older schema puts the copy back itself.**
  - Before it stops anything, `lado update X` to an older X learns X's schema from X's
    wheel on PyPI (`SCHEMA_VERSION` in its `lado/state.py`; the file's URL and sha256 come
    from the index `lado update` already reads).
  - When X's schema is older than `lado.db`'s, the plan warns that `lado.db` goes back to
    `backups/lado.db.schema-<X's schema>` and when that copy was made, that everything
    recorded since is lost, and which running sessions the copy lacks; the usual
    `Update? [y/N]` (or `--yes`) confirms it.
  - With no copy of X's schema, or when X's schema cannot be learned, it refuses before it
    stops anything.
  - After the installer and the version check it restores the copy by SQLite's backup
    API, then resumes only the sessions the copy has.
- **`scripts/rc_check.py`.** `upgrade` keeps a copy of the migration's
  `lado.db.schema-<N>` (not of `lado.db.<final>`), and only when the RC moved the schema.
  `rollback` puts that copy back into `backups/` and leaves the restore to the RC's own
  `lado update <final>`.
- **Documents.** `docs/install.md` (What it does, When something goes wrong, Going back to
  an older version: no copying by hand on the `lado update` path; the Docker path as it
  was), `docs/design/modules.md`, `docs/release.md` 4.4, CHANGELOG.md under
  `## 0.43.0 (unreleased)`.

## Scope

In: `src/lado/self_update.py`, `src/lado/update.py` (the schema of a release),
`scripts/rc_check.py`, their tests (unit, integration), the documents above and the specs
`update-database` (new), `schema-migration`, `release-candidates`.

## Out of scope

- A way back across two schema migrations: one copy is kept, the last migration's, as
  today (the human, #1434). An update to a version whose schema has no copy refuses.
- Automatic rollback in Docker: an old image knows nothing of a newer schema; the way
  stays the manual one of `docs/install.md`.
- The web UI: it updates only to a newer version (`latest_plan`), which never restores;
  its plan's `downgrade` line stays.
- Removing `lado.db.<version>` files an earlier `lado update` left in `backups/`: nothing
  deletes what it did not write; `docs/install.md` says they may be removed by hand.
- A `--force` or a start from an empty database when the copy is missing: the refusal
  names the guide instead; losing everything stays a by-hand step.
- LAD-140 and LAD-141: tasks of their own.

## Acceptance criteria

- AC-1 `lado update` writes, renames and removes no file in `LADO_HOME/backups/`
  (upgrade, failed installer, rollback, downgrade alike).
- AC-2 A rollback after the new version moved the schema restores
  `backups/lado.db.schema-<N>`; without that copy the new version stays installed and the
  result is `rollback_failed` with a reason naming the schema and the copy.
- AC-3 `lado update X` to an older X whose schema is older than `lado.db`'s prints the
  warning (the copy, its time, what is lost, the sessions not in the copy) before it asks
  or stops anything.
- AC-4 Without `backups/lado.db.schema-<X's schema>`, or when X's schema cannot be read
  from its wheel, `lado update X` refuses before it stops anything, nothing changed.
- AC-5 After X is installed and checked, `lado.db` holds the copy's content and schema,
  the copy stays in `backups/`, the sessions the copy has resume on X and the others do
  not, and the result's `database` is `restored`.
- AC-6 An update to an older version of the same schema, or with no `lado.db`, restores
  nothing and fetches no wheel.
- AC-7 `rc_check.py upgrade` keeps `~/.lado-rc/lado.db.<final>` from the migration's copy
  when the RC moved the schema; `rollback` goes back with `lado update <final>` restoring
  it; their tests are green.
- AC-8 `docs/install.md` "Going back to an older version" has no copying by hand for the
  `lado update` path; the Docker path is unchanged.
- AC-9 `make lint`, `make test`, the changed integration files with `-m integration`,
  `openspec validate --specs --strict`, a trial archive, CI green.

## Impact

- Code: `self_update.py`, `update.py`, `scripts/rc_check.py`; `cli.py` passes the index to
  the plan. No schema migration, no MCP or API change; agents' protocol untouched.
- Version: within 0.43.0 (unreleased, already a minor: CLI behaviour and a migration).
