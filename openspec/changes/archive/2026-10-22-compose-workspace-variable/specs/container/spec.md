## REMOVED Requirements

### Requirement: The image carries mise with its data on the home volume

**Reason**: Its scenario "A project's Go from its .tool-versions" is about the human's repository; "project" now means a LADO project (docs/design/projects.md).
**Migration**: Replaced by "The image carries mise and keeps its data on the home volume", the same rule with the scenario "A repository's Go from its .tool-versions".

### Requirement: mise reads the projects' version files and trusts their mise.toml

**Reason**: "project" here is the human's repository; "project" now means a LADO project (docs/design/projects.md).
**Migration**: Replaced by "mise reads the repositories' version files and trusts their mise.toml", the same rule in the new words.

### Requirement: The image's python3 gives way to a project's Python

**Reason**: "project" here is the human's repository; "project" now means a LADO project (docs/design/projects.md).
**Migration**: Replaced by "The image's python3 gives way to a repository's Python", the same rule in the new words.

## ADDED Requirements

### Requirement: The image carries mise and keeps its data on the home volume

The image SHALL carry mise at `/usr/local/bin/mise`, owned by root, copied from mise's
official image pinned by digest, and SHALL keep mise's data, config and cache at its
defaults under `/home/lado`, on the home volume. The user
`lado` SHALL install a tool through mise without root, and the tool SHALL still run after
the container is made again on the same home volume.

#### Scenario: A repository's Go from its .tool-versions

- **WHEN** a repository under `LADO_REPOS` holds `.tool-versions` with `go <version>` and a
  login shell as `lado` runs `mise install` and `go build` there
- **THEN** both succeed without root, and the Go is under `/home/lado/.local/share/mise`

#### Scenario: The tool survives a recreation

- **WHEN** that container is removed and a new one of the image starts on the same home
  volume
- **THEN** `go version` in the repository's folder answers with the same version, with no
  install

#### Scenario: Two agents install the same version at once

- **WHEN** two login shells run `mise install go@<version>` at the same time
- **THEN** both succeed and that version is installed once

#### Scenario: An unpinned mise

- **WHEN** `docker/Dockerfile` takes mise from an image named without `@sha256:`
- **THEN** the unit tests fail and name its line

### Requirement: mise reads the repositories' version files and trusts their mise.toml

The image's mise system config
`/etc/mise/config.toml`, from `docker/mise.toml`, SHALL enable the version files of Go,
Java, Python and Ruby besides `.tool-versions` and `mise.toml`, and no other tool's. A
repository's `mise.toml` under `LADO_REPOS` SHALL be trusted without `mise trust`.

#### Scenario: A repository's mise.toml needs no trust

- **WHEN** a repository under `LADO_REPOS` holds a `mise.toml` naming a tool and a login
  shell runs `mise install` there
- **THEN** mise installs it and does not refuse the file as not trusted

### Requirement: The image's python3 gives way to a repository's Python

The image SHALL answer `python3` and `python` with the Python LADO runs on (CPython 3.13,
uv's, under `/opt/uv/python`), from a folder on `PATH` after mise's shims, so that where
mise has a Python for the folder (a version file, or a container-wide `mise use -g`) that
Python answers instead. The image's Python SHALL be owned by root, and the user `lado`
SHALL NOT be able to install a package into it; `python3 -m venv` SHALL make an
environment.

#### Scenario: Outside a repository

- **WHEN** a login shell as `lado` in a folder without a Python version file runs
  `python3 --version` and `python --version`
- **THEN** both answer `Python 3.13.<patch>`

#### Scenario: A repository's own Python

- **WHEN** a repository under `LADO_REPOS` holds `.python-version` with `3.12` and a login
  shell there runs `mise install`, then `python3 --version`
- **THEN** it answers `Python 3.12.<patch>`, and in the workspace above it
  `python3 --version` still answers 3.13

#### Scenario: The agents cannot change LADO's Python

- **WHEN** a login shell as `lado` runs `python3 -m pip install` of a local package
  outside an environment, and checks whether it may write to the image's Python
- **THEN** pip refuses (externally managed), the image's Python's files are root's and not
  writable by `lado`, and `lado --version` still answers

#### Scenario: A virtual environment

- **WHEN** a login shell as `lado` runs `python3 -m venv` in a repository and installs a
  local package into it with its pip
- **THEN** both succeed, and the package is in the environment only

## MODIFIED Requirements

### Requirement: LADO's image starts the UI server with one docker run

The repository SHALL hold LADO's image as `docker/Dockerfile`, whose every default is
inside the image, so that `docker run -d -p 127.0.0.1:<port>:<port> -e LADO_PORT=<port>
-v <volume>:/home/lado <image>`, with no other file, starts LADO's UI server. The image SHALL set `LADO_CONTAINER=1` and
`LADO_REPOS=/projects` as defaults, and SHALL make `/projects` a folder its user may
write, so that a container without a workspace mount still starts.

#### Scenario: The default port

- **WHEN** the human runs the image with `-p 127.0.0.1:8765:8765` and no `LADO_PORT`
- **THEN** `http://127.0.0.1:8765/api/health` on the host answers `ok` with LADO's
  version, and `docker logs` has the container note naming `0.0.0.0:8765`

#### Scenario: lado doctor in the container

- **WHEN** `lado doctor` runs in a container of the image
- **THEN** it prints no `[FAIL]`, exits 0, and its LADO line ends with `in a container`

### Requirement: The image's profile sets the container, the PATH and the tools' settings

The image SHALL set in `/etc/profile.d/lado.sh`: `LADO_CONTAINER=1`, the programs'
folders first on `PATH` (`/opt/uv/bin`, `/opt/agents/bin`, `/opt/tools/bin`), then the
system's, then `~/.local/bin` and mise's shims folder (`~/.local/share/mise/shims`), and
last the image's fallbacks (`/opt/fallback/bin`), npm's global prefix `$HOME/.local`,
`CLAUDE_CONFIG_DIR=$HOME/.claude` and Claude Code's update check off, and mise's trusted
folder set to the container's `LADO_REPOS`.

#### Scenario: The image's Node stays first

- **WHEN** Node 20 is installed through mise as the container's default
  (`mise use -g node@20`) and a login shell in a repository runs `node --version`
- **THEN** it answers with Node 22, the image's, and `mise exec node@20 -- node --version`
  answers with Node 20

### Requirement: The compose header says where the settings go and how to run a second LADO

The header of `docker/compose.yaml` SHALL say to keep its variables in `.env` next to the file, that
`LADO_LISTEN=0.0.0.0` opens LADO to every device of the network with the token
travelling unencrypted, and that a second LADO is a folder of its own with a copy of the
file and its own `.env` (`COMPOSE_PROJECT_NAME`, `LADO_PORT`, `LADO_VERSION`,
`LADO_WORKSPACE`), so it runs beside the first with a container, a volume and a version of
its own.

#### Scenario: Two LADOs on one host
- **WHEN** the human runs `docker compose up -d` in a folder whose `.env` has
  `LADO_VERSION`, and in a second folder whose `.env` adds `COMPOSE_PROJECT_NAME=lado-2`
  and `LADO_PORT=8766`
- **THEN** both run, `/api/health` answers on 8765 and on 8766, and each has its own home
  volume

### Requirement: A container that may not become root starts as before

A container whose settings forbid becoming root (no-new-privileges,
capabilities dropped) or whose root file system is read-only SHALL start as before, `lado` with uid 1000 and the agents'
`LADO_REPOS` the image's `/projects`, with one warning line in `docker logs`; a step of the
root run that fails SHALL be a warning line, and the server SHALL start anyway.

#### Scenario: The container may not become root

- **WHEN** the container runs with `--security-opt no-new-privileges` or `--cap-drop ALL`
  and a workspace owned by uid 2001
- **THEN** the server answers `/api/health`, `id -u` prints 1000, and `docker logs` has a
  line `lado: warning: the container may not become root (no-new-privileges or dropped
  capabilities): lado keeps uid 1000 instead of the owner's of <path>, and the agents'
  LADO_REPOS is /projects`

#### Scenario: A read-only root file system

- **WHEN** the container runs with `--read-only --tmpfs /tmp` and a workspace owned by
  uid 2001
- **THEN** the server answers `/api/health`, `id -u` prints 1000, and `docker logs` has a
  line `lado: warning: the container's root file system is read-only: lado keeps uid 1000
  instead of the owner's of <path>, and the agents' LADO_REPOS is /projects`

### Requirement: The guide removes only its own container and volume

The guide SHALL remove only its own
container and volume, by name, and nothing in the guide or the headers SHALL run a
`docker ... prune`.

#### Scenario: Removal by name
- **WHEN** the test reads the guide's removal
- **THEN** it runs `docker compose down` and `docker volume rm` of the compose project's
  own `home` volume, and README.md, docs/*.md and docker/ hold no `prune` (docs/research/ and
  docs/superpowers/ are records, not read as instructions)

### Requirement: The agents in a container are told to install a missing tool with mise

When LADO runs in its container (`LADO_CONTAINER`), LADO's instructions SHALL give every
agent, on every provider, a paragraph saying that mise is there: a tool the repository needs
and lacks is installed with mise, by the repository's version files when they name it,
and otherwise by tool and version and run with `mise exec`; no version file or other file
is added to the repository unless the human asks; apt packages and databases cannot be
installed.

#### Scenario: A worker in a container

- **WHEN** LADO runs with `LADO_CONTAINER=1` and starts a worker
- **THEN** the worker's instructions hold the mise paragraph with the sentence to ask the
  supervisor for a default version, and not the supervisor's sentence

### Requirement: The image carries no browser

The image SHALL NOT carry a browser: a repository's Playwright installs it into the home
volume (`make browser`), at that repository's own Playwright version.

#### Scenario: A new home volume has no browser

- **WHEN** a login shell as `lado` in a new container on a new home volume looks for
  Playwright's browsers (`~/.cache/ms-playwright`) and for `chromium`, `chromium-browser`
  or `google-chrome` on `PATH`
- **THEN** there is none

### Requirement: The compose file mounts the workspace at the host's path

`docker/compose.yaml` SHALL take the workspace from `LADO_WORKSPACE`, else from
`LADO_PROJECTS` (the name before 0.43.0, still accepted), mount it at that same path inside
the container and set `LADO_REPOS` to it, and mount the home volume at `/home/lado`, and
SHALL name no container. When neither is set, `docker compose up -d` SHALL refuse with an
error that names `LADO_WORKSPACE`; compose's other commands SHALL NOT ask for either.

#### Scenario: No workspace given
- **WHEN** the human runs `docker compose up -d` with neither `LADO_WORKSPACE` nor
  `LADO_PROJECTS`
- **THEN** no container starts, and the error names `LADO_WORKSPACE`

#### Scenario: The workspace at the host's path
- **WHEN** the human runs `LADO_WORKSPACE=/Users/me/projects docker compose up -d`
- **THEN** the container sees the workspace at `/Users/me/projects` and `lado doctor` in it
  prints `[ok  ] Workspace: /Users/me/projects (LADO_REPOS)`

#### Scenario: An installation's .env with the name before
- **WHEN** `.env` has `LADO_PROJECTS=/Users/me/projects` and no `LADO_WORKSPACE`
- **THEN** `docker compose config` mounts `/Users/me/projects` at `/Users/me/projects` and
  sets `LADO_REPOS=/Users/me/projects`, as before

#### Scenario: Both names
- **WHEN** `.env` has `LADO_WORKSPACE=/Users/me/new` and `LADO_PROJECTS=/Users/me/old`
- **THEN** `docker compose config` mounts and names `/Users/me/new` only

#### Scenario: A project's folder is in the workspace
- **WHEN** the container runs with `LADO_WORKSPACE` set to a host folder, and
  `lado project create acme` runs in it
- **THEN** the host sees `<workspace>/projects/acme`, and the UI's folder check of that
  folder gives no "Outside the workspace" warning
