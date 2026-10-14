## ADDED Requirements

### Requirement: LADO's image starts the UI server with one docker run

The repository SHALL hold LADO's image as `docker/Dockerfile`, whose every default is
inside the image, so that `docker run -d -p 127.0.0.1:<port>:<port> -e LADO_PORT=<port>
-v <volume>:/home/lado <image>`, with no other file, starts LADO's UI server. The server
SHALL listen on `0.0.0.0` at the port of `LADO_PORT`, 8765 when it is unset, as the
image's user `lado` (uid 1000) under tini, with LADO_HOME in `/home/lado/.lado` on the
home volume. The image SHALL set `LADO_CONTAINER=1` and `LADO_REPOS=/projects`, and SHALL
make `/projects` a folder its user may write, so that a container without a projects mount
still starts.

#### Scenario: The default port

- **WHEN** the human runs the image with `-p 127.0.0.1:8765:8765` and no `LADO_PORT`
- **THEN** `http://127.0.0.1:8765/api/health` on the host answers `ok` with LADO's
  version, and `docker logs` has the container note naming `0.0.0.0:8765`

#### Scenario: Another port

- **WHEN** the human runs it with `-e LADO_PORT=8766 -p 127.0.0.1:8766:8766`
- **THEN** `/api/health` answers on the host's port 8766, and `lado ui --no-open` in the
  container prints `http://127.0.0.1:8766/?token=<token>`

#### Scenario: lado doctor in the container

- **WHEN** `lado doctor` runs in a container of the image
- **THEN** it prints no `[FAIL]`, exits 0, and its LADO line ends with `in a container`

### Requirement: The image installs LADO from the wheel given to its build

The image SHALL install LADO from the one wheel in its build context, never from a package
index, so that the image holds exactly that wheel's LADO: in CI the wheel built from the
code under test, at a release the wheel the release uploads to PyPI. `make docker` SHALL
build the web UI's bundle and the wheel from the working copy and the image from them, as
`lado:local`.

#### Scenario: CI tests the pull request's LADO

- **WHEN** CI builds the image for a pull request that changes `src/lado/`
- **THEN** the LADO in the image is that pull request's, and `/api/health` gives the
  version of the wheel built from it

#### Scenario: The web UI is in the image

- **WHEN** the image runs and the host's browser opens the server's link
- **THEN** the server serves the UI's `index.html`, not a missing bundle

### Requirement: The image tells the agents they run in a container

The image SHALL set, in `/etc/profile.d/lado.sh`, which every login shell reads, the
variables its `ENV` sets for the agents' sake: `LADO_CONTAINER=1`, `LADO_REPOS`, the
programs' folders first on `PATH`, `CLAUDE_CONFIG_DIR=$HOME/.claude` and Claude Code's
update check off; an agent's environment comes from the user's login shell
(`agent_env.resolve`), not from the image's `ENV`.

#### Scenario: An agent's lado doctor

- **WHEN** a Claude Code agent runs in a container of the image and `lado doctor` runs
  with exactly the environment of the agent's process
- **THEN** its LADO line ends with `in a container`

### Requirement: The image carries Claude Code only, at its tested version

The image SHALL install Claude Code and no other agent CLI, at the version
`scripts/smoke_ci.py`'s `PINS` gives it (its provider's `TESTED_VERSION`), as the default of
its build argument; a unit test SHALL keep the two the same. Its base images SHALL be
pinned by digest, and Dependabot SHALL update them.

#### Scenario: Claude Code's pin moves

- **WHEN** `PINS["claude"]` changes and `docker/Dockerfile`'s default does not
- **THEN** the unit tests fail and name both versions

#### Scenario: An unpinned base image

- **WHEN** a `FROM` or `COPY --from` of `docker/Dockerfile` names an image without
  `@sha256:`
- **THEN** the unit tests fail and name its line

#### Scenario: The other CLIs

- **WHEN** a container of the image runs `lado doctor`
- **THEN** Claude Code is `ok` at its pin, and Codex, OpenCode and Kilo are `info`, not
  installed

### Requirement: The compose file publishes one port number

`docker/compose.yaml` SHALL run the same image (`LADO_IMAGE`, `lado:local` by default)
with one variable, `LADO_PORT` (8765 by default), as both the server's port in the
container and the published one, `127.0.0.1:${LADO_PORT}:${LADO_PORT}`, so the host's
number and the container's are always the same. It SHALL mount `LADO_PROJECTS`, which is
required, at `/projects`, and the home volume at `/home/lado`, and SHALL name no container,
so a second project (`-p`) runs beside the first with a container and a volume of its own.

#### Scenario: Two LADOs on one host

- **WHEN** the human runs `docker compose up -d` and `LADO_PORT=8766 docker compose -p
  lado-2 up -d` from `docker/`
- **THEN** both run, `/api/health` answers on 8765 and on 8766, and each has its own home
  volume

#### Scenario: No projects folder given

- **WHEN** the human runs `docker compose up -d` without `LADO_PROJECTS`
- **THEN** compose refuses and names `LADO_PROJECTS`
