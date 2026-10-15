## MODIFIED Requirements

### Requirement: LADO's image starts the UI server with one docker run

The repository SHALL hold LADO's image as `docker/Dockerfile`, whose every default is
inside the image, so that `docker run -d -p 127.0.0.1:<port>:<port> -e LADO_PORT=<port>
-v <volume>:/home/lado <image>`, with no other file, starts LADO's UI server. The server
SHALL listen on `0.0.0.0` at the port of `LADO_PORT`, 8765 when it is unset, as the
image's user `lado` (uid 1000 unless the projects' owner gives it another, see "The
image's user takes the projects folder's owner") under tini, with LADO_HOME in
`/home/lado/.lado` on the home volume. The image SHALL set `LADO_CONTAINER=1` and
`LADO_REPOS=/projects` as defaults, and SHALL make `/projects` a folder its user may
write, so that a container without a projects mount still starts.

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

### Requirement: The image tells the agents they run in a container

The image SHALL set, in `/etc/profile.d/`, which every login shell reads, the variables
the container's environment sets for the agents' sake: `LADO_CONTAINER=1`, the programs'
folders first on `PATH`, `CLAUDE_CONFIG_DIR=$HOME/.claude` and Claude Code's update check
off in `/etc/profile.d/lado.sh`, and the container's own `LADO_REPOS` (the image's
`/projects`, or the value given with `-e`) in `/etc/profile.d/lado-repos.sh`, written at
the container's first start; an agent's environment comes from the user's login shell
(`agent_env.resolve`), not from the container's environment.

#### Scenario: An agent's lado doctor

- **WHEN** a Claude Code agent runs in a container of the image and `lado doctor` runs
  with exactly the environment of the agent's process
- **THEN** its LADO line ends with `in a container`

#### Scenario: An agent's LADO_REPOS is the container's

- **WHEN** the container runs with `-e LADO_REPOS=/home/runner/projects` and an agent
  starts in it
- **THEN** the agent's process has `LADO_REPOS=/home/runner/projects`, not `/projects`

### Requirement: The compose file publishes one port number

`docker/compose.yaml` SHALL run the same image (`LADO_IMAGE`, `lado:local` by default)
with one variable, `LADO_PORT` (8765 by default), as both the server's port in the
container and the published one, `127.0.0.1:${LADO_PORT}:${LADO_PORT}`, so the host's
number and the container's are always the same. It SHALL mount `LADO_PROJECTS`, which is
required, at that same path inside the container and set `LADO_REPOS` to it, and mount
the home volume at `/home/lado`, and SHALL name no container, so a second project (`-p`)
runs beside the first with a container and a volume of its own.

#### Scenario: Two LADOs on one host

- **WHEN** the human runs `docker compose up -d` and `LADO_PORT=8766 docker compose -p
  lado-2 up -d` from `docker/`
- **THEN** both run, `/api/health` answers on 8765 and on 8766, and each has its own home
  volume

#### Scenario: No projects folder given

- **WHEN** the human runs `docker compose up -d` without `LADO_PROJECTS`
- **THEN** compose refuses and names `LADO_PROJECTS`

#### Scenario: The projects at the host's path

- **WHEN** the human runs `LADO_PROJECTS=/Users/me/projects docker compose up -d`
- **THEN** the container sees the projects at `/Users/me/projects` and `lado doctor` in it
  prints `[ok  ] Repositories folder: /Users/me/projects (LADO_REPOS)`

## ADDED Requirements

### Requirement: A worker's worktree made in the container works on the host

With the projects folder mounted at the host's own path and `LADO_REPOS` set to it, every
path LADO stores and every link git writes in the container (a worker's worktree, its
`.git` file, the repository's `worktrees/` record) SHALL be the host's path too, so that
git on the host reads a worktree LADO made in the container as a working tree.

#### Scenario: A worker commits in the container

- **WHEN** a session in the container works on `<projects>/app`, a worker of it commits a
  file in its worktree, and the host runs git in `<projects>/app`
- **THEN** on the host `git -C <projects>/app/.lado/worktrees/<session>/<worker> status`
  succeeds, `git worktree list --porcelain` names that worktree with no `prunable`, and
  the worker's commit is on its branch

### Requirement: The image's user takes the projects folder's owner

At a container's first start, before the UI server starts, the image SHALL give its user
`lado` the uid and gid of the owner of `LADO_REPOS`'s folder, unless that owner's uid is 0
(how Docker Desktop shows a bind mount) or equal to `lado`'s already; a gid of 0, root's
group, SHALL never be taken (`lado` keeps its own group). It SHALL then give
`lado` everything under `/home/lado` whose owner is not `lado`'s uid and gid. The server,
`docker exec <container> <command>` with no `-u`, and every agent SHALL run as `lado`
with that uid. The change SHALL be made by a step that runs as root once per container
and, first of all, removes the only way to it (a sudo rule for the entrypoint alone), so
that no process started after it, an agent included, can become root through it. Where
the image's entrypoint was replaced, the rule stays; the root step SHALL then run no
program chosen by its caller's environment (its commands by a fixed PATH or full paths,
the caller's PATH given back only after the drop to `lado`), so that the rule runs only
that step's own work. A container whose settings forbid becoming root (no-new-privileges,
capabilities dropped) or whose root file system is read-only SHALL start as before, `lado` with uid 1000 and the agents'
`LADO_REPOS` the image's `/projects`, with one warning line in `docker logs`; a step of the
root run that fails SHALL be a warning line, and the server SHALL start anyway. A
restart of the same container SHALL keep the uid it took. A folder `LADO_REPOS` that is no
folder in the container, or one `lado` may not write in, SHALL be named in `docker logs`
with one warning line, and the server SHALL start anyway.

#### Scenario: A Linux host's user

- **WHEN** the human's projects folder, owned by uid 1001 and gid 1001 on a Linux host
  (GitHub's runner), is mounted at its path with `LADO_REPOS` set to it, and an agent of
  the container writes a file and a commit there
- **THEN** `docker exec <container> id -u` prints 1001, and on the host the file and the
  commit's objects belong to uid 1001

#### Scenario: Docker Desktop shows the owner as 0

- **WHEN** `LADO_REPOS`'s folder is owned by uid 0 in the container
- **THEN** `lado` keeps uid 1000, and the server starts

#### Scenario: Recreated with another owner, the same home volume

- **WHEN** a container whose projects belong to uid 2001 has run with home volume H, and a
  new container of the image starts with H and projects that belong to uid 2002
- **THEN** in the new container `id -u` prints 2002, nothing under `/home/lado` belongs to
  another uid, the server answers `/api/health`, `lado doctor` prints no `[FAIL]`, and
  `lado ls` works

#### Scenario: Projects of root's group

- **WHEN** `LADO_REPOS`'s folder is owned by uid 2001 and gid 0
- **THEN** `id -u` in the container prints 2001 and `id -g` 1000

#### Scenario: The entrypoint replaced

- **WHEN** the container runs with `--entrypoint`, so the sudo rule stays, and `lado` runs
  the entrypoint through it with a `setpriv` of its own first on the PATH it hands over
- **THEN** that `setpriv` does not run, and the command runs as `lado`

#### Scenario: The container may not become root

- **WHEN** the container runs with `--security-opt no-new-privileges` or `--cap-drop ALL`
  and projects owned by uid 2001
- **THEN** the server answers `/api/health`, `id -u` prints 1000, and `docker logs` has a
  line `lado: warning: the container may not become root (no-new-privileges or dropped
  capabilities): lado keeps uid 1000 instead of the owner's of <path>, and the agents'
  LADO_REPOS is /projects`

#### Scenario: A read-only root file system

- **WHEN** the container runs with `--read-only --tmpfs /tmp` and projects owned by uid
  2001
- **THEN** the server answers `/api/health`, `id -u` prints 1000, and `docker logs` has a
  line `lado: warning: the container's root file system is read-only: lado keeps uid 1000
  instead of the owner's of <path>, and the agents' LADO_REPOS is /projects`

#### Scenario: A restart

- **WHEN** a container that took uid 2001 is restarted with `docker restart`
- **THEN** it runs as uid 2001 again and the server answers

#### Scenario: No way to root is left

- **WHEN** the container has started
- **THEN** `sudo -n true` run as `lado` in it fails

#### Scenario: The projects folder is not writable

- **WHEN** `LADO_REPOS`'s folder belongs to uid 0 and is not writable by others
- **THEN** `docker logs` has a line `lado: warning: LADO may not write in LADO_REPOS
  <path>`, and the server starts

#### Scenario: LADO_REPOS is not mounted

- **WHEN** the container runs with `-e LADO_REPOS=/home/me/projects` and nothing is
  mounted there
- **THEN** `docker logs` has a line `lado: warning: LADO_REPOS is not a folder in the
  container: /home/me/projects; mount the host's folder at this same path`, and the server
  starts

### Requirement: git in the image trusts every repository

The image's system git configuration SHALL have `safe.directory = *`, so that git in the
container never refuses a repository of the projects folder as of "dubious ownership",
whoever the folder's owner seems to be.

#### Scenario: A repository owned by another uid

- **WHEN** git runs as `lado` in the container on a repository whose files belong to
  another uid
- **THEN** `git status` there succeeds
