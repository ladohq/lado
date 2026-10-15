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

## MODIFIED Requirements

### Requirement: lado update refuses in a container at once

In a container `lado update` SHALL refuse before it stops, writes or looks up anything
(no PyPI request, no `update.lock`, no `update.json`, no result, no stopped session or
server), with exit 1 and the one line `lado: LADO runs in a container: a new image updates
it, not lado update; on the host: docker tag "$(docker compose images -q lado)"
lado:previous && docker compose pull && docker compose up -d`, whatever its version
argument and `--yes`. That command (`update.CONTAINER_UPDATE`) SHALL be the update
commands of `docker/compose.yaml`'s header, the image the container runs kept as
`lado:previous` first. Inside an agent the agent's refusal SHALL come first; the
container's refusal SHALL come before the refusal of a running update and the missing
installer.

#### Scenario: The human updates in a container
- **WHEN** the human runs `lado update --yes` in a container where LADO is a uv tool
  install and the UI server runs
- **THEN** it prints the container line on stderr and exits 1, the UI server and every
  session still run, and `update-result.json`, `update.json` and `update.log` are as they
  were

#### Scenario: A named version
- **WHEN** the human runs `lado update 0.36.0` in a container
- **THEN** the same refusal, and PyPI is not asked

#### Scenario: An agent in a container
- **WHEN** an agent runs `lado update` in a container
- **THEN** it gets the agent's refusal

#### Scenario: The same commands as the compose header
- **WHEN** `docker/compose.yaml`'s header says how to update
- **THEN** its two commands joined by `&&` are `update.CONTAINER_UPDATE`

### Requirement: The UI's update refuses in a container

In a container `GET /api/update` SHALL answer `can_update` false, `why_not` `LADO runs in
a container: a new image updates it, not lado update`, `by_hand` the one command `docker
tag "$(docker compose images -q lado)" lado:previous && docker compose pull && docker
compose up -d`, and `container` true (false outside one); `POST /api/update` SHALL answer
409 with that reason and start nothing. The System panel SHALL show a grey `container`
pill beside `LADO <version>` in its head (its tooltip: LADO runs in a container and a new
image updates it), and, when a newer LADO is out, an Update block with no **Update…**
button, the reason, and the command under `On the host:` with its Copy button.

#### Scenario: A newer LADO is out in a container
- **WHEN** the System panel opens in a container and 0.39.0 is available
- **THEN** the head reads `LADO 0.38.0` with a `container` pill, and the Update block reads
  `0.39.0 is out`, the reason, `On the host:` and `docker tag "$(docker compose images -q
  lado)" lado:previous && docker compose pull && docker compose up -d`, and has no
  Update… button

#### Scenario: The latest version in a container
- **WHEN** the System panel opens in a container and nothing newer is out
- **THEN** the head has the `container` pill and there is no Update block

#### Scenario: A start of the update is refused
- **WHEN** a client posts `/api/update` in a container
- **THEN** it gets 409 with the reason, and no `lado update` process is started

#### Scenario: Outside a container
- **WHEN** the System panel opens without `LADO_CONTAINER`
- **THEN** it shows no `container` pill and `UpdateInfo.container` is false

### Requirement: lado doctor and the report say LADO runs in a container

In a container `lado doctor`'s LADO line SHALL end with `, in a container`, and the line
that a newer LADO is out (`update.available_line`, shown by `lado ls` and as
`lado doctor`'s hint) SHALL name `docker tag "$(docker compose images -q lado)"
lado:previous && docker compose pull && docker compose up -d` instead of `lado update`.
The system report (`doctor.report`: the System panel's copy and `lado bug-report`) SHALL
name the installer as `(<installer>, in a container)`.

#### Scenario: The doctor on the latest version
- **WHEN** LADO 0.38.0 runs `lado doctor` in a container and nothing newer is out
- **THEN** it prints `[ok  ] LADO: 0.38.0, the latest version, in a container`

#### Scenario: The doctor with a newer LADO out
- **WHEN** LADO 0.38.0 runs `lado doctor` in a container and 0.39.0 is available
- **THEN** it prints `[warn] LADO: 0.38.0, in a container` with the hint `LADO 0.39.0 is
  available: docker tag "$(docker compose images -q lado)" lado:previous && docker compose
  pull && docker compose up -d`, and `lado ls` ends with that same line

#### Scenario: The report for an issue
- **WHEN** the human copies the system info in a container where LADO is a uv tool install
- **THEN** its LADO line reads `- LADO 0.38.0 (uv tool, in a container), Python ...`
