## MODIFIED Requirements

### Requirement: The image's profile sets the container, the PATH and the tools' settings

The image SHALL set in `/etc/profile.d/lado.sh`: `LADO_CONTAINER=1`, the programs'
folders first on `PATH` (`/opt/uv/bin`, `/opt/agents/bin`, `/opt/tools/bin`), then the
system's, then `~/.local/bin` and mise's shims folder (`~/.local/share/mise/shims`), and
last the image's fallbacks (`/opt/fallback/bin`), npm's global prefix `$HOME/.local`,
`CLAUDE_CONFIG_DIR=$HOME/.claude` and Claude Code's update check off, and mise's trusted
folder set to the container's `LADO_REPOS`.

#### Scenario: The image's Node stays first

- **WHEN** Node 20 is installed through mise as the container's default
  (`mise use -g node@20`) and a login shell in a project runs `node --version`
- **THEN** it answers with Node 22, the image's, and `mise exec node@20 -- node --version`
  answers with Node 20

## ADDED Requirements

### Requirement: The image carries the agents' base tools

The image SHALL carry, from Debian and on every login shell's `PATH`, `jq`, `rg`
(ripgrep), `unzip`, `zip`, `xz`, `bzip2`, `patch`, `file`, `rsync`, `sqlite3`, `tree`,
`lsof` and `nc` (netcat-openbsd), so that the agents and the kits' scripts find them in
a new container on a clean home volume with nothing installed.

#### Scenario: Each tool answers in an agent's shell

- **WHEN** a login shell as `lado`, started from a clean environment as LADO starts an
  agent's, runs each of the tools with its version or help flag in a new container on a
  new home volume
- **THEN** each answers with exit 0

#### Scenario: A tool leaves the apt layer

- **WHEN** a package of the list is missing from `docker/Dockerfile`'s first
  `apt-get install`
- **THEN** the unit tests fail and name it

### Requirement: The image carries openspec at its pin

The image SHALL carry the openspec CLI (`@fission-ai/openspec`) at the exact version of
the build argument `OPENSPEC_VERSION`, in a layer of its own under `/opt/tools`, on every
login shell's `PATH` before mise's shims, with its usage statistics and update check off
(`OPENSPEC_TELEMETRY=0`, `OPENSPEC_NO_UPDATE_CHECK=1` in `/etc/profile.d/lado.sh` and the
image's `ENV`), so that a kit expecting `openspec` starts on a clean home volume and no
openspec of the home volume shadows the image's.

#### Scenario: openspec stays off the network for statistics

- **WHEN** an agent's login shell in a container of the image prints its environment
- **THEN** it has `OPENSPEC_TELEMETRY=0` and `OPENSPEC_NO_UPDATE_CHECK=1`, and so does
  `docker exec`'s environment

#### Scenario: A clean home volume

- **WHEN** a login shell as `lado` in a new container on a new home volume runs
  `openspec --version`
- **THEN** it answers with `OPENSPEC_VERSION`'s default

#### Scenario: An older openspec through mise

- **WHEN** an older openspec is the container's default through mise
  (`mise use -g npm:@fission-ai/openspec@<older>`) and a login shell runs
  `openspec --version`
- **THEN** it answers with the image's pin

#### Scenario: The pin is loose

- **WHEN** `docker/Dockerfile`'s `OPENSPEC_VERSION` default is not an exact version, or
  its install shares a layer with another package
- **THEN** the unit tests fail and name the line

### Requirement: The image's python3 gives way to a project's Python

The image SHALL answer `python3` and `python` with the Python LADO runs on (CPython 3.13,
uv's, under `/opt/uv/python`), from a folder on `PATH` after mise's shims, so that where
mise has a Python for the folder (a version file, or a container-wide `mise use -g`) that
Python answers instead. The image's Python SHALL be owned by root, and the user `lado`
SHALL NOT be able to install a package into it; `python3 -m venv` SHALL make an
environment.

#### Scenario: Outside a project

- **WHEN** a login shell as `lado` in a folder without a Python version file runs
  `python3 --version` and `python --version`
- **THEN** both answer `Python 3.13.<patch>`

#### Scenario: A project's own Python

- **WHEN** a project under `LADO_REPOS` holds `.python-version` with `3.12` and a login
  shell there runs `mise install`, then `python3 --version`
- **THEN** it answers `Python 3.12.<patch>`, and in the projects folder above it
  `python3 --version` still answers 3.13

#### Scenario: The agents cannot change LADO's Python

- **WHEN** a login shell as `lado` runs `python3 -m pip install` of a local package
  outside an environment, and checks whether it may write to the image's Python
- **THEN** pip refuses (externally managed), the image's Python's files are root's and not
  writable by `lado`, and `lado --version` still answers

#### Scenario: A virtual environment

- **WHEN** a login shell as `lado` runs `python3 -m venv` in a project and installs a
  local package into it with its pip
- **THEN** both succeed, and the package is in the environment only
