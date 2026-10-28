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
to run on the host (how to update a container is the documentation's).

#### Scenario: The human updates in a container
- **WHEN** the human runs `lado update --yes` in a container where LADO is a uv tool
  install and the UI server runs
- **THEN** it prints the container line on stderr and exits 1, the UI server and every
  session still run, and `update-result.json`, `update.json` and `update.log` are as they
  were

#### Scenario: A named version
- **WHEN** the human runs `lado update 0.36.0` in a container
- **THEN** the same refusal, and PyPI is not asked

#### Scenario: The same commands as the compose header
- **WHEN** `docker/compose.yaml`'s header says how to update and `lado update` refuses in
  a container
- **THEN** the refusal names none of the header's commands, no `docker` command and no
  `lado:previous`: how to update is the header's and the documentation's

### Requirement: The container's refusal of lado update comes after the agent's

Inside an agent the
agent's refusal of `lado update` SHALL come first; the container's refusal SHALL come before the refusal of
a running update and the missing installer.

#### Scenario: An agent in a container
- **WHEN** an agent runs `lado update` in a container
- **THEN** it gets the agent's refusal

### Requirement: The UI's update refuses in a container

In a container `GET /api/update` SHALL answer `can_update` false, `why_not` `LADO runs in
a container: a new image updates it, not lado update`, `by_hand` empty, and `container`
true (false outside one); `POST /api/update` SHALL answer 409 with that reason and start
nothing.

#### Scenario: A start of the update is refused
- **WHEN** a client posts `/api/update` in a container
- **THEN** it gets 409 with the reason, and no `lado update` process is started

### Requirement: The System panel shows the container and no Update… button

In a container the System panel SHALL show a grey `container` pill beside `LADO <version>` in its
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

#### Scenario: Outside a container
- **WHEN** the System panel opens without `LADO_CONTAINER`
- **THEN** it shows no `container` pill and `UpdateInfo.container` is false

### Requirement: lado doctor and the report say LADO runs in a container

In a container `lado doctor`'s LADO line SHALL end with `, in a container`, and the line
that a newer LADO is out (`update.available_line`, shown by `lado ls` and as
`lado doctor`'s hint) SHALL read `LADO <version> is available: a new image updates LADO in
a container (ghcr.io/ladohq/lado:<version>)` instead of naming `lado update`. The
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

### Requirement: The image's name is one constant

The image's name SHALL be one constant, `update.IMAGE`, that the Release workflow and
`docker/compose.yaml` publish and pull by (a unit test keeps the three the same).

#### Scenario: The names drift apart
- **WHEN** `update.IMAGE`, the image the Release workflow publishes and the image
  `docker/compose.yaml` pulls are not the same name
- **THEN** the unit tests fail

### Requirement: The UI server in a container names the port's publication, not other machines

In a container, a UI server listening on a non-loopback address SHALL decide its start
line by `LADO_LISTEN`, the host address compose publishes the port on:
- `LADO_LISTEN` a non-loopback IPv4 address (`0.0.0.0` too): the warning that the server
  is open to other machines, as outside a container, naming `LADO_LISTEN` and the port;
- `LADO_LISTEN` a loopback address: no line.

#### Scenario: Published to the network by compose
- **WHEN** the same server starts with `LADO_LISTEN=0.0.0.0`
- **THEN** its output has the warning that it is open to other machines, naming
  `0.0.0.0:8765`, and no note

#### Scenario: Published on this computer only by compose
- **WHEN** the same server starts with `LADO_LISTEN=127.0.0.1`
- **THEN** its output has neither the note nor the warning

### Requirement: Without LADO_LISTEN the server in a container notes how its port is published

In a container, a UI server listening on a non-loopback address with `LADO_LISTEN` unset
or not an IPv4 address SHALL print on stderr the one line `lado: note: the LADO
  server runs in a container and listens on <host>:<port> inside it; who reaches it
  depends on how the container publishes the port (127.0.0.1:<port>:<port>: this computer
  only). Published to other machines, the token travels unencrypted (plain HTTP).`
`lado server` and `lado ui` SHALL print the same line.

#### Scenario: The image's server starts
- **WHEN** `lado server --host 0.0.0.0 --port 8765` starts with `LADO_CONTAINER=1` and no
  `LADO_LISTEN`
- **THEN** its output has the note naming `0.0.0.0:8765` and no `open to other machines`

### Requirement: A server on loopback or outside a container warns as before

A server on a loopback address
SHALL print neither the warning nor the note, as outside a container. Outside a container the warning SHALL stay as
it is.

#### Scenario: The same server outside a container
- **WHEN** `lado server --host 0.0.0.0` starts without `LADO_CONTAINER`
- **THEN** it prints the warning that it is open to other machines, as before

### Requirement: lado ui in a container prints the link for the host's browser

In a container `lado ui` SHALL print the server's local link
(`http://127.0.0.1:<port>/?token=<token>` for a server on `0.0.0.0`) and SHALL NOT try to
open a browser. With `--no-open` its standard output SHALL be that one line; without it,
the link followed by the line `Open it in your browser on the host.`

#### Scenario: The launcher asks for the link
- **WHEN** `docker exec lado lado ui --no-open` runs against a server on `0.0.0.0:8765` in
  a container
- **THEN** standard output is exactly `http://127.0.0.1:8765/?token=<token>`, and stderr
  has the note

#### Scenario: lado ui without --no-open in a container
- **WHEN** the human runs `lado ui` in a container without `LADO_LISTEN`
- **THEN** no browser is opened, and it prints the link and `Open it in your browser on
  the host.`, and no `From another machine` line

### Requirement: lado ui adds the link for another device only when there is one

A `From another
machine` line of `lado ui` SHALL follow only when the link for another device exists (share-access,
"The link to another device follows one rule"): on standard output without `--no-open`,
on stderr with it.

#### Scenario: Outside a container
- **WHEN** `lado ui --no-open` runs without `LADO_CONTAINER` against a server on
  `0.0.0.0`
- **THEN** it prints the local link, then `From another machine: http://<address>:<port>/?token=<token>`
  with the address of share-access's rule, and the warning

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
the container's environment sets for the agents' sake; an agent's
environment comes from the user's login shell (`agent_env.resolve`), not from the
container's environment.

#### Scenario: An agent's lado doctor

- **WHEN** a Claude Code agent runs in a container of the image and `lado doctor` runs
  with exactly the environment of the agent's process
- **THEN** its LADO line ends with `in a container`

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

### Requirement: The agents get the container's own LADO_REPOS

The image SHALL set the container's own `LADO_REPOS` (the image's `/projects`, or the value given with `-e`)
in `/etc/profile.d/lado-repos.sh`, written at the container's first start.

#### Scenario: An agent's LADO_REPOS is the container's

- **WHEN** the container runs with `-e LADO_REPOS=/home/runner/projects` and an agent
  starts in it
- **THEN** the agent's process has `LADO_REPOS=/home/runner/projects`, not `/projects`

### Requirement: The compose file runs the published image of LADO_VERSION

`docker/compose.yaml` SHALL run LADO's published image of the version `LADO_VERSION` names,
`ghcr.io/ladohq/lado:${LADO_VERSION}`, unless `LADO_IMAGE` names another image (`lado:local`,
the tests'); without either compose SHALL refuse and name `LADO_VERSION`, and it SHALL
never default to `latest`.

#### Scenario: No version given
- **WHEN** the human runs `docker compose up -d` with neither `LADO_VERSION` nor
  `LADO_IMAGE`
- **THEN** compose refuses and names `LADO_VERSION`

#### Scenario: The published image by its version
- **WHEN** `.env` has `LADO_VERSION=0.39.0` and no `LADO_IMAGE`
- **THEN** `docker compose config` names the image `ghcr.io/ladohq/lado:0.39.0`

### Requirement: The compose file publishes one port number

`docker/compose.yaml` SHALL use one variable, `LADO_PORT` (8765 by default), as
both the server's port in the container and the published one,
`${LADO_LISTEN:-127.0.0.1}:${LADO_PORT}:${LADO_PORT}`, so the host's number and the
container's are always the same; `LADO_LISTEN` is the host address the port is published
on, the host's loopback unless `.env` names another.

#### Scenario: Published on this computer by default
- **WHEN** `.env` has neither `LADO_LISTEN` nor `LADO_PUBLIC_HOST`
- **THEN** `docker compose config` publishes `127.0.0.1:8765:8765` and gives the container
  `LADO_LISTEN=127.0.0.1`

### Requirement: The compose file tells the container where it is published

`docker/compose.yaml` SHALL give the container
`LADO_LISTEN` (`${LADO_LISTEN:-127.0.0.1}`) and `LADO_PUBLIC_HOST`
(`${LADO_PUBLIC_HOST:-}`), the name other devices reach the host by.

#### Scenario: Published to the network
- **WHEN** `.env` has `LADO_LISTEN=0.0.0.0` and `LADO_PUBLIC_HOST=kaos-mbp.local`
- **THEN** `docker compose config` publishes `0.0.0.0:8765:8765` and gives the container
  `LADO_LISTEN=0.0.0.0` and `LADO_PUBLIC_HOST=kaos-mbp.local`

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

### Requirement: The root step removes its own way to root first

The change of `lado`'s uid SHALL be made by a step that runs as root once per container
and, first of all, removes its way to it (a sudo rule for the entrypoint alone), so
that no process started after it, an agent included, can become root through it; the
image's one other sudo rule, for the ssh agent's socket (requirement "The host's ssh agent
reaches the agents without root's group"), runs one fixed program that takes no argument
and no variable and gives no root shell.

#### Scenario: No way to root is left

- **WHEN** the container has started
- **THEN** `sudo -n true` run as `lado` in it fails

### Requirement: With the entrypoint replaced, the root step runs nothing its caller chose

Where
the image's entrypoint was replaced, the rule stays; the root step SHALL then run no
program chosen by its caller's environment (its commands by a fixed PATH or full paths,
the caller's PATH given back only after the drop to `lado`), so that the rule runs only
that step's own work.

#### Scenario: The entrypoint replaced

- **WHEN** the container runs with `--entrypoint`, so the sudo rule stays, and `lado` runs
  the entrypoint through it with a `setpriv` of its own first on the PATH it hands over
- **THEN** that `setpriv` does not run, and the command runs as `lado`

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

### Requirement: git in the image trusts every repository

The image's system git configuration SHALL have `safe.directory = *`, so that git in the
container never refuses a repository of the workspace as of "dubious ownership",
whoever the folder's owner seems to be.

#### Scenario: A repository owned by another uid

- **WHEN** git runs as `lado` in the container on a repository whose files belong to
  another uid
- **THEN** `git status` there succeeds

### Requirement: A new image starts on an old home volume

A container of LADO's image whose home volume holds a `lado.db` of an older schema SHALL
migrate it at its start with the backup the capability `schema-migration` describes, and
`docker logs` SHALL show the upgrade line, or, when the migration fails, its message.

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

### Requirement: The compose header's update keeps the image before by its version

`docker/compose.yaml`'s header SHALL say that an update is that version's `compose.yaml`
downloaded next to `.env` and a new `LADO_VERSION` in `.env`, followed by `docker compose
up -d` (which pulls the image of that version; see "An update takes the version's
compose.yaml"), and that the
image before keeps its version's name, so no name is kept by hand and nothing names
`lado:previous`.

#### Scenario: The image before keeps a name
- **WHEN** a container is updated by the compose header's steps from one version to
  another
- **THEN** the image of the version before is still named by its version tag, and no
  step tags an image

### Requirement: The headers give the way back to the image before

The header of `docker/compose.yaml` SHALL give the steps that go back after a migration that succeeded:
put the version before back in `.env`, stop the container, put the backup in place of
`lado.db` (with its `-wal` and `-shm` removed) with that image, and start it; after a
migration that failed, the first and the last step alone. The Dockerfile's header SHALL
say the same for `docker run`: the container removed and run again with the other
version's tag on the same home volume.

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
`resume_at_start` set, all sessions in one transaction.

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

### Requirement: The container's stop ends the sessions only after it marked them

Only after the transaction that marks the sessions SHALL the container's stop kill each
one's tmux session, close its UI viewers and remove its agents' config folders.

#### Scenario: The order of the stop
- **WHEN** the container's stop finds two sessions running
- **THEN** `lado.db` has both stopped with the mark before their tmux sessions are killed,
  their viewers closed and their agents' config folders removed

### Requirement: A session stopped before the container's stop keeps its mark

A session the container's stop finds stopped already SHALL keep its mark as it is.

#### Scenario: A session the human stopped
- **WHEN** a session was stopped with `lado stop` before the container's stop
- **THEN** it stays stopped without the mark, and the stop's line does not name it

### Requirement: The container's stop is said in its log and to no one else

The `session_stop`
event's detail of the container's stop SHALL end with `; the container stopped`. It SHALL print one line on stderr
(`docker logs`): `lado: the container stops: stopped sessions "<a>", "<b>"; they resume at
its start`, and none when no session ran. The agents that end by this SHALL tell no one, as after `lado stop`.

#### Scenario: No message about the dying agents
- **WHEN** the container's stop ends a session whose supervisor and worker run
- **THEN** no message from `lado` to the human or the supervisor is queued about their end,
  and `lado log` shows the session's stop with `the container stopped`

#### Scenario: Nothing ran
- **WHEN** the container stops with no session running
- **THEN** `docker logs` has no line about sessions

### Requirement: The container's stop makes no LADO_HOME

When `lado.db`
does not exist, the container's stop SHALL do nothing and make no `LADO_HOME`.

#### Scenario: The server's stop after an uninstall
- **WHEN** the server in a container ends after `LADO_HOME` was deleted
- **THEN** no `LADO_HOME` is made again

### Requirement: The container's start resumes its sessions after the migration

When the UI server starts in a container, after `lado.db` is migrated (the CLI migrates
before the command, as before), it SHALL resume in the background, while it already
serves, one session at a time: each stopped session with `resume_at_start` set, and each
session not stopped whose tmux session is gone (the container ended without its stop:
`docker kill`, a crash of Docker or the machine, or a tmux that ended inside the
container). It SHALL NOT resume a session stopped without the mark.

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

### Requirement: Each resume at the container's start is lado start's resume

Each resume at the container's start
SHALL be `lado start`'s resume of that session with its stored repository and settings, its
`session_resume` event's detail starting with `at the container's start`, and SHALL clear
`resume_at_start` in the transaction that takes the session.

#### Scenario: The human resumes a session meanwhile
- **WHEN** while the start resumes sessions one by one, the human resumes from the UI a
  session it has not reached yet
- **THEN** that session keeps running, is not stopped or resumed again by the start, and
  `docker logs` says `lado: session "<name>" runs already at the container's start` when
  its resume was under way

### Requirement: Each resume at the container's start is said in docker logs

`docker logs` SHALL get
`lado: resumed session "<name>" at the container's start` for each one resumed, followed
by `lado: session "<name>": <line>` for each problem and warning `lado start` prints for
that resume (an open run that cannot go on, a kit's or the provider's warning).

#### Scenario: A resume with a warning
- **WHEN** a session whose open run cannot go on is resumed at the container's start
- **THEN** `docker logs` has `lado: resumed session "<name>" at the container's start`,
  followed by `lado: session "<name>": <the line lado start prints about that run>`

### Requirement: A resume that fails at the start leaves its session stopped

`docker logs` SHALL get `lado: could not resume session "<name>" at the container's start: <error>; it stays
stopped` for a resume at the start that fails, which stays stopped without the mark and is not tried at the
next start; the others SHALL go on. When the server is told to end while it resumes, it SHALL
resume no further session.

#### Scenario: A resume that fails
- **WHEN** a session with the mark cannot be resumed at the start (its repository folder
  is gone)
- **THEN** `docker logs` has the failure line with the reason, the session is stopped with
  `resume_at_start` 0, the other sessions are resumed, and at the container's next start
  it is not named

### Requirement: LADO restarts no worker at the container's start

Workers SHALL NOT be restarted by LADO at the container's start: the
supervisor's `session resumed` message names the open runs and the workers to start for
them, as after `lado start`.

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
- No variable for the agents SHALL be set through compose's `environment:` or the image's
  `ENV`, and `LADO_AGENT_ENV=inherit` SHALL not be set, so no value is in `docker
  inspect`.

#### Scenario: A kit that needs a variable starts
- **WHEN** a container runs with a folder holding `TEST_KIT_KEY` mounted at
  `/run/secrets`, and a session starts there with a kit whose role's MCP server has
  `env: {KEY: ${TEST_KIT_KEY}}`
- **THEN** the session and a worker of that role start, its supervisor's process has
  `TEST_KIT_KEY` with the file's value, and `docker inspect` of the container does not
  contain the value

### Requirement: compose binds the secrets folder read-only, no folder by default

`docker/compose.yaml` SHALL bind the path `LADO_SECRETS` names read-only at
`/run/secrets`, by default `/dev/null`: no secrets, as for the ssh agent. It SHALL refuse
to start when a folder `LADO_SECRETS` names does not exist, rather than letting Docker
make it (`create_host_path: false`).

#### Scenario: Secrets enabled by one line
- **WHEN** `.env` has `LADO_SECRETS=./secrets`, the folder `secrets/` next to
  `compose.yaml` holds `GH_TOKEN` with a fake value, and `docker compose up -d` runs
- **THEN** an agent's shell has `GH_TOKEN` with that value, and `lado doctor` prints
  `[ok  ] Variables from outside: /run/secrets: GH_TOKEN`

#### Scenario: The folder named but missing
- **WHEN** `.env` has `LADO_SECRETS=./secrets` and there is no `secrets/`
- **THEN** compose refuses to start and names the missing path, and no folder is made

### Requirement: With no secrets the container says nothing about the folder

With no secrets (the null device at `/run/secrets`, or nothing mounted there, as with
`docker run` without the folder), the container SHALL say nothing about the folder in
`docker logs`, and `lado start` no warning about it; `lado doctor` says how to give
secrets (capability agent-variables).

#### Scenario: compose without the folder
- **WHEN** `docker compose up -d` runs in a folder with `compose.yaml` and `.env`, without
  `secrets/` and without `LADO_SECRETS`
- **THEN** the container starts, `lado doctor` exits 0 with `[info] Variables from
  outside: /run/secrets: none` and no warning, `docker compose logs lado` has no line
  about `/run/secrets` or `LADO_ENV_DIR`, and a session with the fake endpoint reaches
  idle

### Requirement: The headers say that the secrets folder is optional and how to enable it

The headers SHALL say that the secrets folder is optional and is enabled by
`LADO_SECRETS=./secrets` in `.env` (compose) or `-v <folder>:/run/secrets:ro` (`docker
run`).

#### Scenario: The headers on the secrets folder
- **WHEN** the human reads the headers of `docker/compose.yaml` and `docker/Dockerfile`
- **THEN** they say that the folder is optional, enabled by `LADO_SECRETS=./secrets` or
  `-v <folder>:/run/secrets:ro`

### Requirement: The headers say how to fill the secrets folder

The headers SHALL say to make the secrets folder with mode 700 and to put one file per
variable in it (`GH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, a kit's key such as
`YOUGILE_API_KEY`, a model provider's key). A new file reaches the agents started after
it, with no restart. Each LADO container has its own folder or none, and every agent of
one container can read every variable given to it.

#### Scenario: The headers on the folder's files
- **WHEN** the human reads the headers of `docker/compose.yaml` and `docker/Dockerfile`
- **THEN** they say to make the folder with mode 700 and to put one file per variable in
  it, such as `GH_TOKEN`

### Requirement: The container gives the agents the human's git identity

At every start of the container, the entrypoint, running as `lado`, SHALL write
`LADO_GIT_NAME` and `LADO_GIT_EMAIL`, when set and not empty, to `lado`'s global git
config (`user.name`, `user.email`) on the home volume. A repository's own config still
wins. `docker/compose.yaml` SHALL pass both from `.env`, empty
by default.

#### Scenario: An agent's commit
- **WHEN** the container runs with `-e LADO_GIT_NAME="Ann Lee" -e
  LADO_GIT_EMAIL=ann@example.com` and an agent's shell commits in a worktree with no `-c`
- **THEN** the commit's author and committer are `Ann Lee <ann@example.com>`

#### Scenario: A later change
- **WHEN** the container is made again with another `LADO_GIT_EMAIL` on the same home
  volume
- **THEN** git's global `user.email` is the new one

### Requirement: A container without the git identity warns in its log

When `user.name` or `user.email` is still missing from git's config after the entrypoint wrote the identity, `docker logs` SHALL get
one line: `lado: warning: git has no user.name or user.email: agents cannot commit; set
LADO_GIT_NAME and LADO_GIT_EMAIL`.

#### Scenario: No identity
- **WHEN** the container runs without either variable on a fresh home volume
- **THEN** `docker logs` has the warning line, and the server starts

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
path does not exist. The container SHALL need no `group_add`. The headers SHALL give `LADO_SSH_AGENT` for a
Mac (`/run/host-services/ssh-auth.sock`, Docker Desktop's) and for Linux (the host's
`$SSH_AUTH_SOCK`), and SHALL say that every agent of the container may then use the
host's keys.

#### Scenario: A missing ssh agent socket
- **WHEN** `.env` has `LADO_SSH_AGENT=/run/missing.sock` and that path does not exist
- **THEN** compose refuses to start and names the path

### Requirement: The entrypoint gives a root's socket to lado through one fixed program

At every start, the entrypoint SHALL check, as `lado`, whether `lado` can use the socket:
- when it cannot and the socket belongs to uid 0, it SHALL run through `sudo` the image's
  program `/usr/local/bin/lado-ssh-agent-socket`, which takes no argument and keeps no
  variable of its caller (no `SETENV`). That program SHALL give that one path, only when
  it is a socket that is no symbolic link and belongs to uid 0, to `lado`'s uid, keeping
  its group.

#### Scenario: Docker Desktop's root-owned socket
- **WHEN** an ssh agent holding a test key listens on a socket owned by uid 0 at
  `/run/lado/ssh-agent.sock` (made by another container on a shared volume) and LADO's
  container starts, or restarts
- **THEN** `ssh-add -l` in an agent's login shell lists the test key, the UI server's
  process has `SSH_AUTH_SOCK=/run/lado/ssh-agent.sock`, and `id -G` of `lado` has no 0

#### Scenario: The rule gives no root
- **WHEN** an agent runs `sudo -n /usr/local/bin/lado-ssh-agent-socket` with any variable
  or argument
- **THEN** it can at most give that socket to `lado`, and `sudo -n true` fails

### Requirement: An ssh agent's socket lado cannot use is a warning

When `lado` still cannot use the ssh agent's socket after the entrypoint's check, `docker
logs` SHALL get one line, `lado: warning: lado (uid <uid>) cannot use the ssh agent socket
of uid <owner>: <reason>`, and the server SHALL start.

#### Scenario: A socket of another user
- **WHEN** the socket belongs to uid 1234, not 0, and `lado` (uid 1000) may not use it
- **THEN** `docker logs` has `lado: warning: lado (uid 1000) cannot use the ssh agent
  socket of uid 1234: <reason>`, and the server starts

### Requirement: The headers say how the agents log in and get access

The headers of `docker/compose.yaml` and `docker/Dockerfile` SHALL say:
- how to give the agents variables (the optional secrets folder, enabled by
  `LADO_SECRETS=./secrets` in `.env` or `-v <folder>:/run/secrets:ro`, one file per
  variable);
- the git identity (`LADO_GIT_NAME`, `LADO_GIT_EMAIL`);
- GitHub over https (`GH_TOKEN` in the folder, or `gh auth login` inside);
- the ssh agent (`LADO_SSH_AGENT` for a Mac and for Linux).

#### Scenario: The steps are in the headers
- **WHEN** `tests/test_docker.py` reads the headers
- **THEN** each names `secrets`, `LADO_GIT_NAME`, `LADO_GIT_EMAIL`, `GH_TOKEN`, `gh auth
  login`, `LADO_SSH_AGENT`, `CLAUDE_CODE_OAUTH_TOKEN`, `opencode auth login` and `kilo auth
  login`; compose's names `LADO_SECRETS=./secrets`

### Requirement: The headers say how the agent CLIs log in, and the first start makes no folder

The headers of `docker/compose.yaml` and `docker/Dockerfile` SHALL also say:
- the logins of the agent CLIs: Claude Code by `CLAUDE_CODE_OAUTH_TOKEN` (from `claude
  setup-token`) in the folder or one login inside; OpenCode and Kilo by `opencode auth
  login` and `kilo auth login` inside (kept on the home volume) or a model provider's key
  in the folder. Codex's login is not covered.
The first start's commands of both headers SHALL make no folder: the minimal start needs
no secrets.

#### Scenario: The minimal start makes no folder
- **WHEN** `tests/test_docker.py` reads the first start's commands of both headers
- **THEN** none of them is a `mkdir`

### Requirement: The image knows GitHub's ssh host keys

The image SHALL hold GitHub's published public ssh host keys for `github.com` in
`/etc/ssh/ssh_known_hosts`, copied from `docker/ssh_known_hosts`, so the first ssh to
github.com on a new home volume asks no question and ssh still refuses a key that is not
GitHub's. The file SHALL hold only lines for `github.com`, one per key type GitHub
publishes (ed25519, ecdsa-sha2-nistp256, rsa).

#### Scenario: The first ssh on a new volume
- **WHEN** a container on a new home volume, with no ssh agent, runs `ssh -T -o
  BatchMode=yes git@github.com` in `lado`'s login shell
- **THEN** it fails on the missing key (`Permission denied (publickey)`), never with
  `Host key verification failed`, and `~/.ssh/known_hosts` gets no line

#### Scenario: The file
- **WHEN** `tests/test_docker.py` reads `docker/ssh_known_hosts`
- **THEN** every line names `github.com`, and its key types are ed25519,
  ecdsa-sha2-nistp256 and rsa

### Requirement: The image holds no private data

The image SHALL hold no key, login, password or token of any person: the human gives
their own at run time (the secrets folder, logins on the home volume, the host's ssh
agent). The only keys the build puts in it SHALL be public host keys. The build context
SHALL stay the allowlist of `docker/Dockerfile.dockerignore`, which names each file the
build takes.

#### Scenario: The build context
- **WHEN** `tests/test_docker.py` reads `docker/Dockerfile.dockerignore`
- **THEN** it lets in only `dist/lado-*.whl`, `docker/profile.sh`,
  `docker/entrypoint.sh`, `docker/ssh-agent-socket.sh`, `docker/ssh-agent-env.sh` and
  `docker/ssh_known_hosts`

### Requirement: The install guide leads with compose and runs the headers' commands

docs/install.md SHALL have a section `Docker` that leads with compose: get `compose.yaml`,
write `.env`, start, open the UI, the agents' variables (the optional `secrets/`, enabled
by `LADO_SECRETS=./secrets` in `.env` and `mkdir -m 700 secrets`), log in to the agent
CLIs, ssh, update and go back, a second LADO, the sessions, removal and the pitfalls;
README's Install SHALL link to it.

#### Scenario: Secrets as a step of their own
- **WHEN** `tests/test_docker.py` reads the guide's Docker section and README's Docker
  install
- **THEN** neither start has `mkdir`, and the guide's "The agents' variables" has
  `LADO_SECRETS=./secrets` and `mkdir -m 700 secrets`

### Requirement: The guide's commands are the compose header's

The guide's start, update and way-back commands SHALL be
exactly those of `docker/compose.yaml`'s header, which the container tests run (the
update's download is checked by its address, not run). Its `.env` SHALL name every
variable compose reads but `LADO_IMAGE` and `LADO_SECRETS`.

#### Scenario: The commands agree
- **WHEN** `tests/test_docker.py` reads the guide's code blocks and the header
- **THEN** the guide's start commands, its update (the version's `compose.yaml`, then
  `docker compose up -d`) and its way back (`way_back()`) are the header's

### Requirement: The guide removes only its own container and volume

The guide SHALL remove only its own
container and volume, by name, and nothing in the guide or the headers SHALL run a
`docker ... prune`.

#### Scenario: Removal by name
- **WHEN** the test reads the guide's removal
- **THEN** it runs `docker compose down` and `docker volume rm` of the compose project's
  own `home` volume, and README.md, docs/*.md and docker/ hold no `prune` (docs/research/ and
  docs/superpowers/ are records, not read as instructions)

### Requirement: The guide and README check the shell's variables first

The guide SHALL say to check `env | grep -E '^(LADO|COMPOSE)_'` and
`unset` what the shell sets, since a shell's variable beats `.env`. README's Docker install SHALL start without `mkdir`, and SHALL first check the shell
with `env | grep -E '^(LADO|COMPOSE)_'` and `unset`, as the guide does.

#### Scenario: README checks the shell first
- **WHEN** `tests/test_docker.py` reads README's Docker install
- **THEN** its commands have `env | grep -E '^(LADO|COMPOSE)_'` and an `unset` naming
  `LADO_VERSION` and `COMPOSE_PROJECT_NAME`, both before `docker compose up -d`

### Requirement: The guide's first session names Claude Code's trust question

The guide's "Your first session" SHALL say that LADO records Claude Code's trust in the
repository a session is started in, so Claude Code does not ask; that the repository's own
Claude Code settings and MCP servers then run without a question; and that when LADO
cannot record it, the agent waits in Needs you for Claude Code's question, whose answers
the scenario names.

#### Scenario: The guide on the trust question
- **WHEN** the human reads the guide's Docker "Your first session"
- **THEN** it says that LADO trusts the repository for Claude Code itself and that the
  repository's own Claude Code settings and MCP servers run, and that when LADO cannot,
  the agent waits in Needs you and "Yes, I trust this folder" answers it while Enter alone
  answers "No, exit" and closes the agent

### Requirement: The guide quotes the trust answers as LADO's reason words them

The guide's two answers to Claude Code's trust question SHALL be quoted as LADO's own
reason for that wait words them.

#### Scenario: The first session names Claude Code's trust question
- **WHEN** `tests/test_docker.py` reads the guide's Docker "Your first session"
- **THEN** it names Needs you and quotes "Yes, I trust this folder" and "No, exit", and
  each quoted answer is in the reason `ClaudeProvider.first_hook_blocker` gives for a folder
  Claude Code does not trust when LADO cannot record the trust (a config folder it cannot
  write)

### Requirement: README and the guide present Docker first, then PyPI

README's Install and docs/install.md's opening SHALL present the two ways to install,
Docker first and recommended, then PyPI, each with what it is for and what it needs; PyPI's
differences by system (macOS, Linux, Windows inside WSL2) SHALL be named there too.

#### Scenario: Two ways, Docker first
- **WHEN** `tests/test_docker.py` reads README's Install and docs/install.md's opening
- **THEN** each names Docker as recommended before PyPI, and docs/install.md's `## Docker`
  comes before its systems' sections

### Requirement: An update takes the version's compose.yaml

`docker/compose.yaml`'s header, docs/install.md's "Update the container" and README's
Docker update SHALL update in this order, in the folder of `compose.yaml`: keep a copy of
the file (`cp compose.yaml compose.yaml.bak`), download that version's `compose.yaml` next
to `.env` (`curl -fLO
https://github.com/ladohq/lado/releases/download/v<version>/compose.yaml`), set the new
`LADO_VERSION` in `.env`, then `docker compose up -d`.

#### Scenario: The address is the release's asset
- **WHEN** `tests/test_docker.py` reads the update's address and the release workflow's
  `gh release create`
- **THEN** the address's tag is `v` and the version, as `$GITHUB_REF_NAME` is, and its
  file is the asset `compose.yaml`

#### Scenario: README's update
- **WHEN** `tests/test_docker.py` reads README's `## Update`, `### Docker`
- **THEN** it downloads `releases/download/v<version>/compose.yaml` before `docker compose
  up -d`

### Requirement: An update says what stays and touches no other LADO

The update's steps SHALL say that `.env`,
`secrets/` and the home volume stay, that a change made to `compose.yaml` by hand must be
carried over to the new file (`diff compose.yaml.bak compose.yaml` shows it), and that
with several LADOs each is updated in its own folder with its own `.env`. Going back to
the version before SHALL keep the current `compose.yaml`. No step SHALL touch another
LADO's folder, container or volume.

#### Scenario: The header's update
- **WHEN** `tests/test_docker.py` reads the header's update
- **THEN** its commands are `cp compose.yaml compose.yaml.bak`, the `curl -fLO` of
  `releases/download/v<version>/compose.yaml`, then `docker compose up -d`, and its text
  names `LADO_VERSION` in `.env`, `diff compose.yaml.bak compose.yaml` and each LADO in
  its own folder

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

### Requirement: Only the supervisor sets a tool's default version, and only in a container

The supervisor's mise paragraph SHALL say that only it sets a tool's container-wide
default version (`mise use -g`); a worker's SHALL say to ask the supervisor for one.
Outside a container the paragraph SHALL be absent.

#### Scenario: The supervisor in a container

- **WHEN** LADO runs with `LADO_CONTAINER=1` and starts a session
- **THEN** the supervisor's instructions hold the mise paragraph with the sentence that
  only it sets a default version

#### Scenario: Outside a container

- **WHEN** LADO runs without `LADO_CONTAINER` and starts a session with a worker
- **THEN** no agent's instructions name mise

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

### Requirement: The image carries the system libraries of Playwright's Chromium

The image SHALL carry, from Debian in an apt layer of its own, the packages Playwright
installs for Chromium on Debian 12: `libasound2`, `libatk-bridge2.0-0`, `libatk1.0-0`,
`libatspi2.0-0`, `libcairo2`, `libcups2`, `libdbus-1-3`, `libdrm2`, `libgbm1`,
`libglib2.0-0`, `libnspr4`, `libnss3`, `libpango-1.0-0`, `libx11-6`, `libxcb1`,
`libxcomposite1`, `libxdamage1`, `libxext6`, `libxfixes3`, `libxkbcommon0`, `libxrandr2`.

#### Scenario: Playwright's Chromium starts in a new container

- **WHEN** a login shell as `lado`, started from a clean environment as LADO starts an
  agent's, in a new container on a new home volume installs the headless shell of
  Playwright at the version `uv.lock` names
- **THEN** `ldd` of its `chrome-headless-shell` names no library `not found`, and that
  Playwright launches Chromium, which renders a page with Latin and Cyrillic text and
  gives the text back

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

### Requirement: The image gives the agents and the server the host's ssh agent socket

When the path `/run/lado/ssh-agent.sock` in the container is a socket, the image SHALL set
`SSH_AUTH_SOCK=/run/lado/ssh-agent.sock` for every login shell, so for every agent, and
for the UI server, whose Clone from URL and branch listing run git over ssh: one rule,
`docker/ssh-agent-env.sh` at `/etc/profile.d/lado-ssh-agent.sh`, which the entrypoint
sources before the command, after the entrypoint's check of the socket.

#### Scenario: A Linux host's socket of the workspace's owner
- **WHEN** the socket belongs to the uid of the workspace's owner, which `lado` takes
- **THEN** `ssh-add -l` in an agent's login shell lists the key, and the socket's owner is
  unchanged

#### Scenario: No ssh agent
- **WHEN** `LADO_SSH_AGENT` is not set
- **THEN** agents and the UI server have no `SSH_AUTH_SOCK` from the image, and `docker
  logs` has no ssh line

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

### Requirement: The image carries uvx beside uv

The image SHALL carry `uvx` in `/usr/local/bin` beside `uv`, both copied from the one
pinned `uv` stage of `docker/Dockerfile` (the image `ghcr.io/astral-sh/uv`), so that an
agent's `uvx` is uv's own at uv's version, needs no mise, and answers before any mise
shim on `PATH`.

#### Scenario: uvx answers at uv's version in an agent's shell

- **WHEN** a login shell as `lado`, started from a clean environment as LADO starts an
  agent's, runs `command -v uvx`, `uvx --version` and `uv --version` in a new container on
  a new home volume
- **THEN** `uvx` is `/usr/local/bin/uvx`, and `uvx --version` answers with exit 0 and the
  same version number as `uv --version`

#### Scenario: uvx runs a package

- **WHEN** such a shell runs `uvx` offline with a local wheel's console script and the
  image's Python
- **THEN** the script runs and prints its output, and nothing is installed under
  `/opt/uv`

#### Scenario: The copy leaves uvx out

- **WHEN** `docker/Dockerfile` copies from the `uv` stage without `/uvx` into
  `/usr/local/bin`
- **THEN** the unit tests fail and name it

### Requirement: The headers name the UI's login first

The headers of `docker/compose.yaml` and `docker/Dockerfile` SHALL name, before the
terminal's ways to log the agent CLIs in, the UI's Settings → Providers and environment,
which logs Claude Code, OpenCode and Kilo in from the page, a phone too, and keeps Claude
Code's token.

#### Scenario: The headers name the UI's login
- **WHEN** `tests/test_docker.py` reads both headers
- **THEN** each names `Providers and environment`
