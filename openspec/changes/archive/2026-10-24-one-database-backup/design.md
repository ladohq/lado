## Context

`self_update._Update` (the update of the CLI and the UI alike) stops the sessions and the
UI server, `_back_up`s lado.db to `backups/lado.db.<old version>` (deleting every other
file of `backups/`), runs the installer, checks `--version`, and resumes with the
installed binary's public commands. It rolls back only when the new version is bad (a
wrong `--version`, or the UI server does not come up on it), and `_roll_back` restores its
own copy when `state.schema_version()` differs from the schema it read from that copy.

The migration happens later and elsewhere: the new version's `lado start` / `lado ui`
(any CLI command with no session running, `runtime.migrate_if_safe`) calls
`state.migrate`, which writes `backups/lado.db.schema-<N>` first and removes the other
`lado.db.schema-*`. So by the time a rollback needs a copy of the old schema, the
migration has written one; the update's copy is redundant, and its clean-up deletes the
migration's (`lado update 0.42.0` from 0.43.0 loses `lado.db.schema-31`).

A downgrade (`lado update X`, X older) installs X onto a `lado.db` X may not know:
`state.connect` of X raises `SchemaError` ("made by a newer LADO"). Today the plan only
warns "an older LADO may refuse lado.db", and the guide copies the backup by hand.

The human's decisions: #1434 (one copy, the migration's; the update's rollback uses it; a
downgrade puts it back itself, warning first) and #1457 (the five recommendations below,
D2–D6, accepted as proposed).

## Goals / Non-Goals

Goals: `lado update` touches nothing in `backups/`; its rollback restores the migration's
copy; `lado update X` to an older schema warns, refuses without a copy, and restores it;
`rc_check.py` on the same single copy; the documents true to it.

Non-goals: see the proposal's Out of scope (two schema hops, Docker, the UI, old
`lado.db.<version>` files, a forced start from nothing, LAD-140/141).

The plan with each task's tests: `docs/superpowers/plans/2026-10-24-one-database-backup.md`.
The human's view: `docs/superpowers/specs/2026-10-24-one-database-backup-design.md`.

## Decisions

**D1. `_back_up` goes; the update reads only the schema.** `_Update` keeps `self.schema =
state.schema_version()` read before the installer (after the sessions and the server are
stopped, so nothing writes it then) and no `self.backup`. `backups()` in `self_update`
stays a name for `state.backups()`, used to find the copy. The step "backs up lado.db" of
the update's log goes; nothing in `backups/` is written, renamed or removed. *Why:* the
root cause is two owners of one folder; the migration is the only one that writes there.

**D2. X's schema comes from X's wheel on the index (#1457, 1).** `update.release_schema(
data, version) -> int`: from the index's `releases[version]` it takes the not-yanked file
whose `packagetype` is `bdist_wheel` and filename ends `-py3-none-any.whl`, downloads its
`url` (urllib, `INDEX_TIMEOUT`; a `file://` URL works too, which the tests use through
`LADO_UPDATE_INDEX`), checks `digests.sha256`, opens it with `zipfile` and reads
`^SCHEMA_VERSION = (\d+)$` from `lado/state.py`. Any failure (no such file, network,
digest, no match) is a `ValueError`/`OSError` with the reason. It runs only for a
downgrade with a `lado.db` (AC-6). Options weighed:
- (a) the wheel: one source of truth, the release itself; works for every past release
  (0.42.0 checked: 31); costs one ~1.2 MB download per downgrade.
- (b) a table version → schema in LADO's code: a second source of truth that each release
  must extend by hand and that drifts; against AGENTS.md's "One source of truth".
- (c) install X and see whether it refuses: no warning and no refusal before the install,
  which the brief requires.
Held against the roadmap: a release's wheel stays the way LADO is shipped (PyPI, `uv
tool`/`pipx`); the image does not run `lado update` at all. No provider is involved
(neutral core untouched).

**D3. The plan carries the way back (#1457, 2).** `self_update.plan(to, index=None)`:
when `to` is older than this LADO and `lado.db` exists, it calls `release_schema` and,
when S < M, builds `Plan.restore = Restore(copy, schema, made, missing)` (the copy's path,
S, its mtime, the planned running sessions whose names the copy's `sessions` table lacks,
read with a read-only connection). A refusal (D5) is a `runtime.LadoError` raised by
`plan`, before anything stops; the CLI prints it as every refusal. `cli._update` passes
its index. `print_plan` replaces the line "an older LADO may refuse lado.db" with the
warning of the spec when `restore` is set and prints nothing about lado.db otherwise. The
UI's `latest_plan` never downgrades and passes no index; `UpdatePlan.downgrade` stays.

**D4. One consent (#1457, 2).** The warning is part of the plan the human answers with
`Update? [y/N]`; `--yes` is the same consent (scripts, `rc_check.py`, the UI's detached
process). No second question. *Why:* the plan is already the consent of everything the
update does; a second prompt would break `--yes` without making the loss clearer.

**D5. No copy, no way back (#1457, 4).** S < M without `backups/lado.db.schema-<S>`
(no migration, a folder cleaned by hand, two migrations since) refuses with the spec's
text; no `--force`. Unknown S refuses too (D2): no silent "maybe".

**D6. Sessions the copy lacks are not resumed (#1457, 3).** After the restore those
sessions do not exist in `lado.db`; `lado start <repo> --name <s>` of X would make each
anew. `_Update.run` resumes `[s for s in stopped if s.name not in restore.missing]`;
`update.json`'s pending sessions keep all names, which `unfinished()` then ignores as they
are not in `lado.db`. Their repositories and worktrees stay on disk.

**D7. The restore's place in the update.** After the installer and the `--version`
check of X, before the resume: `restore(copy, live)` (`state.copy_db`, SQLite's backup
API, the same as the rollback's, which needs no removal of `-wal`/`-shm`: SQLite writes
through the target's own WAL; the existing test with another connection holding a WAL
frame covers it), then `state.schema_version() == S` checked. An `sqlite3.Error`, or
another schema after it, goes to `_roll_back` with lado.db as it was (the backup API
writes in one step). The result's `database` is `restored`; the line `Restored lado.db
from <path> (schema <S>)` is said.

**D8. When the rollback restores.** `_roll_back` restores only when the live schema is
newer than `self.schema` (not "differs"). After a downgrade's own restore the live schema
is older (S < M = `self.schema`): the version before is reinstalled and migrates the
restored copy again on resume; the loss is the one the human consented to (#1457, 3).

**D9. The rollback checks its copy first (#1457, 5).** First thing in `_roll_back`: when
the live schema is newer than `self.schema` and `backups/lado.db.schema-<self.schema>` is
missing, it ends `rollback_failed` with the spec's reason, stops nothing and reinstalls
nothing: the new version can open its database, the old one could not. A `self.schema`
of None (no lado.db before) never restores.

**D10. `rc_check.py upgrade` keeps the migration's copy.** It reads the schema before
`lado update` (read-only), and after it runs `lado ls` once (the CLI migrates with no
session running; with sessions resumed the migration happened already; a refusal is only
printed). From a final, when the schema moved and `backups/lado.db.schema-<before>`
exists, `_copy` keeps it as `~/.lado-rc/lado.db.<final>` (the name keeps the final's
version, which `rollback` reads; the schema is inside the file). When the schema did not
move, nothing is kept and it says `lado update <final>` alone goes back. For 0.42.0 →
0.43.0rc1 the update is 0.42.0's code, which still writes `lado.db.0.42.0` and deletes
the rest before the installer; the RC's migration writes `lado.db.schema-31` after it, so
the script finds it all the same.

**D11. `rc_check.py rollback` leaves the restore to `lado update`.** After `lado stop
--all` and `lado server stop`, when the plan restores, it writes the kept copy into
`backups/lado.db.schema-<copy schema>` (`.tmp` beside it, then a rename, over a file of
that name; other files stay), then runs `lado update <final>`, which warns, asks and
restores (D3, D7). `_restore` goes; the check of lado.db's schema after it stays. It
starts again only the planned sessions the copy has (as D6). *Why:* one restoring path,
the one users run.

**D12. Leftover `lado.db.<version>` files stay.** A `lado update` of 0.42.x or older
left one in `backups/`; nothing removes it now, the migration keeps files of other names
(spec schema-migration), and `docs/install.md` says it may be removed by hand. *Why:*
nothing deletes what it did not write.

**D13. Version.** Inside 0.43.0 (unreleased): already a minor (a migration, CLI
commands). CHANGELOG.md: the Improved item "The guide says how to go back from 0.43.0 to
0.42.0" is rewritten (no copying out), and a Fixed item says `lado update` no longer
deletes the migration's backup.

## Risks / Trade-offs

- A downgrade now needs PyPI's file host as well as its JSON: offline it refuses (D2),
  where it used to install and let X refuse. The refusal names why.
- The copy may be old (the last migration's): the warning gives its time, so the human
  sees how much is lost before answering.
- `SCHEMA_VERSION = N` as a line of `lado/state.py` becomes something the update reads
  from older releases: a later rename of it breaks downgrades to that later release, not
  to the ones before. The constant's comment says so (task 1.1).
