## MODIFIED Requirements

### Requirement: rc_check reads a database no LADO holds

`scripts/rc_check.py` SHALL read `lado.db` and the copy `~/.lado-rc/lado.db.<final>` by
its state: without a `-wal` file beside it or with an empty one, as an immutable
read-only database (`mode=ro&immutable=1`), which creates and changes no file; with a
non-empty one, with an ordinary connection that refuses writes (`PRAGMA query_only = ON`), so that a running LADO's WAL is read too.
Reading a database no process holds SHALL create no `-wal` or `-shm` file beside it, on
any platform.

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

#### Scenario: no side file while the script reads
- **WHEN** the kept copy is in WAL mode with no `-wal` or `-shm` beside it, and the
  script's connection to it is open
- **THEN** no `-wal` or `-shm` file of it exists, before or after the connection closes

#### Scenario: empty side files left by macOS stay as they are
- **WHEN** the kept copy is in WAL mode with an empty `-wal` and a `-shm` beside it, held
  by no process, and the script reads it
- **THEN** it reads the copy's schema and sessions, no other file appears beside it, and
  the `-wal` stays empty and the `-shm` keeps its size

#### Scenario: a running LADO's WAL is read
- **WHEN** another connection holds `lado.db` in WAL mode, with a session written only to
  its WAL, and the script reads `lado.db`
- **THEN** the script sees that session
