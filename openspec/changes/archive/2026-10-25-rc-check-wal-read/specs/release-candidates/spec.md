## ADDED Requirements

### Requirement: rc_check reads a database no LADO holds

`scripts/rc_check.py` SHALL read `lado.db` and the copy `~/.lado-rc/lado.db.<final>`
with an ordinary SQLite connection that refuses writes (`PRAGMA query_only = ON`), never
with `mode=ro`, so that a database in WAL mode is read in any state: held by a running
LADO (its WAL read too), or held by no process and without its `-wal` and `-shm` files.
After the script has read a database no process holds, no `-wal` or `-shm` file of it
SHALL be left beside it.

#### Scenario: a write through the script's connection is refused
- **WHEN** the script's connection to the kept copy is asked to delete its sessions
- **THEN** SQLite refuses it as read-only, and the copy keeps its sessions

#### Scenario: upgrade from a final that no process holds
- **WHEN** `lado.db` is in WAL mode with no `-wal` or `-shm` beside it, and the human runs
  `upgrade 0.38.0rc1`
- **THEN** the script reads its schema without an error and goes on to `lado update`

#### Scenario: rollback with the kept copy and lado.db at rest
- **WHEN** `lado.db` and `~/.lado-rc/lado.db.0.37.1` are both in WAL mode with no `-wal`
  or `-shm` beside them, and the human runs `rollback`
- **THEN** the plan names both schemas and the sessions, and `~/.lado-rc/` holds only
  `lado.db.0.37.1`

## MODIFIED Requirements

### Requirement: upgrade migrates lado.db before it keeps the copy

`upgrade` SHALL read `lado.db`'s schema before `lado update` (reading only; none without a
`lado.db`), and after it, once the RC is installed, run `lado ls` once, so that a
`lado.db` no resumed session migrated is migrated, and its copy written, before the
script looks for it.

#### Scenario: No session ran
- **WHEN** no session runs, the human runs `upgrade 0.38.0rc1`, and 0.38.0rc1 has a newer
  schema
- **THEN** the script's `lado ls` migrates `lado.db`, and `~/.lado-rc/lado.db.0.37.1` is
  a copy of the migration's `backups/lado.db.schema-26`
