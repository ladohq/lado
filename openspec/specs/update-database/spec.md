# update-database Specification

## Purpose
How `lado update` treats `lado.db`: it keeps no copy of its own, its rollback and an update
to a version with an older schema both go back to the migration's copy
`backups/lado.db.schema-<N>`, warning before they lose anything and refusing when the copy
is not there.

## Requirements

### Requirement: lado update keeps no copy of lado.db of its own

`lado update` SHALL write, rename and remove no file in `LADO_HOME/backups/`, whatever its
outcome; the copy of `lado.db` it relies on is the migration's `lado.db.schema-<N>`
(capability schema-migration). Before the installer it SHALL read `lado.db`'s schema
(`PRAGMA user_version`, read-only), or none when there is no `lado.db`.

#### Scenario: An upgrade leaves the folder alone
- **WHEN** `backups/` holds `lado.db.schema-30` and `lado.db.0.42.0`, and `lado update`
  installs a newer version whose start migrates `lado.db` from schema 31
- **THEN** `backups/` holds `lado.db.0.42.0` and `lado.db.schema-31` (the migration's),
  and no file there was written by the update

#### Scenario: A failed installer
- **WHEN** the installer fails
- **THEN** `backups/` is as it was before the update and `lado.db` is kept

### Requirement: The rollback restores the migration's copy

When an update rolls back and `lado.db`'s schema is now newer than before the update, the
rollback SHALL restore `lado.db` from `backups/lado.db.schema-<N>`, N the schema before the
update, by SQLite's backup API, after the old version is reinstalled and checked, keeping
the copy; the result's `database` SHALL be `restored`. When `lado.db`'s schema is the one
before the update, or older, it SHALL restore nothing (`kept`).

#### Scenario: The new version migrated, then failed
- **WHEN** LADO at schema 31 updates, the new version's resume migrates `lado.db` to 35
  (writing `backups/lado.db.schema-31`), and its UI server does not come up
- **THEN** the old version is reinstalled, `lado.db` has schema 31 and the copy's
  content, `backups/lado.db.schema-31` is still there, and the result is `rolled_back`
  with `database` `restored`

#### Scenario: No migration, no restore
- **WHEN** the new version reports another version before anything migrated
- **THEN** the rollback reinstalls the old version and `database` is `kept`

### Requirement: A rollback without the migration's copy keeps the new version

The rollback SHALL look for the copy it needs before it stops, reinstalls or restores
anything. When it is not there the update SHALL change nothing more and end
`rollback_failed` with the reason `<why>; not rolled back: lado.db has schema <M> and
backups/ holds no lado.db.schema-<N> for LADO <old>, so LADO <new> stays installed`, said
on stderr too.

#### Scenario: The copy was removed by hand
- **WHEN** the new version migrated `lado.db` to 35, `backups/lado.db.schema-31` was
  removed, and the new version's UI server does not come up
- **THEN** the new version stays installed, the sessions it resumed keep running, and the
  result is `rollback_failed` naming schema 35 and `lado.db.schema-31`

### Requirement: An update to an older version learns its schema from its wheel

Before it prints its plan, `lado update X` to a version older than this LADO, with a
`lado.db`, SHALL learn X's schema S from the index: the release's `py3-none-any.whl` file,
checked against the index's sha256, whose `lado/state.py` holds `SCHEMA_VERSION = <S>`. An
update to a newer version, or with no `lado.db`, SHALL fetch no wheel.

#### Scenario: The wheel of 0.42.0
- **WHEN** the human runs `lado update 0.42.0` from 0.43.0 with a `lado.db`
- **THEN** LADO fetches `lado-0.42.0-py3-none-any.whl` and reads schema 31 from it

#### Scenario: No lado.db
- **WHEN** there is no `lado.db` and the human runs `lado update 0.42.0`
- **THEN** no wheel is fetched and the plan has no warning about `lado.db`

#### Scenario: An update forward
- **WHEN** the human runs `lado update` to a newer version
- **THEN** no wheel is fetched

### Requirement: The plan of an update to an older schema says what it loses

When S is older than `lado.db`'s schema M and `backups/lado.db.schema-<S>` exists, the
plan SHALL warn on stderr, before `Update? [y/N]`: X, S and M; the copy's path and time
(local, `YYYY-MM-DD HH:MM`); that everything LADO recorded since is lost while
repositories, worktrees and project folders stay; and the planned sessions the copy
lacks, which are not started again. `Update? [y/N]`, or `--yes`, SHALL be the consent.
With S equal to M there SHALL be no warning about `lado.db`.

#### Scenario: Back from 0.43.0 to 0.42.0
- **WHEN** LADO 0.43.0 runs with `lado.db` at schema 35, `backups/lado.db.schema-31`
  exists, sessions `app` (in the copy) and `web2` (made after the migration) run, and the
  human runs `lado update 0.42.0`
- **THEN** stderr has `lado: WARNING: LADO 0.42.0 knows lado.db up to schema 31; lado.db
  has schema 35.`, the copy's path and time, the loss, and `Sessions not in that copy are
  not started again: web2`; it asks `Update? [y/N]`, and nothing is stopped before the
  answer

#### Scenario: An older version of the same schema
- **WHEN** X's wheel holds `SCHEMA_VERSION = 35` and `lado.db` has schema 35
- **THEN** the plan has no warning about `lado.db`, and the update restores nothing

### Requirement: An update to an older schema refuses when it cannot go back

`lado update X` SHALL exit 1 before it stops, installs or writes anything when X's schema
cannot be learned, or when S is older than M and `backups/lado.db.schema-<S>` does not
exist; the message SHALL say why, name `docs/install.md` for the missing copy, and end
with `nothing was stopped`. It SHALL offer no way on without the copy.

#### Scenario: The copy is of another schema
- **WHEN** `lado.db` has schema 36, `backups/` holds only `lado.db.schema-35`, and the
  human runs `lado update 0.42.0` (schema 31)
- **THEN** it exits 1 with `lado: LADO 0.42.0 needs lado.db at schema 31, and lado.db has
  schema 36; <backups> holds no lado.db.schema-31 to go back to (docs/install.md, Going
  back to an older version); nothing was stopped`, and no session is stopped

#### Scenario: PyPI's wheel cannot be read
- **WHEN** the wheel's download fails, its sha256 differs, or it has no `SCHEMA_VERSION`
- **THEN** it exits 1 with `lado: cannot learn which lado.db schema LADO 0.42.0 needs:
  <reason>; nothing was stopped`, and no session is stopped

### Requirement: An update to an older schema puts the copy back after the installer

After the installer and the `--version` check of X, and before it resumes anything, an
update whose plan warned SHALL restore `lado.db` from `backups/lado.db.schema-<S>` by
SQLite's backup API, keeping the copy, say `Restored lado.db from <path> (schema <S>)`,
then resume on X only the planned sessions the copy has, and the UI server when it ran;
the result's `database` SHALL be `restored`.

#### Scenario: The old version starts with its session
- **WHEN** the human answers `y` in the scenario Back from 0.43.0 to 0.42.0
- **THEN** LADO is 0.42.0, `lado.db` has schema 31 and the copy's content,
  `backups/lado.db.schema-31` is still there, session `app` runs on 0.42.0, `web2` is not
  started, and the result is `ok` with `database` `restored`

### Requirement: A failed way back to an older schema returns to the version before

When the restore fails, the update SHALL roll back to the version before with `lado.db`
as it was. When X fails after the restore (its UI server does not come up), the rollback
SHALL reinstall the version before and restore nothing: that version migrates the
restored database again when it resumes.

#### Scenario: The old version's UI server does not come up
- **WHEN** after the restore X's UI server does not come up
- **THEN** the version before is reinstalled, nothing is restored, and its resume
  migrates `lado.db` from schema 31 again

#### Scenario: The restore fails
- **WHEN** SQLite's backup into `lado.db` fails
- **THEN** the version before is reinstalled, `lado.db` keeps schema 35, and the result
  is `rolled_back` with `database` `kept`
