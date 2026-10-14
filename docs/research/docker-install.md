# Research: installing LADO through Docker (LAD-52)

The question: can LADO ship as a Docker image, so that a user who is not a programmer
installs Docker and runs one command instead of tmux, git, uv, Node.js and an agent CLI
(on Windows a whole Ubuntu in WSL2 first), and what that costs. Checked by hand on a
prototype image on a Mac (Apple silicon, Docker Desktop, engine 29.7.2, linux/arm64),
2026-10-14, with LADO 0.37.0. Openspec change: `openspec/changes/docker-install-research/`.

1. [Summary](#1-summary)
2. [Today and with Docker](#2-today-and-with-docker)
3. [The prototype](#3-the-prototype)
4. [Hands-on checks](#4-hands-on-checks)
5. [Difficulties](#5-difficulties)
6. [Platforms](#6-platforms)
7. [Alternatives](#7-alternatives)
8. [Proposed tasks](#8-proposed-tasks)

## 1. Summary

**Verdict: worth building, as a second way in, not as the default one.** LADO and all four
agent CLIs run in one container, are reached from the host's browser through the web UI,
start sessions and workers on a bind-mounted project, survive a restart and resume (H1,
H2, H5-H7). For a user who already has Docker Desktop, or on Windows, where today's way is a
whole Ubuntu in WSL2, the image is one command instead of seven steps. For the macOS or
Linux user with Homebrew or apt, a one-command install script removes most of the same
pain at a fraction of the cost (section 7).

The three largest difficulties:

1. **The agents' toolchains.** Agents run the project's builds and tests inside the
   container, which has only what the image put there; a Python, Go or Java project needs
   its toolchain in the image or a derived one. A non-programmer cannot do that.
2. **Paths seen twice.** LADO stores the container's paths (`/projects/demo`), and the
   worktrees git links with absolute paths; on the host, `git worktree list` shows a
   worker's worktree as `prunable`, and `git worktree prune` there would drop it (H6).
3. **Updates and logins.** `lado update` inside kills itself (it stops the UI server, the
   container's main process, H7), so the image is updated from outside; and every CLI's
   login must be made inside and kept on a volume, Codex's not carried to its agents at all
   (BACKLOG.md).

## 2. Today and with Docker

Today (docs/install.md), a user installs and types:

| System | Steps |
|---|---|
| macOS | Homebrew, then `brew install tmux uv`, `uv tool install lado`, an agent CLI (Node.js for three of them), its login, `lado doctor`, `lado start`, `lado ui` |
| Linux (Debian, Ubuntu) | `apt install git tmux curl`, Node.js 22 from NodeSource, uv's install script and `source ~/.local/bin/env`, `uv tool install lado`, `npm install -g --prefix ~/.local <cli>`, its login, `lado doctor`, `lado start`, `lado ui` |
| Windows | `wsl --install -d Ubuntu-24.04` as administrator, a restart, a Linux user, then all the Linux steps inside Ubuntu, with the projects inside Ubuntu |

Each step has its own failure (a `PATH` without uv's folder, npm's `EACCES`, Ubuntu 22.04's
old Node: docs/install.md, "If something goes wrong").

With the image, the user installs Docker Desktop (macOS, Windows) or Docker Engine
(Linux) and runs once:

```bash
LADO_PROJECTS=~/lado-projects docker compose -f compose.yaml up -d
docker exec -it lado claude          # log in to a CLI once (section 5.1)
docker exec lado lado ui --no-open   # the UI's link, opened in the host's browser
```

A product would hide these behind one script or a desktop shortcut (section 8). The user
still has to know where the projects folder is and that agents see only it.

## 3. The prototype

Files: [Dockerfile](docker-install/Dockerfile) and
[compose.yaml](docker-install/compose.yaml), as they were when the checks ran (one
change during the checks: `group_add` for H8, which the checks after it ran with).
Evidence, not a product: no build or CI picks them up.

- **Base**: `debian:bookworm-slim`, which gives tmux 3.3a and git 2.39.5 (`lado doctor`
  wants 3.3 and 2.31, docs/install.md). Python 3.11 comes from Debian as a dependency
  of NodeSource's `nodejs` package, and uv uses it for LADO.
- **User**: `lado`, uid 1000, login shell `/bin/bash`. Agents get their environment from
  that login shell (`agent_env.resolve`), and Debian's `/etc/profile` sets `PATH` anew, so
  LADO's folders are added in `/etc/profile.d/lado.sh`.
- **Init**: `tini` as PID 1 (`ENTRYPOINT`), which reaps the processes tmux and the agents
  leave; the main process is `lado server --host 0.0.0.0 --port 8765`.
- **Programs** under `/opt`, outside the home volume, so a new image replaces them: uv,
  LADO 0.37.0 (`uv tool install`), Node.js 22 from NodeSource, and the four CLIs at the
  versions CI pins (`scripts/smoke_ci.py`, `PINS`; the providers' `TESTED_VERSION`): Claude
  Code 2.1.295, Codex 0.162.0, OpenCode 1.18.35, Kilo 7.8.8. Claude Code's self-update is
  off (`DISABLE_AUTOUPDATER=1`); LADO switches off OpenCode's and Kilo's for its agents
  (AGENTS.md, How agents talk) and Codex's update check (providers/codex.py).
- **gh** and **openssh-client** for pushing from inside (H8).
- **Size**: 2.46 GB as `docker image ls` shows it; the four CLIs take 1.8 GB of it
  (`@kilocode` 559 MB, `@anthropic-ai` 488 MB, `@openai` 390 MB, `opencode-ai` 354 MB),
  LADO with uv 77 MB. A first version that ran `chown -R` over `/opt` after the installs
  was 5.09 GB: the layer was copied, so the installs run as `lado`.
- **Build**: 113 s from scratch on this Mac (`docker compose build --no-cache`).
- **Volumes**: `home` on `/home/lado`: LADO_HOME (`~/.lado`) and every CLI's login and
  config (`~/.claude` with `CLAUDE_CONFIG_DIR`, `~/.codex`, `~/.config/opencode`,
  `~/.config/kilo`, `~/.local/share/...`). The projects: one bind mount, the host's
  `$LADO_PROJECTS` on `/projects`.
- **Port**: `127.0.0.1:8765:8765`, the host's loopback only.
- **Reaching it**: `docker exec lado lado ui --no-open` prints the link with the token;
  the host's browser opens it; the agents' terminals are the UI's terminal panel
  (terminal.py), so the user needs no `docker exec -it` for the agents.

## 4. Hands-on checks

| Check | What was done | Result | Evidence |
|---|---|---|---|
| H1 | The image built for linux/arm64; `lado doctor` inside | works | [H1](#h1-image-and-lado-doctor) |
| H2 | The UI from the host's browser; a session from the New session window; an agent's terminal; the token and Origin guard through the port map | works | [H2](#h2-the-ui-from-the-host) |
| H3 | Claude Code: subscription login inside, a LADO session's turn on it, the login after recreating | PENDING | [H3](#h3-claude-code-login) |
| H4 | Codex: ChatGPT login inside; a LADO Codex agent on it | PENDING | [H4](#h4-codex-login) |
| H5 | OpenCode and Kilo supervisors run a turn on LM Studio's model on the host | works | [H5](#h5-local-model-on-the-host) |
| H6 | A worker commits on the bind-mounted repository; the host's view of it | works with a workaround | [H6](#h6-a-worker-on-the-bind-mount) |
| H7 | Container stopped and started; recreated from the image; `lado update` inside | works (restart, recreate); `lado update` does not work | [H7](#h7-restart-recreate-update) |
| H8 | The host's ssh agent, `git push`, `gh` from inside | works with a workaround | [H8](#h8-ssh-agent-push-gh) |

### H1: image and lado doctor

```
$ docker compose build --no-cache          # real 113.04 s
$ docker image ls lado-research:prototype  # 2.46GB
$ docker exec lado lado doctor
[ok  ] LADO: 0.37.0, the latest version
[ok  ] Python: 3.11.2
[ok  ] tmux: tmux 3.3a
[ok  ] git: git version 2.39.5
[ok  ] Agent environment: from your login shell /bin/bash, resolved in 0.0 s; starting PATH from the default (no PATH in /etc/environment)
[ok  ] Agent config folders: only those of running agents
[ok  ] Artifacts: none
[ok  ] Claude Code: 2.1.295 (Claude Code)
[ok  ] Codex CLI: codex-cli 0.162.0
[ok  ] Kilo CLI: 7.8.8
[ok  ] OpenCode: 1.18.35

All checks passed.
```

### H2: the UI from the host

The server's own lines (`docker logs lado`) and the link:

```
lado: warning: the LADO server listens on 0.0.0.0:8765, open to other machines: whoever reaches it with the token can run commands as you, and the token travels unencrypted (plain HTTP). Use it only on a network you trust.
LADO server 0.37.0 at http://127.0.0.1:8765, listening on 0.0.0.0:8765, pid 7
$ docker exec lado lado ui --no-open
http://127.0.0.1:8765/?token=<redacted>
From another machine: http://lado:8765/?token=<redacted> (or this host's address)
```

The first link works in the host's browser because the published port is the same
number; the warning and the "From another machine" line are wrong for a container
published on the host's loopback (section 5.6).

A Chromium on the host (Playwright) opened the link, chose **Launch**, typed into
**Where**, picked the provider OpenCode, wrote a first message and started the session.
The folder picker lists the container's root (`bin/`, `boot/`, `dev/`, `etc/`, ...), not
the host's ([screenshot](docker-install/h2-picker-root.png)); `/projects/demo` showed
`✓ git repository · branch main`. The supervisor's terminal opened in the panel and showed
its turn ([screenshot](docker-install/h2-terminal.png)).

The guard through the port map (`curl` from the host to
`POST /api/sessions/demo/messages`): a foreign `Origin` with the token was 403, no token
403, the Bearer token 200 `{"result":"sent"}`. The Origin is checked against the request's
own Host (server/auth.py, `Guard.check`), which the port map does not change, and the
cookie's name holds the server's port (auth.py, `cookie_name`), so another host port
(`127.0.0.1:18765:8765`) changes nothing for the browser (from the code, not run).

### H3: Claude Code login

PENDING (the human's login).

### H4: Codex login

PENDING (the human's login).

### H5: local model on the host

The container reaches LM Studio on the host as `http://host.docker.internal:1234/v1`
(Docker Desktop provides the name; the compose file adds it for a Linux engine). OpenCode's
and Kilo's global config (`~/.config/opencode/opencode.json`, `~/.config/kilo/kilo.json`)
named the `lmstudio` provider at that address with `qwen/qwen3.5-35b-a3b`, as the live
tests' config does (tests/local_models.py, `opencode_config`).

```
$ docker exec lado lado log demo-kilo      # Kilo, started with lado start ... --provider kilo
07:34:07 supervisor: spawned (role supervisor, provider kilo)
07:34:11 supervisor: mcp_ready (...)
07:34:31 supervisor: idle
# its window: "Hello! I'm running on lmstudio/qwen/qwen3.5-35b-a3b."
```

OpenCode's supervisor of session `demo` (H2) answered likewise in 12.3 s.

### H6: a worker on the bind mount

The OpenCode supervisor of `demo` spawned a worker on the human's message; the worker
committed `hello.txt` on `lado/demo/worker` in `/projects/demo/.lado/worktrees/demo/worker`
(the local model first tried to write `/hello.txt`, refused at OpenCode's permission
dialog; a second message put it right: the model's mistake, not the container's). On the
host:

```
$ git status --short --branch
## main
$ git worktree list
<host projects>/demo                         cc24eb5 [main]
/projects/demo/.lado/worktrees/demo/worker   718c0e9 [lado/demo/worker] prunable
$ cat .lado/worktrees/demo/worker/.git
gitdir: /projects/demo/.git/worktrees/worker
$ git -C .lado/worktrees/demo/worker status
fatal: not a git repository: /projects/demo/.git/worktrees/worker
$ git worktree prune -n -v
Removing worktrees/worker: gitdir file points to non-existent location
$ ls -ln .lado/worktrees/demo/worker
-rw-r--r--  1 501  0  24 ... hello.txt
$ git log --all --format='%h %an %s'
718c0e9 LADO research Add hello.txt
```

The main repository is fine on the host, and the worker's commit is in it (its branch).
The worktree is not usable from the host, and a `git worktree prune` there (or a `git gc`
once `gc.worktreePruneExpire`, three months by default, has passed:
<https://git-scm.com/docs/git-gc>) drops git's record of it, after which LADO's finish
must treat the worktree as gone (`runtime.gone`). Files the container writes are the host
user's on Docker Desktop for Mac (uid 501 here; the container sees its own uid 1000 for
everything under `/projects`).

Workaround: mount the projects at the same path inside as on the host (section 5.3).

An unexplained observation: twice in five runs of a benchmark that wrote 3000 files into
a new folder under `/projects`, git refused it right after (`detected dubious ownership in
repository at '/projects/bench'`); `stat` showed uid 1000 each time it was asked, and it
did not happen on demand. Docker Desktop's file sharing reports the owner of a bind
mount's files as the container user; it seems to flicker under load. A repository that
hits it needs `safe.directory` in the container's git config.

### H7: restart, recreate, update

`docker compose stop` took 0.48 s: tini passes SIGTERM, and LADO's sessions end without
`lado stop`. After `docker compose start`:

```
$ docker exec lado lado ls
demo  /projects/demo  (tmux session is gone)
  supervisor   supervisor opencode idle       19s
  worker       worker     opencode idle       21s     lado/demo/worker
demo-kilo  /projects/demo  (tmux session is gone)
  supervisor   supervisor kilo     idle       6m
$ docker exec lado lado start /projects/demo --name demo --no-attach
Resumed session "demo" in /projects/demo: 0 open runs, the supervisor is told.
```

The UI server came back by itself (it is the container's command; `restart:
unless-stopped`). After `docker compose down` and `up` (a new container from the image),
`lado ls` was the same and the session resumed again: LADO_HOME and the CLIs' configs are
on the `home` volume. `lado doctor` then warns about the agent config folders the killed
agents left (`Agent config folders: left by agents that do not run (they may hold
secrets)`), with the `rm -rf` to run: the hard stop skipped their removal
(providers/base.py, `remove_config_dir`). The resumed session's worker was forgotten, as
after any `lado stop` (AGENTS.md, `lado stop`); its branch stays.

`lado update` inside (to 0.36.0, a throwaway container):

```
$ docker exec lado lado update --yes 0.36.0      # exit 137
LADO 0.37.0 -> 0.36.0 (PyPI, released 2026-10-12)
Installed with uv tool: uv tool install lado==0.36.0 --refresh-package lado
Restarts:
  UI server  http://127.0.0.1:8765
Stopping the UI server... stopped
Backed up lado.db to /home/lado/.lado/backups/lado.db.0.37.0
Upgrading: uv tool install lado==0.36.0 --refresh-package lado
$ docker exec lado lado --version                 # the container restarted
lado 0.37.0
# ~/.lado/update-result.json: "outcome": "running", "ended_at": null; ~/.lado/update.json left
```

Stopping the UI server ended the container's main process, so Docker killed every
process in it, the update too, in the middle of its installer. Docker's restart policy
started it again on the old version. A later `lado update` said `LADO 0.37.0 is the latest
version` and went on; the result file still said `running`.

### H8: ssh agent, push, gh

Docker Desktop's ssh agent socket
(<https://docs.docker.com/desktop/features/networking/networking-how-tos/>) is
`root:root`, mode 660, inside the container:

```
$ docker exec lado ssh-add -l
Error connecting to agent: Permission denied
```

With the container user in group 0 (`group_add: ["0"]` in compose.yaml):

```
$ docker exec lado ssh -T git@github.com
Hi <redacted>! You've successfully authenticated, but GitHub does not provide shell access.
$ docker exec lado git ls-remote git@github.com:ladohq/lado.git HEAD   # read only
b56a32940a3b...
$ docker exec lado git -C /projects/demo push scratch main             # a scratch bare repository under /projects
 * [new branch]      main -> main
```

A push over ssh to a remote was not done: there is no scratch remote, and the design
forbids the project's own; the ssh login above is the part the container changes. The
agents' login shell has `SSH_AUTH_SOCK` (it is in the container's environment, which
`docker exec` and the server pass on). The first push, right after the bare repository was
made on the host, failed with `does not appear to be a git repository`; the same push a
moment later worked.

`gh` has no login inside (`You are not logged into any GitHub hosts`): the host's is in
the macOS keychain. With `GH_TOKEN` passed to one `docker exec` (`-e GH_TOKEN`), `gh api
user` worked and `gh auth status` said `Logged in ... (GH_TOKEN)`. A lasting login is `gh
auth login` inside, which keeps the token in `~/.config/gh/hosts.yml` on the volume, as a
plain file when no keyring is there (<https://cli.github.com/manual/gh_auth_login>; not
run).

## 5. Difficulties

Each: its cause, what the user sees, ways out with their cost.

### 5.1 The providers' logins

- **Cause**: each CLI keeps its login in its own place, and a container has no keychain
  and no browser. LADO itself carries the user's login to the agents only as far as each
  CLI reads it from the user's home: Claude Code's config dir, OpenCode's and Kilo's data
  folder; Codex's login is not carried (each agent has its own `CODEX_HOME`, BACKLOG.md,
  "Codex agents cannot log in").
- **User sees**: an agent's terminal with the CLI's login screen.
- **Ways out**:
  1. Log in once inside (`docker exec -it lado claude`, `codex login --device-auth`,
     `opencode auth login`, `kilo auth login`), kept on the home volume (H3, H4). Cost: a
     step in a terminal; the login is a plain file on the volume (Claude Code on Linux:
     `~/.claude/.credentials.json`, <https://docs.anthropic.com/en/docs/claude-code/iam>).
  2. A token in the environment: `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token` (its
     help: "Set up a long-lived authentication token (requires Claude subscription)"),
     `OPENAI_API_KEY` or `codex login --with-api-key` for Codex with an API key. Cost: the
     token in compose's environment or an env file.
  3. LADO carries Codex's `auth.json` into each agent's `CODEX_HOME` (the BACKLOG entry):
     needed for Codex with a ChatGPT login in any setup, not only Docker. Cost: S/M.

### 5.2 The project's own toolchains

- **Cause**: an agent builds and tests the project with the programs of the container: the
  image has git, Node.js 22 and Python 3.11, nothing else (no compilers, `make`, Java, Go,
  Rust, databases).
- **User sees**: the agent reports `command not found` for the project's build or test,
  or installs it with `npm`/`pip` into the container, where it is lost on recreation.
- **Ways out**:
  1. A "full" image with common toolchains (build-essential, Python's venv, Go, Java).
     Cost: several GB more, and still not every project.
  2. A documented derived image (`FROM lado` plus the project's `apt-get install`).
     Cost: needs a programmer, against the goal.
  3. The project's own dev container (section 7) with LADO added to it. Cost: the project
     must have one.

### 5.3 Paths of the container against the host

- **Cause**: LADO stores the repository path it was given (`sessions.repo`), and git links
  a worktree to its repository with absolute paths in `.git` files (git 2.39 has no other
  way; `--relative-paths` and `worktree.useRelativePaths` came with git 2.48,
  <https://git-scm.com/docs/git-worktree>).
- **User sees**: in the UI, paths like `/projects/demo`; the folder picker shows the
  container's root (H2); on the host, a worker's worktree is `prunable` and its folder is
  not a git repository (H6); an IDE on the host cannot open a worker's worktree as git.
- **Ways out**:
  1. Mount the projects at the same path as on the host (`-v $HOME/lado:$HOME/lado`, the
     `~/lado` of `clone.DEFAULT_PARENT`). Every stored path and git link is then right on
     both sides. Cost: the compose file needs the host's path; on Windows the host path
     is a WSL one (section 6).
  2. A base with git 2.48+ and `worktree.useRelativePaths=true` in the image's git config.
     Cost: a newer git than Debian 13 has (2.47.3, `apt-cache policy git` in
     `debian:trixie-slim`), so another base or git built for the image, and LADO's
     worktree code checked with relative links.
  3. The picker starts in `/projects` (a `LADO_` variable for the UI's default folder).
     Cost: a small code change; does not fix git.

### 5.4 File ownership on a Linux host

- **Cause**: Docker Engine on Linux mounts the host's folder as it is, numeric uids
  included, with no mapping (not checked here; Docker's user namespace page says the
  ownership of mounted folders "must be pre-arranged",
  <https://docs.docker.com/engine/security/userns-remap/>); Docker Desktop for Mac maps
  them to the user (H6).
- **User sees**: on a Linux host whose user is not uid 1000, files the agents wrote are
  owned by uid 1000, and git inside refuses the host's repositories as "dubious
  ownership".
- **Ways out**:
  1. Run the container as the host's uid (`user: "${UID}:${GID}"`); the image must then
     work for any uid (home, `/opt` readable). Cost: a little image work.
  2. Rootless Docker or user namespace remapping
     (<https://docs.docker.com/engine/security/userns-remap/>). Cost: setup a
     non-programmer will not do.

### 5.5 Git credentials and push

- **Cause**: the host's ssh agent and `gh` login stay on the host.
- **User sees**: `Permission denied (publickey)`, `gh` not logged in (H8).
- **Ways out**:
  1. Docker Desktop's ssh socket with the user in its group (H8). Cost: the root group,
     and on a Linux engine the socket must be mounted from `$SSH_AUTH_SOCK` instead.
  2. `gh auth login` inside, and `gh auth setup-git` for https remotes. Cost: one more
     login, kept as a plain file on the volume.

### 5.6 The UI server inside

- **Cause**: the server must listen on `0.0.0.0` to be reached through the port map, and
  `lado ui` cannot open a browser.
- **User sees**: the warning that the server is open to other machines, though the port
  is published on the host's loopback only; a "From another machine" link with the
  container's hostname (`http://lado:8765`, cli.py), which works nowhere; `lado ui`
  inside prints the link instead of opening it.
- **Ways out**:
  1. A setting (`LADO_IN_CONTAINER` or a `--published` address) that words the warning for
     a container and prints the host's link. Cost: S, code in cli.py and server/run.py.
  2. The launcher on the host prints or opens the link (`docker exec ... lado ui
     --no-open`). Cost: part of the launcher (section 8).

### 5.7 Updates

- **Cause**: `lado update` stops the UI server, the container's main process; Docker then
  kills every process in the container (H7). Also, a LADO updated in place lives in the
  container's writable layer and is lost when the container is made again from the image.
- **User sees**: the update and the UI's **Restart and update** end half way; LADO comes
  back on the old version; `update-result.json` says `running`.
- **Ways out**:
  1. `lado update` and the UI's update refuse in a container and name the way (`docker
     compose pull && docker compose up -d`). Cost: S; how LADO knows it is in one (an
     environment variable the image sets).
  2. A supervisor process (tini plus a small loop, or s6) that keeps the container up
     while the server restarts. Cost: the update still lives only until the next
     recreation.
  3. The CLIs too: updated only with a new image (they are pinned; self-update off).

### 5.8 The container's life

- **Cause**: tmux, the agents and the session loops are processes of the container.
- **User sees**: after a stop, a restart of Docker or of the computer, every session is
  "tmux session is gone" and must be resumed (H7); workers outside runs are forgotten.
  The agents' config folders stay behind (`lado doctor` warns).
- **Ways out**:
  1. On start, the image resumes the sessions that were running (a `lado start` per
     session, from a list LADO keeps). Cost: M; LADO has no "resume all" today.
  2. `docker stop` gives LADO time: the container's stop runs `lado stop --all`
     (`STOPSIGNAL` handled by a small entrypoint). Cost: S; it removes the config
     folders, but sessions still need a resume.
  3. An init that reaps processes is needed and in place (`tini`; `docker run --init`
     does the same, <https://docs.docker.com/reference/cli/docker/container/run/#init>).

### 5.9 Docker in the agents' tools

- **Cause**: a project whose tests start containers needs a Docker daemon inside.
- **User sees**: `docker: command not found` or no daemon.
- **Ways out**:
  1. Mount the host's Docker socket. Cost: whoever controls the socket is root on the host
     (<https://docs.docker.com/engine/security/#docker-daemon-attack-surface>): the
     sandbox is gone.
  2. Docker in Docker (privileged). Cost: privileged, heavy.
  3. Not supported; such projects use the native install. Cost: none; recommended.

### 5.10 Local models on the host

- **Cause**: `localhost` inside is the container.
- **User sees**: connection refused for `http://localhost:1234`.
- **Way out**: `host.docker.internal` (Docker Desktop; on a Linux engine the compose line
  `host.docker.internal:host-gateway`,
  <https://docs.docker.com/reference/cli/docker/container/run/#add-host>), H5. Cost: the
  CLI's provider config names that host, a step the user must know.

### 5.11 Speed of bind mounts

- **Cause**: on macOS and Windows a bind mount crosses from the Linux VM to the host's
  file system.
- **User sees**: slower builds and git on big repositories. Measured here (3000 small
  files written, then `git add` and `git commit`): `/projects` (bind mount) 0.52 s and
  1.91 s; the home volume 0.03 s and 0.14 s. About 14 times slower for git's writes.
- **Ways out**:
  1. Projects on a volume (fast) and the host reaches them through git only (push, pull).
     Cost: the user cannot open the files in a host editor directly.
  2. Accept it: an agent's turn is dominated by the model, not by git. Cost: none for
     small repositories.

### 5.12 Images for arm64 and amd64

- **Cause**: Apple silicon and most Windows and Linux machines differ.
- **Way out**: `docker buildx build --platform linux/amd64,linux/arm64`
  (<https://docs.docker.com/build/building/multi-platform/>); every part of the image
  exists for both (Debian, NodeSource, the CLIs' npm packages ship both). Cost: CI time;
  the amd64 image was not built here.

### 5.13 Docker Desktop's licence and resources

- **Cause**: Docker Desktop is free for personal use, education, non-commercial open
  source and companies under 250 employees and $10 million revenue; larger companies
  need a paid subscription (<https://docs.docker.com/subscription/desktop-license/>). It
  runs a Linux VM with its own memory and disk (8 GB of memory here).
- **User sees**: a licence question at work; Docker Desktop's VM taking memory beside the
  agents.
- **Ways out**: Docker Engine on Linux (free); on macOS, alternatives such as Colima or
  OrbStack (not checked). Cost: each a different install, against the one-command goal.

### 5.14 Security

- **Cause and gain**: the agents run with the permission mode the user chose, often
  bypassed. In the container they reach only the projects folder, the home volume and the
  network, not the host's home, keys or other repositories: a real gain over the native
  install.
- **Limits**: the ssh agent (5.5) and a Docker socket (5.9) given to the container give
  the agents those powers too; the logins on the volume are readable by every agent.
  The UI's port must stay on the host's loopback (compose.yaml), as the server inside
  listens on every address.

### 5.15 LADO's machine logic in a container

- `lado doctor`: passes (H1); its `Graphical session` check does not apply (not a Mac).
- macOS keychain logic (`gui_session.place` returns `other` off macOS; Claude Code's
  `keychain_login` is None off macOS, providers/claude.py): never triggered in the
  container, as Linux CLIs keep their logins in files.
- Telemetry: the report's `os` is `linux` and `arch` `aarch64`, `installer` `uv`
  (telemetry.py, `_installer`); a container is not told apart from a Linux install. A
  field for it would need docs/telemetry.md's list and `FIELDS_VERSION` bumped.
- `lado uninstall` inside removes LADO_HOME and tries the program; for the image the way
  is `docker compose down -v` and removing the image.

## 6. Platforms

- **macOS**: checked here (Docker Desktop, Apple silicon). Works with the workarounds of
  sections 4 and 5. Intel Macs need the amd64 image (not built).
- **Windows** (not checked; from documentation): Docker Desktop with the WSL2 backend
  (<https://docs.docker.com/desktop/setup/install/windows-install/>) needs WSL2 anyway,
  but installs and manages it itself. A bind mount of a Windows folder (`C:\Users\...`) is
  slow; Docker's own advice is to keep the files in the WSL file system
  (<https://docs.docker.com/desktop/features/wsl/best-practices/>), which a
  non-programmer will not find in Explorer easily (`\\wsl$\...`). The ssh agent socket of
  section 5.5 is Docker Desktop's on Windows too (same page as H8). The gain here is the
  largest: no Ubuntu user, apt, NodeSource or uv steps.
- **Linux** (not checked; from documentation): Docker Engine, free; `host.docker.internal`
  needs the `host-gateway` line (in compose.yaml); file ownership (5.4); the ssh socket is
  the user's `$SSH_AUTH_SOCK` mounted. A Linux user has apt already, so the gain is the
  smallest.

## 7. Alternatives

| Way | Removes | Leaves | Cost |
|---|---|---|---|
| Docker image (this report) | tmux, git, uv, Node.js, the CLIs; WSL setup by hand on Windows | Docker itself, logins inside, toolchains, paths, updates from outside | L (image, CI for two architectures, launcher, five code changes) |
| One-command install script (`curl ... \| sh`): installs what `lado doctor` would print (brew or apt, uv, Node.js, LADO, a chosen CLI) | the typing and the order of docs/install.md, most failures of "If something goes wrong" | Homebrew on macOS, WSL on Windows, the CLI's login | S/M |
| Homebrew formula (`brew install lado` with tmux, uv, node as dependencies) | three steps on macOS | the CLI and its login; macOS and Linuxbrew only | S |
| Desktop app (ROADMAP stage 7) | the terminal entirely; the UI as an app | the runtime's dependencies, unless it bundles them (or a container) | L, planned |
| Dev container (<https://containers.dev/>): LADO as a feature added to a project's `.devcontainer` | the toolchain problem (5.2): the project's own image | the user must use VS Code or a devcontainer CLI; per project | M |

**Recommendation**: build the one-command install script first: it serves the macOS and
Linux users who are most of LADO's users today, with the least maintenance, and it is
reused inside the Docker image. Then the Docker image, aimed at Windows users and at those
who want the agents sandboxed, with the fixes it needs (section 8). The desktop app of
stage 7 can later bundle the same image or script instead of its own installer.

## 8. Proposed tasks

Drafts; none is created in the tracker without the human's yes. Titles in Russian, as the
tracker is.

1. **«Установочный скрипт одной командой»** — `install.sh`: by the system, brew or apt,
   uv, Node.js, LADO, an agent CLI of the user's choice, then `lado doctor`. Size M.
   Depends on nothing.
2. **«Перенос логина Codex в агентов»** — the BACKLOG entry: carry `auth.json` into each
   Codex agent's `CODEX_HOME`. Size S/M. Depends on nothing; needed by task 5 for Codex.
3. **«lado update в контейнере»** — refuse `lado update` and the UI's update when an image
   sets `LADO_CONTAINER`, naming the image's way. Size S. Depends on nothing.
4. **«Ссылки и предупреждение UI-сервера в контейнере»** — the warning and the links of
   5.6 for a server published on the host's loopback; the picker's start folder. Size S.
   Depends on nothing.
5. **«Образ Docker для LADO»** — the image (from this prototype: projects at the host's
   path, any uid, tini, a stop that runs `lado stop --all`), compose file, multi-arch build
   and publishing in the release workflow (GHCR), a docs/install.md section, a smoke test
   of the image in CI. Size L. Depends on 2, 3, 4.
6. **«Возобновление сессий при старте контейнера»** — resume the sessions that ran when
   the container stopped. Size M. Depends on 5.
7. **«Лаунчер Docker для не-программистов»** — a script or shortcut per system that runs
   compose, waits, opens the UI's link and the logins. Size M. Depends on 5.
