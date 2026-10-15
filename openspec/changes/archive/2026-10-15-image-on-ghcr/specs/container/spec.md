## MODIFIED Requirements

### Requirement: lado update refuses in a container at once

In a container `lado update` SHALL refuse before it stops, writes or looks up anything
(no PyPI request, no `update.lock`, no `update.json`, no result, no stopped session or
server), with exit 1 and the one line `lado: LADO runs in a container: a new image updates
it, not lado update`, whatever its version argument and `--yes`; it SHALL name no command
to run on the host (how to update a container is the documentation's). Inside an agent the
agent's refusal SHALL come first; the container's refusal SHALL come before the refusal of
a running update and the missing installer.

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
- **WHEN** `docker/compose.yaml`'s header says how to update and `lado update` refuses in
  a container
- **THEN** the refusal names none of the header's commands, no `docker` command and no
  `lado:previous`: how to update is the header's and the documentation's

### Requirement: The UI's update refuses in a container

In a container `GET /api/update` SHALL answer `can_update` false, `why_not` `LADO runs in
a container: a new image updates it, not lado update`, `by_hand` empty, and `container`
true (false outside one); `POST /api/update` SHALL answer 409 with that reason and start
nothing. The System panel SHALL show a grey `container` pill beside `LADO <version>` in its
head (its tooltip: LADO runs in a container and a new image updates it), and, when a newer
LADO is out, an Update block with the version, What's new, no **Update…** button, the
reason, and no commands.

#### Scenario: A newer LADO is out in a container
- **WHEN** the System panel opens in a container and 0.39.0 is available
- **THEN** the head reads `LADO 0.38.0` with a `container` pill, and the Update block reads
  `0.39.0 is out`, What's new and the reason, and has no Update… button, no `On the
  host:` and no Copy button

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
`lado doctor`'s hint) SHALL read `LADO <version> is available: a new image updates LADO in
a container (ghcr.io/ladohq/lado:<version>)` instead of naming `lado update`. The image's
name SHALL be one constant, `update.IMAGE`, that the Release workflow and
`docker/compose.yaml` publish and pull by (a unit test keeps the three the same). The
system report (`doctor.report`: the System panel's copy and `lado bug-report`) SHALL name
the installer as `(<installer>, in a container)`.

#### Scenario: The doctor on the latest version
- **WHEN** LADO 0.38.0 runs `lado doctor` in a container and nothing newer is out
- **THEN** it prints `[ok  ] LADO: 0.38.0, the latest version, in a container`

#### Scenario: The doctor with a newer LADO out
- **WHEN** LADO 0.38.0 runs `lado doctor` in a container and 0.39.0 is available
- **THEN** it prints `[warn] LADO: 0.38.0, in a container` with the hint `LADO 0.39.0 is
  available: a new image updates LADO in a container (ghcr.io/ladohq/lado:0.39.0)`, and
  `lado ls` ends with that same line

#### Scenario: The report for an issue
- **WHEN** the human copies the system info in a container where LADO is a uv tool install
- **THEN** its LADO line reads `- LADO 0.38.0 (uv tool, in a container), Python ...`

### Requirement: The compose file publishes one port number

`docker/compose.yaml` SHALL run LADO's published image of the version `LADO_VERSION` names,
`ghcr.io/ladohq/lado:${LADO_VERSION}`, unless `LADO_IMAGE` names another image (`lado:local`,
the tests'); without either compose SHALL refuse and name `LADO_VERSION`, and it SHALL
never default to `latest`. It SHALL use one variable, `LADO_PORT` (8765 by default), as
both the server's port in the container and the published one,
`127.0.0.1:${LADO_PORT}:${LADO_PORT}`, so the host's number and the container's are always
the same. It SHALL mount `LADO_PROJECTS`, which is required, at that same path inside the
container and set `LADO_REPOS` to it, and mount the home volume at `/home/lado`, and SHALL
name no container. Its header SHALL say to keep these variables in `.env` next to the file,
and that a second LADO is a folder of its own with a copy of the file and its own `.env`
(`COMPOSE_PROJECT_NAME`, `LADO_PORT`, `LADO_VERSION`, `LADO_PROJECTS`), so it runs beside
the first with a container, a volume and a version of its own.

#### Scenario: Two LADOs on one host
- **WHEN** the human runs `docker compose up -d` in a folder whose `.env` has
  `LADO_VERSION`, and in a second folder whose `.env` adds `COMPOSE_PROJECT_NAME=lado-2`
  and `LADO_PORT=8766`
- **THEN** both run, `/api/health` answers on 8765 and on 8766, and each has its own home
  volume

#### Scenario: No projects folder given
- **WHEN** the human runs `docker compose up -d` without `LADO_PROJECTS`
- **THEN** compose refuses and names `LADO_PROJECTS`

#### Scenario: No version given
- **WHEN** the human runs `docker compose up -d` with neither `LADO_VERSION` nor
  `LADO_IMAGE`
- **THEN** compose refuses and names `LADO_VERSION`

#### Scenario: The published image by its version
- **WHEN** `.env` has `LADO_VERSION=0.39.0` and no `LADO_IMAGE`
- **THEN** `docker compose config` names the image `ghcr.io/ladohq/lado:0.39.0`

#### Scenario: The projects at the host's path
- **WHEN** the human runs `LADO_PROJECTS=/Users/me/projects docker compose up -d`
- **THEN** the container sees the projects at `/Users/me/projects` and `lado doctor` in it
  prints `[ok  ] Repositories folder: /Users/me/projects (LADO_REPOS)`

### Requirement: A new image starts on an old home volume

A container of LADO's image whose home volume holds a `lado.db` of an older schema SHALL
migrate it at its start with the backup the capability `schema-migration` describes, and
`docker logs` SHALL show the upgrade line, or, when the migration fails, its message.
`docker/compose.yaml`'s header SHALL say that an update is a new `LADO_VERSION` in `.env`
followed by `docker compose up -d` (which pulls the image of that version), and that the
image before keeps its version's name, so no name is kept by hand and nothing names
`lado:previous`. It SHALL give the steps that go back after a migration that succeeded:
put the version before back in `.env`, stop the container, put the backup in place of
`lado.db` (with its `-wal` and `-shm` removed) with that image, and start it; after a
migration that failed, the first and the last step alone. The Dockerfile's header SHALL
say the same for `docker run`: the container removed and run again with the other
version's tag on the same home volume.

#### Scenario: The migration on start
- **WHEN** the image starts on a home volume whose `lado.db` has the schema before this
  LADO's and holds a stopped session
- **THEN** `/api/health` answers `ok`, `lado.db` has this LADO's schema,
  `~/.lado/backups/lado.db.schema-<the schema before>` exists, `docker logs` has the
  upgrade line, and `lado ls` in the container lists the session

#### Scenario: A migration that fails
- **WHEN** the image starts on a home volume whose `lado.db` cannot be migrated
- **THEN** `docker logs` has the message of a failed migration naming the image of the
  version run before and no traceback, and `lado.db` keeps its schema

#### Scenario: The image before keeps a name
- **WHEN** a container is updated by the compose header's steps from one version to
  another
- **THEN** the image of the version before is still named by its version tag, and no
  step tags an image

#### Scenario: Back to the backup
- **WHEN** after the migration on start the compose header's steps back run
- **THEN** `lado.db` has the schema before again, and the container runs the image of the
  version before

## REMOVED Requirements

### Requirement: The image carries Claude Code only, at its tested version

**Reason**: The human's decision (2026-10-15): one image with all four agent CLIs.
**Migration**: Replaced by "The image carries the four agent CLIs at their tested
versions".

## ADDED Requirements

### Requirement: The image carries the four agent CLIs at their tested versions

The image SHALL install Claude Code, Codex CLI, OpenCode and Kilo CLI, each by the npm
package and at the version `scripts/smoke_ci.py`'s `PINS` gives it (its provider's
`TESTED_VERSION`) as the default of its own build argument, and no other agent CLI, with
Node.js 22 and npm on the agents' `PATH`; a unit test SHALL keep each default the same as
its pin and the image's CLIs the same as `PINS`' providers. Its base images SHALL be pinned
by digest, and Dependabot SHALL update them.

#### Scenario: A pin moves
- **WHEN** `PINS["kilo"]` changes and `docker/Dockerfile`'s default for Kilo does not
- **THEN** the unit tests fail and name both versions

#### Scenario: A provider is added to PINS
- **WHEN** `PINS` gets a fifth provider and the Dockerfile does not install it
- **THEN** the unit tests fail and name it

#### Scenario: An unpinned base image
- **WHEN** a `FROM` or `COPY --from` of `docker/Dockerfile` names an image without
  `@sha256:`
- **THEN** the unit tests fail and name its line

#### Scenario: lado doctor sees the four
- **WHEN** a container of the image runs `lado doctor`, on amd64 and on arm64
- **THEN** Claude Code, Codex CLI, OpenCode and Kilo CLI are each `ok` at their pin

#### Scenario: An agent runs npx
- **WHEN** an agent's login shell in a container of the image runs `node --version` and
  `npx --version`
- **THEN** both answer, Node with major version 22

### Requirement: Two LADO containers update independently

Updating one LADO container to another version SHALL change nothing of another LADO
container on the same machine: not its image, its container, its volume, nor the name of
the image it runs.

#### Scenario: One of two is updated
- **WHEN** two compose projects of `docker/compose.yaml`, each in its own folder with its
  own `.env`, run the same version, and the first's `.env` gets another version followed
  by `docker compose up -d` there
- **THEN** the first runs the other version's image, and the second's container is the
  same container (not recreated), still running the first version's image, under the
  same image reference
