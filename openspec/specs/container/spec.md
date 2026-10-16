# container Specification

## Purpose
How LADO behaves when it runs in a container: the image says so with `LADO_CONTAINER`,
`lado update` and the UI's update refuse there and name the new version's published image
(the compose file runs `ghcr.io/ladohq/lado:${LADO_VERSION}`: an update is a new
`LADO_VERSION` and `docker compose up -d`, and the image before keeps its tag), a new image
migrates the home volume's `lado.db` with a backup and the compose header's steps go back
to the image of the version before, and `lado doctor`, the System panel and the issue
report say LADO runs in a container.

## Requirements

### Requirement: LADO knows it runs in a container by LADO_CONTAINER

LADO SHALL take itself as running in a container when the environment variable
`LADO_CONTAINER` is set to a value other than the empty string and `0`, and SHALL NOT
guess it any other way (no look at `/.dockerenv` or cgroups). One function
(`update.in_container`) SHALL answer it for the CLI, `lado doctor`, the system report and
the UI server alike.

#### Scenario: The image sets it
- **WHEN** LADO runs with `LADO_CONTAINER=1`
- **THEN** it runs in a container

#### Scenario: Unset, empty or 0
- **WHEN** `LADO_CONTAINER` is unset, empty or `0`
- **THEN** LADO does not run in a container, also inside a Docker container

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

### Requirement: The UI server in a container names the port's publication, not other machines

In a container, a UI server listening on a non-loopback address SHALL NOT print the
warning that it is open to other machines; `lado server` and `lado ui` SHALL instead print
on stderr the one line `lado: note: the LADO server runs in a container and listens on
<host>:<port> inside it; who reaches it depends on how the container publishes the port
(127.0.0.1:<port>:<port>: this computer only). Published to other machines, the token
travels unencrypted (plain HTTP).` A server on a loopback address SHALL print neither, as
outside a container. Outside a container the warning SHALL stay as it is.

#### Scenario: The image's server starts
- **WHEN** `lado server --host 0.0.0.0 --port 8765` starts with `LADO_CONTAINER=1`
- **THEN** its output has the note naming `0.0.0.0:8765` and no `open to other machines`

#### Scenario: The same server outside a container
- **WHEN** `lado server --host 0.0.0.0` starts without `LADO_CONTAINER`
- **THEN** it prints the warning that it is open to other machines, as before

### Requirement: lado ui in a container prints the link for the host's browser

In a container `lado ui` SHALL print the server's local link
(`http://127.0.0.1:<port>/?token=<token>` for a server on `0.0.0.0`) and SHALL NOT print a
`From another machine` line nor try to open a browser. With `--no-open` its standard
output SHALL be that one line; without it, the link followed by the line `Open it in your
browser on the host.`

#### Scenario: The launcher asks for the link
- **WHEN** `docker exec lado lado ui --no-open` runs against a server on `0.0.0.0:8765` in
  a container
- **THEN** standard output is exactly `http://127.0.0.1:8765/?token=<token>`, and stderr
  has the note

#### Scenario: lado ui without --no-open in a container
- **WHEN** the human runs `lado ui` in a container
- **THEN** no browser is opened, and it prints the link and `Open it in your browser on
  the host.`

#### Scenario: Outside a container
- **WHEN** `lado ui --no-open` runs without `LADO_CONTAINER` against a server on
  `0.0.0.0`
- **THEN** it prints the local link, then `From another machine: http://<hostname>:<port>/?token=<token> (or this host's address)`,
  and the warning, as before

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
and, first of all, removes its way to it (a sudo rule for the entrypoint alone), so
that no process started after it, an agent included, can become root through it; the
image's one other sudo rule, for the ssh agent's socket (requirement "The host's ssh agent
reaches the agents without root's group"), runs one fixed program that takes no argument
and no variable and gives no root shell. Where
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

### Requirement: The container's stop stops its sessions for a resume

When the UI server runs in a container (`update.in_container()`) and is told to end
(SIGTERM, SIGINT, `lado server stop`), it SHALL, before it waits for any open request or
event stream, mark every session not stopped as stopped, as `lado stop` marks one (its
agents forgotten, messages they never got dropped, open runs and gates kept), with the mark
`resume_at_start` set, all sessions in one transaction; and only then kill each one's tmux
session, close its UI viewers and remove its agents' config folders. The `session_stop`
event's detail SHALL end with `; the container stopped`. It SHALL print one line on stderr
(`docker logs`): `lado: the container stops: stopped sessions "<a>", "<b>"; they resume at
its start`, and none when no session ran. A session stopped already keeps its mark as it
is. The agents that end by this SHALL tell no one, as after `lado stop`. When `lado.db`
does not exist, it SHALL do nothing and make no `LADO_HOME`.

#### Scenario: compose down with a running session
- **WHEN** a session runs in a container of `docker/compose.yaml` and the human runs
  `docker compose down`
- **THEN** `docker logs` has the line naming the session, the container exits with 0 (not
  killed after the grace period), and the home volume's `lado.db` has the session stopped
  with `resume_at_start` 1

#### Scenario: Within Docker's default grace period
- **WHEN** a container with three running sessions gets `docker stop` with Docker's default
  ten seconds
- **THEN** the container's exit code is 0 and all three sessions are stopped with the mark

#### Scenario: No message about the dying agents
- **WHEN** the container's stop ends a session whose supervisor and worker run
- **THEN** no message from `lado` to the human or the supervisor is queued about their end,
  and `lado log` shows the session's stop with `the container stopped`

#### Scenario: A session the human stopped
- **WHEN** a session was stopped with `lado stop` before the container's stop
- **THEN** it stays stopped without the mark, and the stop's line does not name it

#### Scenario: Nothing ran
- **WHEN** the container stops with no session running
- **THEN** `docker logs` has no line about sessions

#### Scenario: The server's stop after an uninstall
- **WHEN** the server in a container ends after `LADO_HOME` was deleted
- **THEN** no `LADO_HOME` is made again

### Requirement: The container's start resumes its sessions after the migration

When the UI server starts in a container, after `lado.db` is migrated (the CLI migrates
before the command, as before), it SHALL resume in the background, while it already
serves, one session at a time: each stopped session with `resume_at_start` set, and each
session not stopped whose tmux session is gone (the container ended without its stop:
`docker kill`, a crash of Docker or the machine, or a tmux that ended inside the
container). It SHALL NOT resume a session stopped without the mark. Each resume SHALL be
`lado start`'s resume of that session with its stored repository and settings, its
`session_resume` event's detail starting with `at the container's start`, and SHALL clear
`resume_at_start` in the transaction that takes the session. `docker logs` SHALL get
`lado: resumed session "<name>" at the container's start` for each one resumed, followed
by `lado: session "<name>": <line>` for each problem and warning `lado start` prints for
that resume (an open run that cannot go on, a kit's or the provider's warning), and
`lado: could not resume session "<name>" at the container's start: <error>; it stays
stopped` for one that fails, which stays stopped without the mark and is not tried at the
next start; the others SHALL go on. Workers SHALL NOT be restarted by LADO: the
supervisor's `session resumed` message names the open runs and the workers to start for
them, as after `lado start`. When the server is told to end while it resumes, it SHALL
resume no further session.

#### Scenario: compose up after compose down
- **WHEN** after `docker compose down` with a running session the human runs `docker
  compose up -d`
- **THEN** the session runs again, its supervisor gets to idle, `docker logs` has the
  resumed line, `resume_at_start` is 0, and `lado doctor` warns about no agent config
  folder

#### Scenario: A container killed without SIGTERM
- **WHEN** a session runs and the container is ended with `docker kill`, then started
- **THEN** the session runs again with its supervisor idle and `lado doctor` warns about
  no agent config folder

#### Scenario: A new image on the home volume
- **WHEN** a container of a new LADO image starts on a home volume whose `lado.db` has the
  schema before and a session not stopped
- **THEN** `docker logs` has the upgrade line before the resumed line, `lado.db` has this
  LADO's schema and the session runs

#### Scenario: A session the human stopped stays stopped
- **WHEN** the container starts with a session stopped by `lado stop`
- **THEN** that session is still stopped and `docker logs` does not name it

#### Scenario: A resume that fails
- **WHEN** a session with the mark cannot be resumed at the start (its repository folder
  is gone)
- **THEN** `docker logs` has the failure line with the reason, the session is stopped with
  `resume_at_start` 0, the other sessions are resumed, and at the container's next start
  it is not named

#### Scenario: The human resumes a session meanwhile
- **WHEN** while the start resumes sessions one by one, the human resumes from the UI a
  session it has not reached yet
- **THEN** that session keeps running, is not stopped or resumed again by the start, and
  `docker logs` says `lado: session "<name>" runs already at the container's start` when
  its resume was under way

#### Scenario: An open run's worker
- **WHEN** a session with an open run whose step is a worker's is resumed at the start
- **THEN** only its supervisor runs, and its first message from `lado` is `session
  resumed: 1 open run` naming the worker to start with `spawn_worker`

### Requirement: Outside a container the server's stop and start leave the sessions

When LADO does not run in a container, the UI server's end (`lado server stop`, SIGTERM,
Ctrl-C, `lado update`'s stop) SHALL change no session, and its start SHALL resume none.

#### Scenario: lado server stop on a machine
- **WHEN** a session runs and `lado server stop` ends the UI server without
  `LADO_CONTAINER`
- **THEN** the session still runs, and a new `lado server` resumes nothing

### Requirement: Stopping one LADO container leaves another's sessions

Stopping or starting one LADO container SHALL change no session of another LADO container
on the same machine.

#### Scenario: compose down of one of two
- **WHEN** two compose projects of `docker/compose.yaml`, each in its own folder with its
  own `.env`, each run a session, and the first runs `docker compose down`
- **THEN** the second's session still runs with its supervisor's same process, and the
  second's `lado.db` has no session stopped

### Requirement: The headers say that sessions follow the container

`docker/compose.yaml`'s header SHALL say that `docker compose down` (or stop) stops the
container's sessions and `docker compose up -d` resumes them, except those stopped by
hand, and that each resumed session's supervisor takes one model turn at the start; the
Dockerfile's header SHALL say the same for `docker stop` and `docker start`.

#### Scenario: The headers
- **WHEN** a unit test reads both headers
- **THEN** each says that the sessions stop with the container and resume at its start, and
  names the supervisor's model turn

### Requirement: The image takes the agents' variables from a secrets folder

The image SHALL set `LADO_ENV_DIR=/run/secrets` for the UI server and `docker exec` (the
processes that launch agents), so the agents get the variables of the files mounted there
(capability agent-variables).
- `docker/compose.yaml` SHALL bind the folder `LADO_SECRETS` names (default `./secrets`,
  next to the file) read-only at `/run/secrets`, refusing to start when that folder does
  not exist, rather than letting Docker make it.
- No variable for the agents SHALL be set through compose's `environment:` or the image's
  `ENV`, and `LADO_AGENT_ENV=inherit` SHALL not be set, so no value is in `docker
  inspect`.
- The headers SHALL say to make the folder with mode 700 and to put one file per variable
  in it (`GH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, a kit's key such as `YOUGILE_API_KEY`, a
  model provider's key). A new file reaches the agents started after it, with no
  restart. Each LADO container has its own folder, and every agent of one container can
  read every variable given to it.

#### Scenario: A kit that needs a variable starts
- **WHEN** a container runs with a folder holding `TEST_KIT_KEY` mounted at
  `/run/secrets`, and a session starts there with a kit whose role's MCP server has
  `env: {KEY: ${TEST_KIT_KEY}}`
- **THEN** the session and a worker of that role start, its supervisor's process has
  `TEST_KIT_KEY` with the file's value, and `docker inspect` of the container does not
  contain the value

#### Scenario: compose without the folder
- **WHEN** `docker compose up -d` runs in a folder without `secrets/` and without
  `LADO_SECRETS`
- **THEN** compose refuses and names the missing path

### Requirement: The container gives the agents the human's git identity

At every start of the container, the entrypoint, running as `lado`, SHALL write
`LADO_GIT_NAME` and `LADO_GIT_EMAIL`, when set and not empty, to `lado`'s global git
config (`user.name`, `user.email`) on the home volume. A repository's own config still
wins. When either is still missing from git's config after that, `docker logs` SHALL get
one line: `lado: warning: git has no user.name or user.email: agents cannot commit; set
LADO_GIT_NAME and LADO_GIT_EMAIL`. `docker/compose.yaml` SHALL pass both from `.env`, empty
by default.

#### Scenario: An agent's commit
- **WHEN** the container runs with `-e LADO_GIT_NAME="Ann Lee" -e
  LADO_GIT_EMAIL=ann@example.com` and an agent's shell commits in a worktree with no `-c`
- **THEN** the commit's author and committer are `Ann Lee <ann@example.com>`

#### Scenario: No identity
- **WHEN** the container runs without either variable on a fresh home volume
- **THEN** `docker logs` has the warning line, and the server starts

#### Scenario: A later change
- **WHEN** the container is made again with another `LADO_GIT_EMAIL` on the same home
  volume
- **THEN** git's global `user.email` is the new one

### Requirement: git over https to GitHub uses gh's token

The image's system git config SHALL make `gh auth git-credential` the only credential
helper for `https://github.com`. With `GH_TOKEN` in an agent's environment, or after `gh
auth login` in the container (its token in `~/.config/gh` on the home volume), git SHALL
get that token for `https://github.com` with no prompt and no extra step.

#### Scenario: The token from the secrets folder
- **WHEN** the secrets folder holds `GH_TOKEN` with a fake value and an agent's shell runs
  `git credential fill` for `protocol=https`, `host=github.com`
- **THEN** git prints `password=<that value>`

### Requirement: The host's ssh agent reaches the agents without root's group

`docker/compose.yaml` SHALL bind the path that `LADO_SSH_AGENT` names (default
`/dev/null`: no ssh agent) at `/run/lado/ssh-agent.sock`, refusing to start when that
path does not exist. When that path in the container is a socket, the image's profile
SHALL set `SSH_AUTH_SOCK=/run/lado/ssh-agent.sock` for every login shell, so for every
agent.

At every start, the entrypoint SHALL check, as `lado`, whether `lado` can use the socket:
- when it cannot and the socket belongs to uid 0, it SHALL run through `sudo` the image's
  program `/usr/local/bin/lado-ssh-agent-socket`, which takes no argument and keeps no
  variable of its caller (no `SETENV`). That program SHALL give that one path, only when
  it is a socket that is no symbolic link and belongs to uid 0, to `lado`'s uid, keeping
  its group.
- when `lado` still cannot use it, `docker logs` SHALL get one line, `lado: warning: lado
  (uid <uid>) cannot use the ssh agent socket of uid <owner>: <reason>`, and the server
  SHALL start.

The container SHALL need no `group_add`. The headers SHALL give `LADO_SSH_AGENT` for a
Mac (`/run/host-services/ssh-auth.sock`, Docker Desktop's) and for Linux (the host's
`$SSH_AUTH_SOCK`), and SHALL say that every agent of the container may then use the
host's keys.

#### Scenario: Docker Desktop's root-owned socket
- **WHEN** an ssh agent holding a test key listens on a socket owned by uid 0 at
  `/run/lado/ssh-agent.sock` (made by another container on a shared volume) and LADO's
  container starts, or restarts
- **THEN** `ssh-add -l` in an agent's login shell lists the test key, and `id -G` of
  `lado` has no 0

#### Scenario: A Linux host's socket of the projects' owner
- **WHEN** the socket belongs to the uid of the projects' owner, which `lado` takes
- **THEN** `ssh-add -l` in an agent's login shell lists the key, and the socket's owner is
  unchanged

#### Scenario: No ssh agent
- **WHEN** `LADO_SSH_AGENT` is not set
- **THEN** agents have no `SSH_AUTH_SOCK` from the image, and `docker logs` has no ssh line

#### Scenario: The rule gives no root
- **WHEN** an agent runs `sudo -n /usr/local/bin/lado-ssh-agent-socket` with any variable
  or argument
- **THEN** it can at most give that socket to `lado`, and `sudo -n true` fails

### Requirement: The headers say how the agents log in and get access

The headers of `docker/compose.yaml` and `docker/Dockerfile` SHALL say:
- how to give the agents variables (the secrets folder, one file per variable);
- the git identity (`LADO_GIT_NAME`, `LADO_GIT_EMAIL`);
- GitHub over https (`GH_TOKEN` in the folder, or `gh auth login` inside);
- the ssh agent (`LADO_SSH_AGENT` for a Mac and for Linux);
- the logins of the agent CLIs: Claude Code by `CLAUDE_CODE_OAUTH_TOKEN` (from `claude
  setup-token`) in the folder or one login inside; OpenCode and Kilo by `opencode auth
  login` and `kilo auth login` inside (kept on the home volume) or a model provider's key
  in the folder. Codex's login is not covered.

#### Scenario: The steps are in the headers
- **WHEN** `tests/test_docker.py` reads the headers
- **THEN** each names `secrets`, `LADO_GIT_NAME`, `LADO_GIT_EMAIL`, `GH_TOKEN`, `gh auth
  login`, `LADO_SSH_AGENT`, `CLAUDE_CODE_OAUTH_TOKEN`, `opencode auth login` and `kilo auth
  login`
