## MODIFIED Requirements

### Requirement: The image tells the agents they run in a container

The image SHALL set, in `/etc/profile.d/`, which every login shell reads, the variables
the container's environment sets for the agents' sake: `LADO_CONTAINER=1`, the programs'
folders first on `PATH`, then the system's, then `~/.local/bin` and mise's shims folder
(`~/.local/share/mise/shims`), npm's global prefix `$HOME/.local`,
`CLAUDE_CONFIG_DIR=$HOME/.claude` and Claude Code's update check off in
`/etc/profile.d/lado.sh`, mise's trusted folder set to the container's `LADO_REPOS`, and
the container's own `LADO_REPOS` (the image's `/projects`, or the value given with `-e`)
in `/etc/profile.d/lado-repos.sh`, written at the container's first start; an agent's
environment comes from the user's login shell (`agent_env.resolve`), not from the
container's environment.

#### Scenario: An agent's lado doctor

- **WHEN** a Claude Code agent runs in a container of the image and `lado doctor` runs
  with exactly the environment of the agent's process
- **THEN** its LADO line ends with `in a container`

#### Scenario: An agent's LADO_REPOS is the container's

- **WHEN** the container runs with `-e LADO_REPOS=/home/runner/projects` and an agent
  starts in it
- **THEN** the agent's process has `LADO_REPOS=/home/runner/projects`, not `/projects`

#### Scenario: The image's Node stays first

- **WHEN** Node 20 is installed through mise as the container's default
  (`mise use -g node@20`) and a login shell in a project runs `node --version`
- **THEN** it answers with Node 22, the image's, and `mise exec node@20 -- node --version`
  answers with Node 20

## ADDED Requirements

### Requirement: The image carries mise with its data on the home volume

The image SHALL carry mise at `/usr/local/bin/mise`, owned by root, copied from mise's
official image pinned by digest, and SHALL keep mise's data, config and cache at its
defaults under `/home/lado`, on the home volume. Its system config
`/etc/mise/config.toml`, from `docker/mise.toml`, SHALL enable the version files of Go,
Java, Python and Ruby besides `.tool-versions` and `mise.toml`, and no other tool's. A
project's `mise.toml` under `LADO_REPOS` SHALL be trusted without `mise trust`. The user
`lado` SHALL install a tool through mise without root, and the tool SHALL still run after
the container is made again on the same home volume.

#### Scenario: A project's Go from its .tool-versions

- **WHEN** a project under `LADO_REPOS` holds `.tool-versions` with `go <version>` and a
  login shell as `lado` runs `mise install` and `go build` there
- **THEN** both succeed without root, and the Go is under `/home/lado/.local/share/mise`

#### Scenario: The tool survives a recreation

- **WHEN** that container is removed and a new one of the image starts on the same home
  volume
- **THEN** `go version` in the project's folder answers with the same version, with no
  install

#### Scenario: Two agents install the same version at once

- **WHEN** two login shells run `mise install go@<version>` at the same time
- **THEN** both succeed and that version is installed once

#### Scenario: A project's mise.toml needs no trust

- **WHEN** a project under `LADO_REPOS` holds a `mise.toml` naming a tool and a login
  shell runs `mise install` there
- **THEN** mise installs it and does not refuse the file as not trusted

#### Scenario: An unpinned mise

- **WHEN** `docker/Dockerfile` takes mise from an image named without `@sha256:`
- **THEN** the unit tests fail and name its line

### Requirement: The image carries the build tools

The image SHALL carry `make`, `gcc`, `g++` and `libc6-dev` from Debian, on every login
shell's `PATH`.

#### Scenario: C and C++ build

- **WHEN** a login shell as `lado` runs a Makefile that compiles a C and a C++ file
- **THEN** both programs build and run

### Requirement: The agents' global installs go to the home volume

An agent's `npm install -g` and `uv tool install` SHALL write under `/home/lado/.local`,
on the home volume, whatever uid the entrypoint gave `lado`, and the command they install
SHALL be on the `PATH` of the next login shell. The image's `ENV`, which the server and
`docker exec` get, SHALL point no install at `/opt`; the baked-in agent CLIs and LADO stay
in `/opt`.

#### Scenario: Installs at another uid

- **WHEN** the projects folder belongs to uid 1001 (GitHub's runner) and an agent's login
  shell runs `npm install -g` of a package and `uv tool install` of another, both local
- **THEN** both succeed, their files are under `/home/lado/.local`, and a new login shell
  runs both commands

#### Scenario: Installs on a home volume of 0.40.0

- **WHEN** the image starts on a home volume a container of LADO 0.40.0 used, and an
  agent's login shell runs the same installs
- **THEN** they succeed as on a new volume, and the volume's sessions are kept

#### Scenario: The image's ENV names no /opt for installs

- **WHEN** `docker/Dockerfile`'s runtime `ENV` sets `NPM_CONFIG_PREFIX`, `UV_TOOL_DIR`,
  `UV_TOOL_BIN_DIR` or `UV_PYTHON_INSTALL_DIR` to a folder under `/opt`
- **THEN** the unit tests fail and name the variable

### Requirement: The agents in a container are told to install a missing tool with mise

When LADO runs in its container (`LADO_CONTAINER`), LADO's instructions SHALL give every
agent, on every provider, a paragraph saying that mise is there: a tool the project needs
and lacks is installed with mise, by the project's version files when they name it, and
otherwise by tool and version and run with `mise exec`; no version file or other file is
added to the project unless the human asks; apt packages and databases cannot be
installed. The supervisor's paragraph SHALL say that only it sets a tool's container-wide
default version (`mise use -g`); a worker's SHALL say to ask the supervisor for one.
Outside a container the paragraph SHALL be absent.

#### Scenario: A worker in a container

- **WHEN** LADO runs with `LADO_CONTAINER=1` and starts a worker
- **THEN** the worker's instructions hold the mise paragraph with the sentence to ask the
  supervisor for a default version, and not the supervisor's sentence

#### Scenario: The supervisor in a container

- **WHEN** LADO runs with `LADO_CONTAINER=1` and starts a session
- **THEN** the supervisor's instructions hold the mise paragraph with the sentence that
  only it sets a default version

#### Scenario: Outside a container

- **WHEN** LADO runs without `LADO_CONTAINER` and starts a session with a worker
- **THEN** no agent's instructions name mise
