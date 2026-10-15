## ADDED Requirements

### Requirement: A new image starts on an old home volume

A container of LADO's image whose home volume holds a `lado.db` of an older schema SHALL
migrate it at its start with the backup the capability `schema-migration` describes, and
`docker logs` SHALL show the upgrade line, or, when the migration fails, its message.
`docker/compose.yaml`'s header SHALL give the steps that go back to an older image after a
migration that succeeded: stop the container, put the backup in place of `lado.db` (with
its `-wal` and `-shm` removed) with the older image, and start the older image.

#### Scenario: The migration on start
- **WHEN** the image starts on a home volume whose `lado.db` has the schema before this
  LADO's and holds a stopped session
- **THEN** `/api/health` answers `ok`, `lado.db` has this LADO's schema,
  `~/.lado/backups/lado.db.schema-<the schema before>` exists, `docker logs` has the
  upgrade line, and `lado ls` in the container lists the session

#### Scenario: A migration that fails
- **WHEN** the image starts on a home volume whose `lado.db` cannot be migrated
- **THEN** `docker logs` has the message of a failed migration with `LADO_IMAGE=<that
  image> docker compose up -d` and no traceback, and `lado.db` keeps its schema

#### Scenario: Back to the backup
- **WHEN** after the migration on start the compose header's steps run
- **THEN** `lado.db` has the schema before again
