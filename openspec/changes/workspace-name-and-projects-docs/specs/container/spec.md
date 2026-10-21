## MODIFIED Requirements

### Requirement: The image's server listens on LADO_PORT as the image's user

The image's server
SHALL listen on `0.0.0.0` at the port of `LADO_PORT`, 8765 when it is unset, as the
image's user `lado` (uid 1000 unless the workspace's owner gives it another, see "The
image's user takes the workspace's owner") under tini, with LADO_HOME in
`/home/lado/.lado` on the home volume.

#### Scenario: Another port

- **WHEN** the human runs it with `-e LADO_PORT=8766 -p 127.0.0.1:8766:8766`
- **THEN** `/api/health` answers on the host's port 8766, and `lado ui --no-open` in the
  container prints `http://127.0.0.1:8766/?token=<token>`

### Requirement: A worker's worktree made in the container works on the host

With the workspace mounted at the host's own path and `LADO_REPOS` set to it, every
path LADO stores and every link git writes in the container (a worker's worktree, its
`.git` file, the repository's `worktrees/` record) SHALL be the host's path too, so that
git on the host reads a worktree LADO made in the container as a working tree.

#### Scenario: A worker commits in the container

- **WHEN** a session in the container works on `<workspace>/app`, a worker of it commits a
  file in its worktree, and the host runs git in `<workspace>/app`
- **THEN** on the host `git -C <workspace>/app/.lado/worktrees/<session>/<worker> status`
  succeeds, `git worktree list --porcelain` names that worktree with no `prunable`, and
  the worker's commit is on its branch

### Requirement: The server, docker exec and the agents run as the image's user

The server,
`docker exec <container> <command>` with no `-u`, and every agent SHALL run as `lado`
with the uid it took from the workspace's owner.

#### Scenario: A Linux host's user

- **WHEN** the human's workspace, owned by uid 1001 and gid 1001 on a Linux host
  (GitHub's runner), is mounted at its path with `LADO_REPOS` set to it, and an agent of
  the container writes a file and a commit there
- **THEN** `docker exec <container> id -u` prints 1001, and on the host the file and the
  commit's objects belong to uid 1001

### Requirement: git in the image trusts every repository

The image's system git configuration SHALL have `safe.directory = *`, so that git in the
container never refuses a repository of the workspace as of "dubious ownership",
whoever the folder's owner seems to be.

#### Scenario: A repository owned by another uid

- **WHEN** git runs as `lado` in the container on a repository whose files belong to
  another uid
- **THEN** `git status` there succeeds

### Requirement: The agents' global installs go to the home volume

An agent's `npm install -g` and `uv tool install` SHALL write under `/home/lado/.local`,
on the home volume, whatever uid the entrypoint gave `lado`, and the command they install
SHALL be on the `PATH` of the next login shell. The image's `ENV`, which the server and
`docker exec` get, SHALL point no install at `/opt`; the baked-in agent CLIs and LADO stay
in `/opt`.

#### Scenario: Installs at another uid

- **WHEN** the workspace belongs to uid 1001 (GitHub's runner) and an agent's login
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

- **WHEN** a login shell as `lado` runs `python3 -m venv` in a project and installs a
  local package into it with its pip
- **THEN** both succeed, and the package is in the environment only

## REMOVED Requirements

### Requirement: The compose file mounts the projects at the host's path

**Reason**: Renamed: the folder is called the workspace (docs/design/projects.md).
**Migration**: Replaced by "The compose file mounts the workspace at the host's path", the same rule in the new words.

### Requirement: The image's user takes the projects folder's owner

**Reason**: Renamed: the folder is called the workspace (docs/design/projects.md).
**Migration**: Replaced by "The image's user takes the workspace's owner", the same rule in the new words.

### Requirement: A projects folder LADO cannot use is named at the start

**Reason**: Renamed: the folder is called the workspace (docs/design/projects.md).
**Migration**: Replaced by "A workspace LADO cannot use is named at the start", the same rule in the new words.

## ADDED Requirements

### Requirement: The compose file mounts the workspace at the host's path

`docker/compose.yaml` SHALL mount
`LADO_PROJECTS`, which is required, at that same path inside the container and set
`LADO_REPOS` to it, and mount the home volume at `/home/lado`, and SHALL name no
container.

#### Scenario: No workspace given
- **WHEN** the human runs `docker compose up -d` without `LADO_PROJECTS`
- **THEN** compose refuses and names `LADO_PROJECTS`

#### Scenario: The workspace at the host's path
- **WHEN** the human runs `LADO_PROJECTS=/Users/me/projects docker compose up -d`
- **THEN** the container sees the workspace at `/Users/me/projects` and `lado doctor` in it
  prints `[ok  ] Workspace: /Users/me/projects (LADO_REPOS)`

### Requirement: The image's user takes the workspace's owner

At a container's first start, before the UI server starts, the image SHALL give its user
`lado` the uid and gid of the owner of `LADO_REPOS`'s folder, unless that owner's uid is 0
(how Docker Desktop shows a bind mount) or equal to `lado`'s already; a gid of 0, root's
group, SHALL never be taken (`lado` keeps its own group). It SHALL then give
`lado` everything under `/home/lado` whose owner is not `lado`'s uid and gid. A
restart of the same container SHALL keep the uid it took.

#### Scenario: Docker Desktop shows the owner as 0

- **WHEN** `LADO_REPOS`'s folder is owned by uid 0 in the container
- **THEN** `lado` keeps uid 1000, and the server starts

#### Scenario: Recreated with another owner, the same home volume

- **WHEN** a container whose workspace belongs to uid 2001 has run with home volume H, and a
  new container of the image starts with H and a workspace that belongs to uid 2002
- **THEN** in the new container `id -u` prints 2002, nothing under `/home/lado` belongs to
  another uid, the server answers `/api/health`, `lado doctor` prints no `[FAIL]`, and
  `lado ls` works

#### Scenario: A workspace of root's group

- **WHEN** `LADO_REPOS`'s folder is owned by uid 2001 and gid 0
- **THEN** `id -u` in the container prints 2001 and `id -g` 1000

#### Scenario: A restart

- **WHEN** a container that took uid 2001 is restarted with `docker restart`
- **THEN** it runs as uid 2001 again and the server answers

### Requirement: A workspace LADO cannot use is named at the start

A folder `LADO_REPOS` that is no
folder in the container, or one `lado` may not write in, SHALL be named in `docker logs`
with one warning line, and the server SHALL start anyway.

#### Scenario: The workspace is not writable

- **WHEN** `LADO_REPOS`'s folder belongs to uid 0 and is not writable by others
- **THEN** `docker logs` has a line `lado: warning: LADO may not write in LADO_REPOS
  <path>`, and the server starts

#### Scenario: LADO_REPOS is not mounted

- **WHEN** the container runs with `-e LADO_REPOS=/home/me/projects` and nothing is
  mounted there
- **THEN** `docker logs` has a line `lado: warning: LADO_REPOS is not a folder in the
  container: /home/me/projects; mount the host's folder at this same path`, and the server
  starts
