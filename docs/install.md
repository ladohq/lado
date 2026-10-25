# Installing LADO

There are two ways to install LADO: **Docker**, the recommended one, and **PyPI**.

| | Docker (recommended) | PyPI (`uv tool install lado`) |
|---|---|---|
| What you install | Docker only: the image holds LADO, tmux, git, gh and the four agent CLIs at the versions LADO is tested with | tmux, git, uv and an agent CLI on your computer, then LADO |
| What the agents reach | your workspace folder and the keys you give them (files in `secrets/`, your ssh agent); not the rest of your computer | everything you can: they run as you |
| Agent CLI logins | made once inside the container, or a token in `secrets/`; your own CLI config stays as it is. Codex's login is not carried yet | the logins and config your CLIs already have |
| How you work | the web UI; commands as `docker compose exec lado lado ...` | the terminal (`lado start`, tmux windows with `lado attach`) and the web UI |
| Update and back | a new `LADO_VERSION` in `.env` and `docker compose up -d`; the version before the same way | `lado update` |
| More than one LADO | side by side, each with its own folder, version, logins and keys | one per `LADO_HOME` |
| Systems | macOS (Docker Desktop) and Linux; Windows not checked yet | macOS, Linux, and Windows inside WSL2 |

Take **Docker** unless you want LADO in your own terminal with the agent CLIs you already
use, or you are on Windows: the agents work apart from the rest of your computer, nothing
but Docker is installed, every CLI is at its tested version, and an update or a step back is
one line.

**PyPI** installs LADO on your computer, and what it needs differs by system:

- **macOS**: tmux and uv from [Homebrew](https://brew.sh); git from the Xcode command line
  tools or Homebrew.
- **Linux**: git, tmux and curl from the system's packages (apt on Debian and Ubuntu), uv
  from its installer.
- **Windows**: only inside WSL2, in Ubuntu, exactly as on Linux; native Windows is refused
  with a pointer to WSL2.

On every system LADO from PyPI needs:

- **tmux** (3.3 or newer for the best experience; 3.2 works, see
  [tmux older than 3.3](#lado-doctor-warns-about-tmux-older-than-33)),
- **git** (2.31 or newer, see [git older than 2.31](#lado-doctor-warns-about-git-older-than-231)),
- **[uv](https://docs.astral.sh/uv/)**, which installs LADO and the Python it runs on,
- **one agent CLI**: Claude Code, Codex, Kilo or OpenCode, logged in once.

`lado doctor` checks tmux, git and the agent CLIs and prints the command to install what is
missing. The short version of this guide is in [README.md](../README.md#install).

- [Docker](#docker) (recommended)
- PyPI: [macOS](#macos), [Linux](#linux), [Windows](#windows), [Agent CLIs](#agent-clis),
  [Your first session](#your-first-session), [Uninstall](#uninstall)
- [Update](#update): Docker and PyPI
- [Common problems](#common-problems)

## Docker

LADO's image, `ghcr.io/ladohq/lado:<version>`, holds LADO, tmux, git, gh, the ssh client
and the four agent CLIs at the versions LADO is tested with: nothing to install but
Docker. It runs the web UI on this computer's loopback; the agents work in your workspace
folder, which the container sees at the same path as your computer, so their commits and
worktrees are yours too. The image holds no one's keys or logins: you give your own at run
time (a login inside, your ssh agent, a secrets folder if you want one). Compose keeps
every setting in `.env`, so an update is a new `compose.yaml` and one line;
[`docker run`](#with-docker-run) works too.

The headers of [docker/compose.yaml](../docker/compose.yaml) and
[docker/Dockerfile](../docker/Dockerfile) are the reference; this guide repeats the steps
you run.

### Prerequisites

- **macOS**: [Docker Desktop](https://www.docker.com/products/docker-desktop/).
- **Linux**: Docker Engine with the compose plugin (`docker compose version` answers).

### Check the shell

A variable set in your shell beats the same one in `.env`: a `LADO_VERSION` left from an
earlier try runs that version, whatever `.env` says. Look first, and unset what you find:

```bash
env | grep -E '^(LADO|COMPOSE)_'
unset LADO_VERSION LADO_WORKSPACE LADO_PROJECTS LADO_PORT LADO_IMAGE COMPOSE_PROJECT_NAME   # each name printed
```

### Get compose.yaml and write .env

A folder of its own for this LADO, with the compose file of the latest release:

```bash
mkdir ~/lado-docker && cd ~/lado-docker
curl -fLO https://github.com/ladohq/lado/releases/latest/download/compose.yaml
```

Next to it, a file `.env` with your settings; compose reads it for every command run in
this folder. On a Mac:

```ini
LADO_VERSION=<version>              # the LADO version to run, e.g. the latest release's
LADO_WORKSPACE=/Users/ann/workspace # your workspace folder, a full path
LADO_PORT=8765                      # the UI's port on this computer
LADO_GIT_NAME="Ann Lee"             # git's identity for the agents' commits
LADO_GIT_EMAIL=ann@example.com
LADO_SSH_AGENT=/run/host-services/ssh-auth.sock   # Docker Desktop's ssh agent
# LADO_LISTEN=0.0.0.0               # a phone too: see Open LADO on your phone
# LADO_PUBLIC_HOST=ann-mbp.local
```

On Linux:

```ini
LADO_VERSION=<version>              # the LADO version to run, e.g. the latest release's
LADO_WORKSPACE=/home/ann/workspace  # your workspace folder, a full path
LADO_PORT=8765                      # the UI's port on this computer
LADO_GIT_NAME="Ann Lee"             # git's identity for the agents' commits
LADO_GIT_EMAIL=ann@example.com
LADO_SSH_AGENT=/run/user/1000/ssh-agent.socket    # your ssh agent: echo $SSH_AUTH_SOCK
# LADO_LISTEN=0.0.0.0               # a phone too: see Open LADO on your phone
# LADO_PUBLIC_HOST=ann-laptop.local
```

`<version>` is a LADO version without `v`, e.g. the newest on the
[releases page](https://github.com/ladohq/lado/releases). `LADO_WORKSPACE` is the only
folder of your computer the agents see; an `.env` that names it `LADO_PROJECTS`, its name
before 0.43.0, is still accepted. The folder must exist: compose never makes it. For the
examples above:

```bash
mkdir -p ~/workspace
```

`LADO_SSH_AGENT` is
optional: without it there is no ssh in the container. On Linux the socket's path may
change with each login: point it at a stable one, or run `docker compose up -d` again after
a new login.

### Start

```bash
docker compose up -d
docker compose exec lado lado ui --no-open   # the UI's link with its token
```

Open the link in your browser. `docker compose logs lado` shows what the container says,
its warnings too.

### The agents' variables

Optional: many agents need none, since Claude Code, gh, OpenCode and Kilo can log in inside
the container (below). Tokens and keys for the agents are files in a folder `secrets/`,
one per variable: the file's name is the variable's, its content the value. To give them,
add a line to `.env`:

```ini
LADO_SECRETS=./secrets
```

then make the folder, readable only by you, and start again:

```bash
mkdir -m 700 secrets
docker compose up -d
```

With `LADO_SECRETS` set, compose refuses to start while the folder is missing rather than
make it; without it the container has none and says nothing about it
(`docker compose exec lado lado doctor` says how to give them). LADO reads the files at
each agent's start, so a new file reaches the next agent with no restart; they never show
in `docker inspect`, and `lado doctor` lists the names it uses. For example, git over
https and `gh` with your GitHub token:

```bash
printf %s "$(gh auth token)" > secrets/GH_TOKEN
```

Others: `CLAUDE_CODE_OAUTH_TOKEN` (below), a kit's key as its MCP server names it (e.g.
`YOUGILE_API_KEY`), a model provider's key for OpenCode and Kilo. Every agent of this LADO
can read every file of its `secrets/`.

A variable only one project's agents should get, or with another value there (a board's
address, a local model's), is set per project instead, no file needed: `docker compose exec
lado lado project set <project> NAME VALUE` ([cli.md](cli.md)); the project's value wins
over the folder's for that project's sessions. A key one project's agents should get (each
client's own board or GitHub token) is set as the project's secret, typed without echo or
piped in, never on the command line:

```bash
docker compose exec -it lado lado project set <project> YOUGILE_API_KEY --secret
printf %s "$(gh auth token)" | docker compose exec -T lado lado project set <project> GH_TOKEN --secret
```

LADO keeps it in its home volume (`~/.lado/projects/<project>/secrets/`), shows only its
name (`lado project show`), and removes it with `lado project unset` or with the project. A
backup of the home volume holds the projects' secrets: keep it as you keep the keys. The
projects of one LADO are no security boundary: an agent of one project can read another's
secrets. For clients that must not mix, run a separate LADO.

### Log in to the agent CLIs

Logins made inside the container stay on its home volume, through updates.

- **Claude Code**: log in once inside, as on your computer (it prints a link to open in
  your browser and asks for the code it shows):

  ```bash
  docker compose exec -it lado claude
  ```

  Then `/exit`. Or, instead, a long-lived token: run `claude setup-token` on your computer
  and put what it prints in `secrets/CLAUDE_CODE_OAUTH_TOKEN` (`printf %s '<token>' >
  secrets/CLAUDE_CODE_OAUTH_TOKEN`, with [the folder](#the-agents-variables) given).
- **OpenCode and Kilo**: `docker compose exec -it lado opencode auth login` or
  `docker compose exec -it lado kilo auth login`, or the model provider's key in `secrets/`.
- **Codex**: not covered in the container yet.

### git over ssh

The agents push over ssh with your computer's ssh agent (`LADO_SSH_AGENT`), and the web
UI's **Clone from URL** clones an ssh address (`git@github.com:...`) with it: every agent of
this LADO may use the keys it holds. The key GitHub knows must be in that agent:

```bash
ssh-add -l                                   # your keys; none: add yours
ssh-add --apple-use-keychain ~/.ssh/id_ed25519   # on a Mac; on Linux: ssh-add ~/.ssh/id_ed25519
docker compose exec lado bash -lc 'ssh -T git@github.com'
```

The last line answers `Hi <you>! You've successfully authenticated`. The image knows
GitHub's host keys, so ssh asks nothing; another host's key: see
[If something goes wrong in Docker](#if-something-goes-wrong-in-docker).

### Your first session

In the UI, **Launch**: **Where** starts in your workspace; pick a repository there (it
needs a first commit), or **Clone from URL**, which clones into it. No repository yet? Your
first window opens in **From scratch**: type a name, and LADO makes a new folder with an
empty git repository there (no GitHub needed). A folder outside the
workspace lives only in the container: the window warns about it. Choose the agent
CLI and press **Start session**.

The container's Claude Code has trusted no folder yet, so on a repository it has not seen
it asks whether to trust it before its first answer, in every permission mode. Meanwhile
the agent waits in **Needs you**, which says what to answer: open its terminal and choose "Yes, I trust this folder"; Enter alone answers
"No, exit" and closes the agent. It is asked once per repository (the workers' worktrees
are covered) and remembered on the home volume, so restarts and updates do not ask again;
another LADO container has its own home volume and asks once more. A trusted repository's
own Claude Code settings (`.claude/`) and MCP servers (`.mcp.json`) run, so trust only a
repository whose settings you accept.

### Open LADO on your phone

The container publishes the UI on this computer's loopback only. To open it from a phone
or another computer on your network, add two lines to `.env`, then start again:

```ini
LADO_LISTEN=0.0.0.0              # let the other devices of your network in
LADO_PUBLIC_HOST=ann-mbp.local   # this computer's name (or address), for the link
```

```bash
docker compose up -d
```

Inside its container LADO cannot learn this computer's name or address, so
`LADO_PUBLIC_HOST` gives it; or publish on one address instead of both lines:
`LADO_LISTEN=192.168.1.23`. Then in the UI: `live` (top right) → the QR-code icon, **Open on
another device**: scan the QR code with the phone's camera, or **Copy link** and send it.
`docker compose exec lado lado ui --no-open` prints the same link on its stderr, as
`From another machine: …`.

The link holds the token: whoever has it can run commands as you, and it travels
unencrypted (plain HTTP). Use it only on a network you trust. With `LADO_LISTEN=0.0.0.0`
a laptop is open on every network it joins: café Wi-Fi too. To take access back, **New
link…** in the same dialog logs out everyone who opened LADO with the old link, without a
restart; this browser stays in.

### The repositories' toolchains

The image has git, Node.js 22, uv, `make`, `gcc` and `g++`, the agents' everyday tools
(`jq`, `rg`, `unzip`, `zip`, `xz`, `bzip2`, `patch`, `file`, `rsync`, `sqlite3`, `tree`,
`lsof`, `nc`), openspec, `python3` and `python`, and [mise](https://mise.jdx.dev) for the
rest. An agent that needs a tool the repository lacks (Go,
Rust, Java, a Python, ...) installs it with mise by itself: by the repository's version files
(`.tool-versions`, `mise.toml`, `.go-version`, `.java-version`, `.python-version`,
`.ruby-version`) when they name it, otherwise as `<tool>@<version>`, which it runs with
`mise exec`. A `go.mod` names a Go only by its `toolchain` line: its `go` line is a minimum
and is not read. It adds no file to the repository unless you ask. What mise installs lives on the
home volume, so it stays for every agent of this LADO, after `docker compose up -d
--force-recreate` and after an update; a second LADO has its own home volume and its own
tools.

- A tool by hand, the default for every agent of this LADO where no version file names one:
  `docker compose exec lado mise use -g go@1.23`. An agent leaves this to the supervisor; a
  worker asks it.
- The agents always run on the image's Node 22, also where `.nvmrc` or a version file names
  another (Kilo, Codex and the kits' MCP servers run on it). A repository's other Node runs
  through mise: `mise exec node@20 -- npm test`.
- `python3` and `python` are the image's Python 3.13, the one LADO runs on, unless the
  repository's version file or `mise use -g` names another: then mise's answers. No agent
  can change the image's Python (pip refuses it); a repository's packages go into a virtual
  environment (`python3 -m venv`, `uv`).
- openspec is the image's, at the version the image pins, with its usage statistics and
  update check off (`OPENSPEC_TELEMETRY=0`, `OPENSPEC_NO_UPDATE_CHECK=1`). One installed
  through mise stays on the home volume and is shadowed by the image's; a newer openspec
  comes with a newer image.
- A repository's `mise.toml` under the workspace needs no `mise trust`.
- A tool the image lacks, such as `shellcheck`, comes through mise:
  `mise exec shellcheck@latest -- shellcheck script.sh`.
- An agent's `npm install -g` and `uv tool install` go to `~/.local` on the home volume and
  stay over an update too.
- The system libraries of Playwright's Chromium are in the image, so a repository's browser
  tests (LADO's own `make test-ui`) run headless; the browser itself is not:
  `make browser` (`playwright install chromium`) puts it on the home volume, at the
  repository's own Playwright version.
- What is not covered: other system packages (`apt`) and databases (PostgreSQL, Redis, ...).
  An agent says so instead of installing them.
- An old version takes room on the home volume until you remove it:
  `docker compose exec lado mise ls`, then `docker compose exec lado mise uninstall go@1.22.5`.

### Update the container

A new version of LADO in Docker is a new image: `lado update` and the web UI's **Update…**
do not update a container, and say so. LADO still tells you when one is out:
`docker compose exec lado lado ls` prints `LADO X.Y.Z is available: a new image updates
LADO in a container (ghcr.io/ladohq/lado:X.Y.Z)`, and the web UI shows `↑ X.Y.Z` next to
`live`. The versions are on the [releases page](https://github.com/ladohq/lado/releases).

In the folder of your `compose.yaml`: keep a copy of yours, download the new version's in
place of it (`<version>` is the new number as `.env` has it; the address puts a `v` before
it), set the new `LADO_VERSION` in `.env`, then start (compose pulls that version's image):

```bash
cp compose.yaml compose.yaml.bak
curl -fLO https://github.com/ladohq/lado/releases/download/v<version>/compose.yaml
docker compose up -d
```

Every update takes its version's `compose.yaml`, since a release may add a mount or a
setting to it: 0.40.0 added git's identity, the ssh agent and the secrets folder, which an
older file does not give the container. `.env`, `secrets/` and the home volume stay. A
change you made to `compose.yaml` by hand is replaced: `diff compose.yaml.bak
compose.yaml` shows it, carry it over to the new file (your settings belong in `.env`,
which stays). With several LADOs on this computer, update each in its own folder, with its
own `.env`; nothing here touches another one's container or volume. An `.env` with
`LADO_PROJECTS`, the workspace's name before 0.43.0, keeps working; renaming it to
`LADO_WORKSPACE` is optional, and `LADO_WORKSPACE` wins when both are set.

What happens:

- Compose pulls `ghcr.io/ladohq/lado:<new version>`, stops the old container and starts a
  new one on the same home volume.
- The running sessions stop with the old container, as `lado stop` would, and resume in
  the new one. Each agent starts a new conversation, a busy one loses its current turn,
  and each resumed supervisor takes one model turn: update while your agents are idle.
  For a few seconds after the start `lado ls` may still show a session as `tmux session
  is gone`: the sessions resume one by one, and `docker compose logs lado` says
  `resumed session "<name>"` for each.
- The new LADO upgrades its database at its start, after a backup
  (`~/.lado/backups/lado.db.schema-<N>` on the home volume; `docker compose logs lado`
  names it).
- Logins made inside, kits, sessions and their history, git's identity and the files of
  `secrets/` stay; your workspace is not touched.
- The old image keeps its tag, so going back is the version before in `.env` (below).

`docker compose exec lado lado --version` shows the version that runs. The commands of
another `.env` (a second LADO) run in its own folder and leave this one as it is.

### Go back to the version before

Put the version you had before back in `.env`; the way back keeps the `compose.yaml` you
have (an older LADO ignores the mounts and settings it does not know). Then, with `<N>`
from the backup's name (what LADO did since the upgrade is lost):

```bash
docker compose down
docker compose run --rm lado sh -c 'cd ~/.lado && rm -f lado.db-wal lado.db-shm && cp backups/lado.db.schema-<N> lado.db'
docker compose up -d
```

When an upgrade's migration failed, the database is as it was: the first and the last
command do it.

### A second LADO

Another folder with a copy of `compose.yaml`, a `secrets/` of its own or none, and an
`.env` that adds its own `COMPOSE_PROJECT_NAME` and port:

```ini
COMPOSE_PROJECT_NAME=lado-2
LADO_PORT=8766
LADO_VERSION=<version>
LADO_WORKSPACE=/Users/ann/work
```

It has its own container, home volume, logins and version: updating or removing one leaves
the other as it is. Run each one's commands in its own folder.

### The sessions and the container

`docker compose down` (or `stop`, or Docker's own end) stops the container's sessions, as
`lado stop` would; `docker compose up -d` (or `start`) resumes them, also after an update or
a crash. Sessions you stopped yourself stay stopped. Each resumed session's supervisor takes
one model turn at its start.

### Remove it

From its folder: the container, then its home volume by name. The volume is
`<project>_home`: `lado_home`, or `lado-2_home` for `COMPOSE_PROJECT_NAME=lado-2`. Look
before you remove:

```bash
docker compose down
docker volume ls --filter name='^lado_home$'   # exactly this name
docker volume rm lado_home
```

The volume holds LADO's sessions and the logins made inside; your workspace stays. The image
too, if no other container uses it: `docker image rm ghcr.io/ladohq/lado:<version>`.
Nothing here touches another LADO's container or volume.

### With docker run

The same image with one command; an update is that command again with the new version
(the [Dockerfile's header](../docker/Dockerfile) has the rest):

```bash
docker run -d --name lado -p 127.0.0.1:8765:8765 -v lado-home:/home/lado \
  -v "$HOME/workspace:$HOME/workspace" -e LADO_REPOS="$HOME/workspace" \
  -e LADO_GIT_NAME="Ann Lee" -e LADO_GIT_EMAIL=ann@example.com \
  ghcr.io/ladohq/lado:<version>
docker exec lado lado ui --no-open   # the UI's link with its token
```

The agents' variables: `mkdir -m 700 secrets` and `-v "$PWD/secrets:/run/secrets:ro"` added
to the `docker run`.

### If something goes wrong in Docker

The image brings tmux, git and the agent CLIs at their tested versions, so there is no
`lado doctor` step to install anything. When something is off, it is the first look:
`docker compose exec lado lado doctor` says whether the workspace is there and
writable, which files of `secrets/` the agents get (names only) and which are not used, and
which agent CLIs run. `docker compose logs lado` has the container's own warnings (git's
identity, the ssh agent, the workspace).

- **Another version, port or folder than `.env` says**: a variable of your shell beats
  `.env`. `env | grep -E '^(LADO|COMPOSE)_'`, `unset` each, and `docker compose up -d`
  again; `docker compose config` shows what compose takes.
- **`set LADO_VERSION to the LADO version to run` though `LADO_IMAGE` is set**: an older
  Compose v2 asks for it all the same. Set `LADO_VERSION` too, or update Docker.
- **A git name or email removed from `.env` stays**: it is in git's config on the home
  volume. `docker compose exec lado git config --global --unset user.name` (or
  `user.email`).
- **An agent has a token it should not**: every agent of one LADO reads every file of its
  `secrets/`. Values for some agents only need another LADO with its own folder.
- **A file in `secrets/` does not reach the agents**: `LADO_SECRETS=./secrets` is missing
  from `.env` (`lado doctor` says `/run/secrets: none`). Add it, then `docker compose up -d`.
- **No git identity, no ssh agent or no secrets after an update from 0.39.0**: the
  `compose.yaml` is still 0.39.0's. Take the new version's, as
  [Update the container](#update-the-container) says.
- **Two LADOs on a Mac and ssh works only in one**: Docker Desktop's ssh agent socket is
  one for all containers, and each LADO's start gives it to its own user. With
  workspaces of two owners the LADO started last has it; `docker compose restart` takes it
  back for the other. Workspaces of the same owner share it.
- **`docker run --user root --cap-drop ALL` does not start**: drop one of them. Without
  `--user root` the server runs as the container's user anyway.
- **`could not give lado the uid and gid of LADO_REPOS's owner` or `could not give lado
  everything under /home/lado` in `docker compose logs lado`**: a container tries this
  only at its first start, so a restart does not try again. Fix the cause, then
  `docker compose down` and `docker compose up -d`: a new container tries again.
- **A session's folder that your computer does not see**: it is outside the
  workspace, on the container's home volume (the New session window and `lado start` warn).
  Put the repository under `LADO_WORKSPACE`. `~` in the container is `/home/lado`, not your
  home: type the full path.
- **Another git host over ssh asks about its key**: the image knows only GitHub's. Add the
  host's key on the home volume, which trusts the first answer: compare its fingerprint
  with the one the host publishes.
  `docker compose exec lado sh -c 'mkdir -p -m 700 ~/.ssh && ssh-keyscan gitlab.com >> ~/.ssh/known_hosts && ssh-keygen -lf ~/.ssh/known_hosts'`.
- **An agent closed right after the session started**: Enter on Claude Code's trust
  question answered "No, exit". Stop the session and resume it in the UI (or
  `docker compose exec lado lado stop <session>`, then
  `docker compose exec lado lado start <repository> --name <session>` with the
  repository's path in the container) and choose "Yes, I trust this folder"; see
  [Your first session](#your-first-session).
- **The UI's link is lost**: `docker compose exec lado lado ui --no-open`.
- **`No version is set for shim: go`**: neither the repository's version files nor a
  default name that tool. Add the version to the repository (`.tool-versions`: `go 1.23.4`)
  or set a default: `docker compose exec lado mise use -g go@1.23`.
- **mise refuses a Python version** (an attestation or checksum it cannot check): take
  another version, or the repository's Python through uv (`uv run`). Do not switch mise's
  checks off.
- **`Config files in ... are not trusted`**: the repository is outside the workspace.
  Move it under `LADO_WORKSPACE`, or trust it once:
  `docker compose exec lado mise trust <folder>/mise.toml`.
- **`bind source path does not exist: <path>`** at `docker compose up -d` (Docker Desktop
  may word it otherwise, naming the same path): with
  `/set-LADO_WORKSPACE-to-your-workspace-folder`, `.env` names no workspace: set
  `LADO_WORKSPACE` in it to your workspace folder, a full path. With your own folder, it
  does not exist yet: `mkdir -p <path>`, then `docker compose up -d` again.

## macOS

### Prerequisites

[Homebrew](https://brew.sh). git comes with the Xcode command line tools
(`xcode-select --install`) or from Homebrew (`brew install git`).

### Steps

1. Install tmux and uv, then LADO:

   ```bash
   brew install tmux uv
   uv tool install lado
   ```

2. Install an agent CLI and log in to it once: [Agent CLIs](#agent-clis). Codex, Kilo and
   OpenCode install with npm, which comes with Node.js: `brew install node`.
3. Check:

   ```bash
   lado doctor
   ```

   It ends with `All checks passed.` when LADO can start a session.
4. Start a session: [Your first session](#your-first-session).

### If something goes wrong

- `lado: command not found` after `uv tool install lado`: uv's tool folder is not on your
  `PATH`. Run `uv tool update-shell` and open a new terminal.
- See also [Common problems](#common-problems).

## Linux

These steps are for Debian and Ubuntu (apt). They are also the steps inside Ubuntu on
Windows: the [Windows](#windows) section refers to them.

### Prerequisites

A user that can run `sudo`.

### Steps

1. Install git, tmux and curl:

   ```bash
   sudo apt update && sudo apt install -y git tmux curl
   ```

2. Install Node.js 22 from NodeSource, for the agent CLIs from npm (Codex, Kilo,
   OpenCode):

   ```bash
   curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
   sudo apt install -y nodejs
   ```

3. Install uv, then LADO:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   source ~/.local/bin/env
   uv tool install lado
   ```

   `source ~/.local/bin/env` puts uv on the `PATH` of this terminal; new terminals get it
   from your shell's startup file, which uv's installer changed.
4. Install an agent CLI, e.g. Kilo, and log in to it once ([Agent CLIs](#agent-clis)):

   ```bash
   npm install -g --prefix ~/.local @kilocode/cli
   ```

5. Check:

   ```bash
   lado doctor
   ```

   It ends with `All checks passed.` when LADO can start a session.
6. Start a session: [Your first session](#your-first-session).

### If something goes wrong

- `sudo apt install -y nodejs` fails with `trying to overwrite
  '/usr/include/node/common.gypi'`: an older Ubuntu (22.04) has Ubuntu's own Node 12
  installed. Remove it, then install again:

  ```bash
  sudo apt remove -y libnode-dev libnode72
  sudo apt install -y nodejs
  ```

- `npm install -g` without `--prefix` fails with a permission error (`EACCES`): the system
  Node installs global packages into a folder only root can write. Use
  `--prefix ~/.local`, as above, instead of `sudo`.
- See also [Common problems](#common-problems).

## Windows

LADO runs inside WSL2, in Ubuntu. An agent CLI installed on Windows itself does not count:
install it inside Ubuntu, as below.

### Prerequisites

Windows 10 or 11 with WSL2 available, and an account that can run cmd as administrator.

### Steps

1. Install Ubuntu. Open **cmd as administrator** (Start → type `cmd` → right click → Run
   as administrator) and run:

   ```
   wsl --install -d Ubuntu-24.04
   ```

   Restart if Windows asks. Ubuntu's window then asks for a user name (Latin letters) and
   a password; the password is for `sudo`. Later, open Ubuntu with `wsl` in cmd or
   "Ubuntu" in the Start menu.
2. In Ubuntu, do the [Linux steps](#steps-1) 1 to 4: git, tmux and curl from apt,
   Node.js 22 (for CLIs from npm), uv and LADO, and an agent CLI with
   `npm install -g --prefix ~/.local` (Kilo there, or another one).
3. Run `lado doctor` (it ends with `All checks passed.`), then `kilo` once to log in and
   pick a model (or your CLI's login, [Agent CLIs](#agent-clis)), then start a session in
   a git repository inside Ubuntu: [Your first session](#your-first-session). Later
   updates: `lado update` ([Update](#update)).

### If something goes wrong

- `sudo apt install -y nodejs` fails with `trying to overwrite
  '/usr/include/node/common.gypi'`: see [Linux](#if-something-goes-wrong-1).
- `lado doctor` does not see an agent CLI you installed on Windows (npm in cmd or
  PowerShell, `AppData\Roaming\npm`): by design. A Windows CLI does not work inside Ubuntu,
  and LADO does not pass the Windows `PATH` to agents (`lado doctor` says so: `Windows
  PATH: not passed to agents`). Install the CLI inside Ubuntu.
- `lado doctor` warns about tmux older than 3.3: see
  [Common problems](#lado-doctor-warns-about-tmux-older-than-33).
- See also [Common problems](#common-problems).

## Agent CLIs

Install one (or more) and log in to it once by starting it in a terminal. These are the
commands `lado doctor` prints for a missing CLI:

| CLI         | Install                                                          | Command    |
|-------------|------------------------------------------------------------------|------------|
| Claude Code | see [its docs](https://docs.anthropic.com/en/docs/claude-code)   | `claude`   |
| Codex       | `npm install -g @openai/codex`                                   | `codex`    |
| Kilo        | `npm install -g @kilocode/cli`                                   | `kilo`     |
| OpenCode    | `npm install -g opencode-ai`                                     | `opencode` |

On Linux and in WSL, with Node.js from apt, add `--prefix ~/.local` to `npm install -g`
(e.g. `npm install -g --prefix ~/.local @openai/codex`): a global install into the system
Node's folder needs `sudo`, and `~/.local/bin` is already on your `PATH` (uv's installer
uses it too). On macOS with Node from Homebrew, `npm install -g` works as is.

`lado doctor` warns when a CLI's version is not the one LADO is tested with: agent status
and message delivery may break with another version.

## Your first session

LADO works on a git repository with at least one commit:

```bash
cd ~/my-repo
lado start .            # a supervisor in tmux; --provider NAME picks the agent CLI
lado ui                 # the web UI in your browser
```

No repository yet? `lado start --new ~/workspace/my-site` makes a new or empty folder a git
repository with an empty first commit and starts there; the UI's **Launch** offers the same
as **From scratch**. Either needs git to know your name and email (`lado doctor` checks it).
`lado start --help` lists the options; `lado update` installs a newer LADO later
([Update](#update)).

## Update

How you update depends on how you installed LADO:

- **Docker**: a new `LADO_VERSION` in `.env`, then `docker compose up -d`, in the folder
  of your `compose.yaml`: [Update the container](#update-the-container), and back to the
  version before: [Go back to the version before](#go-back-to-the-version-before).
  `lado update` does not update a container.
- **PyPI**: `lado update`, in the terminal or the web UI, as follows.

From PyPI, `lado update` installs the latest LADO, `lado update X.Y.Z` another version.
The web UI does the same: click `live` in the top bar, then **Update…** and **Restart and
update**.

### What it does

1. It shows its plan (the version you have and the one it installs, the installer's
   command, the sessions and the UI server it restarts) and asks `Update? [y/N]`. The web
   UI shows the same plan in its window.
2. It stops your running sessions and the UI server.
3. It installs exactly that version with the installer LADO came with:
   `uv tool install lado==X.Y.Z`, or `pipx install --force lado==X.Y.Z`.
4. It checks that the installed `lado --version` is that version.
5. It starts the sessions and the UI server again, on the new version.

`lado update` keeps no copy of `lado.db` of its own and changes nothing in
`~/.lado/backups/`. The copy it relies on is the one a schema upgrade makes:
`~/.lado/backups/lado.db.schema-<N>`, `<N>` the schema before, written when the new
version first upgrades `lado.db` (its first `lado start`, `lado ui` or other command with
no session running).

`--yes` skips the question. Without a terminal (in a script) it is required: there
`lado update` refuses to go on without it. What happens to your sessions' work:
[README](../README.md#update).

### When something goes wrong

- The new version reports another version than the one asked for, or the UI server does
  not come up on it: LADO rolls back. It stops what the new version started, installs
  the old version again and starts your sessions on it. When the new version upgraded
  `lado.db`'s schema, it restores `lado.db` from `~/.lado/backups/lado.db.schema-<N>`. That
  copy missing (removed by hand), it rolls nothing back: the new version stays installed,
  as it can open `lado.db` and the old one could not, and the result names the schema and
  the missing copy.
- The installer fails: nothing changed; the sessions start again on the old version.
- Everything the update said and every command it ran, with their output, is in
  `~/.lado/update.log`.
- An update that stops half way leaves sessions stopped: `lado ls` names them, with the
  `lado start` that resumes each.

### Going back to an older version

`lado update 0.42.0` installs an older version the same way. First it learns which
`lado.db` schema that version knows, from its wheel on PyPI. When it is the schema of your
`lado.db`, nothing changes about the database. When it is older (0.42.x knows schema 31,
0.43.0 moved `lado.db` to 35), the older LADO would refuse `lado.db`, so:

- The plan warns before it asks: `lado.db` goes back to the copy
  `~/.lado/backups/lado.db.schema-31`, made when 0.43.0 upgraded it; everything LADO
  recorded since then is lost (sessions, runs, gates, messages, projects); repositories,
  worktrees and project folders stay on disk. It names the running sessions the copy does
  not have: they are not started again. `Update? [y/N]`, or `--yes`, is your yes to that.
- After the installer and the version check it puts the copy back into `lado.db`, keeps
  the copy, says `Restored lado.db from … (schema 31)` and starts the sessions the copy
  has on 0.42.x.
- Without that copy (no upgrade wrote it, two upgrades since, removed by hand), or when it
  cannot read the version's schema from PyPI, it refuses before it stops anything and
  says why. Going back then means starting from an empty database, by hand: move
  `~/.lado/lado.db` away and update.

`lado update` of 0.42.x and older kept its own copies, `lado.db.<version>`, in
`~/.lado/backups/`; nothing uses or removes them now: remove them by hand.

Installed otherwise (pip, below), do by hand what `lado update` does:

```bash
lado stop --all
lado server stop
pip install lado==0.42.0
cd ~/.lado && rm -f lado.db-wal lado.db-shm && cp backups/lado.db.schema-31 lado.db
```

Then start your sessions and `lado ui` again on 0.42.x.

In Docker it is [Go back to the version before](#go-back-to-the-version-before) with
`<N>` = 31.

What stays: the projects, their variables and which session is in which project are
forgotten with the database, but `<workspace>/projects/` stays with every repository in
it, and so does each project's data folder `~/.lado/projects/<id>/` with its secrets in
`secrets/`: remove it by hand when you no longer need them. Upgrading again, `lado doctor`
calls `projects/` "your own folder" and `lado project create` refuses until you move it
away; after that, `lado project create` with an id whose `~/.lado/projects/<id>/` is left
refuses (`… is left from a project <id>: remove it or choose another id`), so an old secret
is never taken over silently.

### The check for a newer version

`lado ls`, `lado doctor` and the web UI look on PyPI at most once a day and say
`LADO X.Y.Z is available: lado update` (the web UI: `↑ X.Y.Z` next to `live`).
`LADO_NO_UPDATE_CHECK=1` in your environment switches the check off.

### Installed otherwise

LADO updates itself only when it was installed from PyPI with `uv tool install lado` or
`pipx install lado`. Installed with pip (e.g. in a virtual environment), from a working
copy or from a git address (also through uv tool or pipx), `lado update` and the web UI
show the commands to run by hand instead: stop the sessions and the UI server, install
the version with that environment's `pip install lado==X.Y.Z`, then start them again.

## Uninstall

```bash
lado uninstall --dry-run    # what it would do; changes nothing
lado uninstall              # shows the same plan and asks Uninstall? [y/N]
```

`--yes` skips the question; without a terminal (in a script) it is required.

### What it does

1. It stops the UI server and every session of this `LADO_HOME` (as `lado stop --all`),
   waits for their session loops and closes the web UI's terminals. LADO's tmux server
   ends with its last session; when sessions of another `LADO_HOME` run on the same tmux
   socket, it stays and the output names them.
2. In each repository a session ran in, it removes the worktrees under
   `.lado/worktrees/<session>/` and the branches `lado/<session>/*` that `lado finish`
   would remove without asking: merged into the repository's current branch, nothing
   uncommitted. It keeps every other one and prints the commands that remove it:

   ```bash
   git -C <repo> worktree remove --force <worktree>
   git -C <repo> branch -D <branch>
   ```

   Once no worktree is left, `.lado/worktrees` and its line `/.lado/worktrees/` in
   `.git/info/exclude` go too. Your repository's own files in `.lado/` (e.g. `sdlc.md`) stay.
   A repository that is gone is named and passed over.
3. It deletes `~/.lado`: the history, artifacts, installed kits and their git cache,
   backups and logs.
4. Last, it removes the program with the tool that installed it: `uv tool uninstall lado`
   or `pipx uninstall lado`. Installed with pip or run from a working copy, the program
   stays and the output says where it runs from.

`--keep-data` stops everything and removes the program, but keeps `~/.lado` and the
repositories as they are: install LADO again and `lado start <repo> --name <session>`
resumes a session with its runs and history.

With another `LADO_HOME` (`LADO_HOME=/tmp/try lado uninstall`), it stops that folder's
sessions, cleans their repositories and deletes that folder; `~/.lado` and the program
stay, since `~/.lado` may still use it, and the output prints the command that removes
the program. It never deletes `/`, your home folder or a folder above it, nor a folder
without `lado.db` that is not `~/.lado`.

It refuses, changing nothing: inside an agent, while `lado update` runs, and when
`lado.db` was made by a newer LADO (uninstall with that LADO, or by hand below). An older
`lado.db` is upgraded as `lado stop --all` upgrades it.

### What stays

- Worktrees and branches with work that is not merged, listed with their commands.
- Repositories `lado start <git-url>` cloned into the workspace (`~/workspace/` by default,
  `~/lado/` before 0.43.0), and projects' folders: they are yours.
- tmux, uv, git and the agent CLIs.
- The agent CLIs' own records of the folders they ran in. LADO never writes to them, and
  removes nothing there:
  - Claude Code: the folder's entry in `~/.claude.json` (`projects`, with the trust you
    gave it; so a LADO installed again is not asked again) and its conversations in
    `~/.claude/projects/`.
  - Codex: nothing of LADO's agents; their Codex home was LADO's own, under `~/.lado`.
  - OpenCode and Kilo: their sessions in their data folders, `~/.local/share/opencode/`
    and `~/.local/share/kilo/`.

### By hand

For a LADO before 0.37 (no `lado uninstall`) or one installed with pip:

```bash
lado stop --all
lado server stop
sqlite3 ~/.lado/lado.db 'SELECT DISTINCT repo FROM sessions'   # the repositories
```

In each repository: `git worktree list` and `git branch --list 'lado/*'`; remove each
worktree under `.lado/worktrees/` and its branch whose work you do not need
(`git worktree remove <path>`, `git branch -D <branch>`), then the line
`/.lado/worktrees/` from `.git/info/exclude`. Then:

```bash
rm -rf ~/.lado
uv tool uninstall lado      # or: pipx uninstall lado, or pip uninstall lado
```

### Testing an upgrade as a new user meets it

```bash
lado uninstall --yes            # the machine as a new user's, but the agent CLIs' records
uv tool install lado==0.36.0    # the release users have
lado start ~/work/app           # use it as a user would
lado update                     # the upgrade under test
```

## Common problems

### `lado doctor` warns about tmux older than 3.3

Ubuntu 22.04 has tmux 3.2a. LADO works; gate popups have no coloured border. Ubuntu 24.04
has a newer tmux. Before 3.2 there are no gate popups (gates show only in `lado ls`) and no
agent terminals in the web UI.

### `git is not installed or not on PATH`

LADO runs git itself (`lado start`, the UI's New session window, `lado kits add`), on the
`PATH` of the terminal or of the server you started it from. On macOS install the Xcode
command line tools, `xcode-select --install` (or `brew install git`); on Linux and WSL
`sudo apt install git` (or your distribution's package manager). Then run `lado doctor`
again: its `git` line names the version it found.

### `git does not run: xcrun: error: invalid active developer path`

On a Mac without the Xcode command line tools, `/usr/bin/git` is only a stub that asks for
them. Run `xcode-select --install`, then `lado doctor` again. Before LADO 0.36 this showed
as "not inside a git repository".

### `lado doctor` warns about git older than 2.31

LADO works, but its look at whether an agent CLI trusts the folder (`git rev-parse
--path-format=absolute`) needs git 2.31: with an older git LADO may not foresee a CLI's
"trust this folder?" question, or expect one that does not come. Install a newer git.

### `Agent CLI: no agent CLI installed`

No agent CLI is on the `PATH` of the terminal you ran `lado doctor` in, which is where it
looks. Install one ([Agent CLIs](#agent-clis)), open a new terminal and run `lado doctor`
again. LADO starts agents with the `PATH` of your login shell, so a CLI that works in one
terminal but not for LADO is usually added to `PATH` only in a file your login shell does
not read; `lado doctor`'s `Agent environment` line says where LADO's `PATH` comes from.

### Without uv

`pip install lado` (Python 3.10 or newer) installs LADO too, e.g. into a virtual
environment. `lado update` then only prints the commands to run by hand
([Installed otherwise](#installed-otherwise)).
