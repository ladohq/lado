## ADDED Requirements

### Requirement: A new image starts on an old home volume

A container of LADO's image whose home volume holds a `lado.db` of an older schema SHALL
migrate it at its start with the backup the capability `schema-migration` describes, and
`docker logs` SHALL show the upgrade line, or, when the migration fails, its message.
`docker/compose.yaml`'s header SHALL say how to keep the image a container runs before an
update, since `docker compose pull` gives its name to the new image and Docker may then
remove the old one: tag it `lado:previous` (`docker tag "$(docker compose images -q lado)"
lado:previous`). It SHALL give the steps that go back to that image after a migration that
succeeded: stop the container, put the backup in place of `lado.db` (with its `-wal` and
`-shm` removed) with `lado:previous`, and start `lado:previous`.

#### Scenario: The migration on start
- **WHEN** the image starts on a home volume whose `lado.db` has the schema before this
  LADO's and holds a stopped session
- **THEN** `/api/health` answers `ok`, `lado.db` has this LADO's schema,
  `~/.lado/backups/lado.db.schema-<the schema before>` exists, `docker logs` has the
  upgrade line, and `lado ls` in the container lists the session

#### Scenario: A migration that fails
- **WHEN** the image starts on a home volume whose `lado.db` cannot be migrated
- **THEN** `docker logs` has the message of a failed migration with `LADO_IMAGE=lado:previous
  docker compose up -d` and no traceback, and `lado.db` keeps its schema

#### Scenario: The image before keeps a name
- **WHEN** the compose header's command to keep the image runs while the container runs
- **THEN** `lado:previous` names the image the container runs

#### Scenario: Back to the backup
- **WHEN** after the migration on start the compose header's steps run
- **THEN** `lado.db` has the schema before again, and the container runs `lado:previous`
