## ADDED Requirements

### Requirement: LADO backs lado.db up before it upgrades the schema

Before LADO upgrades `lado.db` to a newer schema, by any command that migrates it, it SHALL
copy `lado.db` by SQLite's backup API to `LADO_HOME/backups/lado.db.schema-<N>`, N the
schema version before the migration, and then remove every other `lado.db.schema-*` file
of that folder (one it cannot remove stays, and the migration goes on), leaving files of other names (`lado update`'s `lado.db.<version>`) as they
are. Once the migration is done the command SHALL print on stderr `lado: upgraded lado.db
from schema <N> to <M>; its backup is <path>`. A `lado.db` at the current schema, or no
`lado.db`, SHALL make no backup and no line.

#### Scenario: A LADO upgraded by hand
- **WHEN** `lado.db` has schema 27, this LADO's schema is 28, and the human runs `lado ls`
- **THEN** `lado.db` has schema 28, `backups/lado.db.schema-27` holds the database as it
  was at schema 27, and stderr has `lado: upgraded lado.db from schema 27 to 28; its
  backup is <LADO_HOME>/backups/lado.db.schema-27`

#### Scenario: The update's backup stays
- **WHEN** `backups/` holds `lado.db.0.38.0` and `lado.db.schema-26`, and a command
  migrates `lado.db` from schema 27
- **THEN** `backups/` holds `lado.db.0.38.0` and `lado.db.schema-27`

#### Scenario: Nothing to migrate
- **WHEN** `lado.db` has the current schema and the human runs `lado ls`
- **THEN** no file is written to `backups/` and stderr has no upgrade line

#### Scenario: The stop's migration
- **WHEN** `lado stop --all` migrates an older `lado.db`
- **THEN** the backup of the older schema is in `backups/` and the line is printed

### Requirement: No backup, no migration

When the backup cannot be written, LADO SHALL NOT migrate: `lado.db` SHALL stay at its
schema, and the command SHALL exit 1 with `lado: could not back up lado.db to <path>
before upgrading it from schema <N> to <M>: <reason>; nothing was changed`.

#### Scenario: backups is not writable
- **WHEN** `LADO_HOME/backups` cannot be written and a command would migrate `lado.db`
  from schema 27
- **THEN** the command exits 1 with that message, and `lado.db` still has schema 27

### Requirement: A failed migration says how to go back

When a step of the migration fails, LADO SHALL leave `lado.db` as it was (the migration is
one transaction), keep the error in its error journal, and exit 1 with one message on
stderr and no traceback: `lado: could not upgrade lado.db from schema <N> to <M>: <error>.
lado.db is unchanged; its backup is <path>.`, then the way back, and `Report it with lado
bug-report.` The way back SHALL be, in a container (`update.in_container`), `To go back,
run the image you had before, which the header of docker/compose.yaml has you keep as
lado:previous: LADO_IMAGE=lado:previous docker compose up -d`, and elsewhere `To go back,
install the LADO you had before.`

#### Scenario: Outside a container
- **WHEN** a migration step fails while `lado ls` migrates `lado.db` from schema 27
- **THEN** `lado ls` exits 1, stderr has the message with `install the LADO you had
  before`, `lado.db` still has schema 27, `backups/lado.db.schema-27` exists, and
  `errors.jsonl` has the error

#### Scenario: In a container
- **WHEN** the same happens with `LADO_CONTAINER=1`
- **THEN** the message names the header of `docker/compose.yaml` and `LADO_IMAGE=lado:previous
  docker compose up -d`
