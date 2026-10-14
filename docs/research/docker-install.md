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

**Verdict: build it as LADO's main way in, as it isolates the agents from the user's
machine; a one-command install script stays for those without Docker (section 7).** One
image, to publish on GHCR (5.16), holds LADO and four CLIs behind the web UI: sessions,
workers, a Claude Code login, restarts, resumes and a project's toolchain from mise work
(H1-H3, H5-H7, H9). It isolates the agents from the host, not from each other; a
container per session is the next step (5.14). Largest difficulties:

1. **Toolchains**: a thin image with mise in the home volume (H9), and a project's dev
   container where it has one (5.2).
2. **Files and paths**: git links worktrees by the container's paths (H6, 5.3); on a
   Linux host the files need the host user's uid (5.4).
3. **Updates and logins**: `lado update` inside kills itself (H7); CLIs log in inside,
   and only a Linux host's login files can be mounted (a Mac keeps Claude Code's in the
   keychain); a first-start wizard in the UI should replace `docker exec` (5.1).

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

The prototype builds its image on the first `up`. A product would ship a ready image
(5.16), so the user builds nothing. It would also hide these commands behind a script or
a desktop shortcut, and the login behind a wizard in the UI (section 8). The user still
has to know where the projects folder is and that agents see only it.

## 3. The prototype

Files: [Dockerfile](docker-install/Dockerfile) and
[compose.yaml](docker-install/compose.yaml), as they were when the checks ran. One change
was made during the checks: `group_add` for H8, and the checks after it ran with it.
After the review, two comments changed, not the files' behaviour: the ssh socket line is
marked as Docker Desktop's only, and the Dockerfile's usage line lost a needless `-it`.
H9 ran on the same image, with mise installed into the home volume at run time (not in
the Dockerfile). Evidence, not a product: no build or CI picks them up.

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
| H3 | Claude Code: subscription login inside, a LADO session's turn on it, the login after recreating | works | [H3](#h3-claude-code-login) |
| H4 | Codex: ChatGPT login inside; a LADO Codex agent on it | not checked: the human has no ChatGPT/Codex subscription | [H4](#h4-codex-login) |
| H5 | OpenCode and Kilo supervisors run a turn on LM Studio's model on the host | works | [H5](#h5-local-model-on-the-host) |
| H6 | A worker commits on the bind-mounted repository; the host's view of it | works with a workaround | [H6](#h6-a-worker-on-the-bind-mount) |
| H7 | Container stopped and started; recreated from the image; `lado update` inside | works (restart, recreate); `lado update` does not work | [H7](#h7-restart-recreate-update) |
| H8 | The host's ssh agent, `git push`, `gh` from inside | works with a workaround | [H8](#h8-ssh-agent-push-gh) |
| H9 | mise in the home volume installs a project's Go and Python; the agents' `PATH` finds them; they survive recreating the container | works with a workaround | [H9](#h9-a-toolchain-from-mise) |

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

The human ran `docker exec -it lado claude` in a terminal on the host, chose the login
with a Claude subscription, opened the link it printed in the host's browser and pasted
the code back. The login is a file on the home volume (`CLAUDE_CONFIG_DIR` is
`~/.claude`):

```
$ docker exec lado claude auth status
  "loggedIn": true,
  "authMethod": "claude.ai",
$ docker exec lado stat -c '%a %n' /home/lado/.claude/.credentials.json
600 /home/lado/.claude/.credentials.json
```

A LADO session with `--provider claude` on `/projects/demo`:

```
$ docker exec lado lado start /projects/demo --name demo-claude --provider claude --no-attach --prompt "Say hello ..."
lado: Claude Code asks whether to trust /projects/demo: in its terminal choose "Yes, I trust this folder" (Enter alone answers "No, exit" and closes the agent)
# answered "Yes, I trust this folder" in the agent's window
$ docker exec lado lado log demo-claude
07:53:53 supervisor: blocked (Claude Code asks whether to trust /projects/demo: ...)
07:54:04 supervisor: mcp_ready (...)
07:54:11 supervisor → human [delivered] Hello! I'm the supervisor of this LADO session, and I run on Claude Opus 5.5 (claude-opus-5-5).
```

After `docker compose up -d --force-recreate`, `claude auth status` still said
`"loggedIn": true`, and `lado start /projects/demo --name demo-claude` resumed the
session with no trust question (the answer is in `.claude.json` on the volume): the
supervisor ran its turn. The other way, `CLAUDE_CODE_OAUTH_TOKEN` from `claude
setup-token`, was not run (it needs a token of the human's); its catch in a container is
in section 5.1.

### H4: Codex login

Not checked: the human has no ChatGPT or Codex subscription. From documentation and the
CLI: `codex login --device-auth` (its `--help` lists it) prints a link and a code to enter
in any browser, so it needs no callback port into the container; Codex keeps the login in
`auth.json` under `CODEX_HOME` when its `cli_auth_credentials_store` is `file`, or in the
system's credential store (`keyring`, `auto`)
(<https://developers.openai.com/codex/auth>). In a container without a keyring that is
`~/.codex/auth.json` on the home volume. A LADO Codex agent would not use it: each agent
gets its own `CODEX_HOME`, and LADO does not carry `auth.json` into it (providers/codex.py;
BACKLOG.md, "Codex agents cannot log in"), so it would show Codex's login screen, in the
container as on a host.

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
<https://git-scm.com/docs/git-gc>) drops git's record of it, in the container too, as the
repository is shared. The folder stays. LADO's `runtime.gone` judges a worktree by its
folder only, so it does not count it as gone. Finishing the worker, or ending its run,
then calls `git worktree remove`, and git refuses with `fatal: '<path>' is not a working
tree` (the reviewer reproduced this in a scratch repository; BACKLOG.md). Files the container writes are the host
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
agents get `SSH_AUTH_SOCK`: it is one of the few variables `agent_env.resolve` starts the
login shell with (checked by calling it inside the container, section 5.1). The first push, right after the bare repository was
made on the host, failed with `does not appear to be a git repository`; the same push a
moment later worked.

`gh` has no login inside (`You are not logged into any GitHub hosts`): the host's is in
the macOS keychain. With `GH_TOKEN` passed to one `docker exec` (`-e GH_TOKEN`), `gh api
user` worked and `gh auth status` said `Logged in ... (GH_TOKEN)`. A lasting login is `gh
auth login` inside, which keeps the token in `~/.config/gh/hosts.yml` on the volume, as a
plain file when no keyring is there (<https://cli.github.com/manual/gh_auth_login>; not
run).

### H9: a toolchain from mise

A fresh container of the same image, with an empty home volume and a scratch projects
folder; no login. mise (<https://mise.jdx.dev/>) was installed as the user `lado` with its
script, into `~/.local/bin` on the home volume. Its shims folder went first on `PATH` in
`~/.profile`, which the login shell reads, so the agents get it too. A project with a
`.tool-versions`:

```
$ docker exec lado bash -lc 'curl -fsSL https://mise.run | sh'
mise: installed successfully to /home/lado/.local/bin/mise
# ~/.profile: export PATH="$HOME/.local/share/mise/shims:$PATH"
$ cd /projects/gotest && echo "go 1.23.4" > .tool-versions && mise install
mise ✓ go@1.23.4  9.6s  go1.23.4.linux-arm64.tar.gz
$ go version
go version go1.23.4 linux/arm64
```

The agents' environment, as LADO builds it (`agent_env.resolve()` called inside the
container), had `/home/lado/.local/share/mise/shims` first on its `PATH`, and `go` was
found there. After `docker compose up -d --force-recreate`, `go version` in the project
still said `go1.23.4`: the tools are on the home volume (`~/.local/share/mise`, 267 MB
with Go and one Python; mise's data folder, <https://mise.jdx.dev/directories.html>). No
root and no new image were needed.

Three catches:

- **Outside a project that names a version, a shim fails.** In `/tmp`, `go version` said
  `mise ERROR No version is set for shim: go`. An agent works in its worktree, which has
  the project's committed `.tool-versions`, so this hits only a version file that is not
  committed.
- **Other tools' version files are read only once enabled.** `.python-version` with
  `3.12.7` gave `python: command not found` until `mise settings add
  idiomatic_version_file_enable_tools python` (mise's "idiomatic version files",
  <https://mise.jdx.dev/configuration.html>).
- **Some prebuilt versions are refused.** Python 3.12.7 then failed with `No GitHub
  artifact attestations found for python@3.12.7`. `3.13` installed 3.13.16 in 5.7 s.

Not checked: a LADO agent itself installing a tool when it meets `command not found`. The
volume was removed after the check.

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
     `OPENAI_API_KEY` or `codex login --with-api-key` for Codex with an API key. Catch: by
     default compose's `environment:` does not reach the agents. LADO builds an agent's
     environment from the login shell, started with a few variables only (AGENTS.md, How
     agents talk; `agent_env.resolve`). Called inside the container with `-e LADO_PROBE=1
     -e CLAUDE_CODE_OAUTH_TOKEN=dummy`, it passed neither of them. It did pass
     `SSH_AUTH_SOCK` and what `/etc/profile.d/lado.sh` exports. Two ways to get the token
     to the agents:
     - `LADO_AGENT_ENV=inherit` in the image's environment. The agents then get the
       environment of the process that starts them, compose's variables included
       (`agent_env.resolve` takes `os.environ`; LADO's own hints suggest it, `INHERIT_HINT`).
       The processes that start agents are the UI server, the container's command, and
       `docker exec ... lado start`. It also makes `/etc/profile.d` unneeded for `PATH`.
       Not run here. Cost: agents see the whole environment of whatever starts them, every
       other secret in compose's `environment:` too, and a `docker exec -e` adds to it.
     - Put the token in a file the login shell reads: `~/.profile` on the volume, or a
       profile script that reads a Docker secret. Cost: a long-lived token in a file, and
       the image must document where it goes.
  3. LADO carries Codex's `auth.json` into each agent's `CODEX_HOME` (the BACKLOG entry):
     needed for Codex with a ChatGPT login in any setup, not only Docker. Cost: S/M.

**The agent CLI the user already has on the host, logged in.** The wish: no login step in
the container at all. By documentation, LADO's code and two harmless checks (no host
login or config was mounted):

- *Mount the host's login and config into the container.* What is on the host:
  - Claude Code on macOS keeps its login in the login keychain ("Claude
    Code-credentials", providers/claude.py, `keychain_login`;
    <https://docs.anthropic.com/en/docs/claude-code/iam>), not in a file, so mounting
    `~/.claude` carries no login; only a Mac whose keychain refused the write has
    `~/.claude/.credentials.json`. Its settings and folder trust are in `~/.claude.json`,
    outside `~/.claude`, with the host's paths. On a Linux host the login is
    `~/.claude/.credentials.json` (mode 600, same page), which a mount does carry.
  - Codex: `~/.codex/auth.json` when `cli_auth_credentials_store` is `file`, else the
    system's store (<https://developers.openai.com/codex/auth>); and LADO does not carry
    it to its agents anyway (H4).
  - OpenCode and Kilo: `~/.local/share/opencode/auth.json` and
    `~/.local/share/kilo/auth.json` (`opencode auth list` and `kilo auth list` print the
    path; <https://opencode.ai/docs/providers/>), plain files; LADO's OpenCode and Kilo
    agents read the user's data folder, so a mount would work for them.

  Costs: two programs then use one OAuth login, and both refresh it. Codex says it
  refreshes ChatGPT tokens during use (same page). Whether a refresh in one breaks the
  other is not checked; a copy instead of a mount is more likely to break, since only one
  side gets the new refresh token. File ownership on a Linux host (5.4). And the mount
  gives every agent in the container the host's real credentials (5.14).
- *Run the host's CLI binary in the container.* Impossible on macOS and Windows: their
  binaries are not Linux programs. Checked with a copy of macOS's `/bin/echo` mounted into
  a Debian container: `exec /x/echo: exec format error`. On a Linux host with the same
  architecture, an npm-installed CLI might run from a mount if its Node and libraries
  match. Cost: the image no longer pins the version LADO is tested with.
- *Agents on the host, only LADO in the container.* LADO cannot split so: an agent is a
  process in LADO's tmux server, and its hooks, `lado mcp` and the session loop are LADO
  processes on the same `lado.db` (AGENTS.md, Layout: `runtime.py`, `interpreter.py`,
  `hooks.py`). A host agent needs tmux, LADO and its Python on the host: that is the
  native install, and the container would only hold the UI server, which `lado ui`
  starts natively anyway. Nothing of the Docker gain is left.
- *A token from the host.* `claude setup-token` run once on the host gives a long-lived
  `CLAUDE_CODE_OAUTH_TOKEN` (way 2 above). This is the one host-side way that works for
  Claude Code on a Mac. Cost: the catch of way 2, and the token is a full login to the
  subscription in a file. Not run here: it needs the human's token.

Recommendation: log in inside once (way 1). Use a token from the host only when the user
already has one, passed with `LADO_AGENT_ENV=inherit` or in the login shell's profile
(way 2). Mount the host's files only on Linux, and only for OpenCode and Kilo.

**First start and models.** Nothing comes from the host: the agents' settings live only
on the container's `home` volume, which is empty at the first start. A user with no agent
CLI on the host is in the same place as one with all four, and needs only the logins.
Then:

- Claude Code and Codex work after their login on their default model (H3 for Claude
  Code; Codex from its documentation, <https://developers.openai.com/codex/auth>).
- OpenCode and Kilo need a provider first: an account or a key (`opencode auth login`,
  `kilo auth login`), or a local model, as LM Studio in H5.

Where each keeps its model:

- Claude Code: `model` in `~/.claude/settings.json`
  (<https://code.claude.com/docs/en/settings>), or `/model` in a session.
- Codex: `model` and `model_provider` in `~/.codex/config.toml`; LADO carries these into
  each agent's own config (providers/codex.py, `CARRIED`).
- OpenCode and Kilo: `model` and the provider in their global config,
  `~/.config/opencode/opencode.json` and `~/.config/kilo/kilo.json` (H5;
  <https://opencode.ai/docs/config/>).

Today the user changes a model in the agent's terminal in the UI, or by editing the file
through `docker exec`, which a non-programmer will not do. Way out: **a first-start
wizard in the UI**. It would let the user choose an agent and log in, showing the CLI's
link and code in the UI instead of a `docker exec` terminal. It would then let them pick
the model, or for OpenCode and Kilo the provider and model, and write that to the agent's
settings. Cost: M/L, code in LADO's server and UI. It helps the native install as well
(section 8).

### 5.2 The project's own toolchains

- **Cause**: an agent builds and tests the project with the programs of the container: the
  image has git, Node.js 22 and Python 3.11, nothing else (no compilers, `make`, Java, Go,
  Rust, databases).
- **User sees**: the agent reports `command not found` for the project's build or test,
  or installs it with `npm`/`pip` into the container, where it is lost on recreation.
- **Ways out**:
  1. **A thin image and a version manager in the home volume** (recommended). The image
     ships mise (or asdf) with its shims on the login shell's `PATH`. The agent installs
     Python, Node.js, Go or Java by the project's own files (`.tool-versions`, and once
     enabled `.nvmrc`, `.python-version`), and the tools stay on the home volume through
     a recreation, with no root (H9). Cost: S inside the image task. The agents' role or
     LADO's instructions should say to install a missing tool with mise (not checked:
     H9). It does not cover apt packages (system libraries, compilers' headers) or
     databases.
  2. **The project's own dev container** (<https://containers.dev/>): LADO added to the
     project's `.devcontainer` as a Dev Container Feature, so the project's image brings
     its tools. Cost: M; ideal for projects that have one, and a programmer's way.
  3. **Tests that start the project's containers** (its compose, Testcontainers) need
     Docker in the container: Docker in Docker, or the host's socket, which gives up the
     isolation (5.9).
  4. **Nix** (<https://nixos.org/>) describes a project's whole toolchain, apt's part too. Cost: hard to keep up;
     not for a first step.

  A "full" image with common toolchains is a dead end: several GB more, and still not
  every project. A derived image (`FROM lado` plus `apt-get install`) needs a programmer.

### 5.3 Paths of the container against the host

- **Cause**: LADO stores the repository path it was given (`sessions.repo`), and git links
  a worktree to its repository with absolute paths in `.git` files (git 2.39 has no other
  way; `--relative-paths` and `worktree.useRelativePaths` came with git 2.48,
  <https://git-scm.com/docs/git-worktree>).
- **User sees**: in the UI, paths like `/projects/demo`; the folder picker shows the
  container's root (H2); on the host, a worker's worktree is `prunable` and its folder is
  not a git repository (H6); an IDE on the host cannot open a worker's worktree as git.
  After a `git worktree prune` or `git gc` on the host, finishing that worker or ending
  its run fails with git's `is not a working tree` (H6).
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
  Files may even be ones the user cannot change or delete without `sudo`.
- **Ways out**:
  1. **On Docker Engine on Linux only, the image takes the uid of the projects' owner**
     (recommended there). At start, as root, its entrypoint reads the owner of
     `/projects` and gives the user `lado` that uid and gid, then drops to it (tools such
     as fixuid or gosu). Files the agents write are then the host user's. VS Code Dev
     Containers do the same, also only on Linux: `updateRemoteUserUID` "On Linux, if
     `containerUser` or `remoteUser` is specified, the user's UID/GID will be updated to
     match the local user's UID/GID to avoid permission problems with bind mounts",
     default `true` (<https://containers.dev/implementors/json_reference/>). On Docker
     Desktop the entrypoint must leave uid 1000 alone. There the bind mount's folder shows
     as `0:0` to any container user: `docker run --rm -u <uid> -v <folder>:/projects
     debian:bookworm-slim stat -c '%u:%g' /projects` printed `0:0` for uid 0, 1000 and 1234
     on this Mac. So the entrypoint would make `lado` root. It skips an owner of 0, and
     Docker Desktop maps the files to the host user anyway (H6). Cost: S inside the image
     task; the home volume's files must follow the new uid (a `chown` of the volume when
     the uid changes). Not checked on a Linux host.
  2. **Rootless Podman with `--userns=keep-id`**, which maps "the current user's UID:GID
     ... to the same values in the container"
     (<https://docs.podman.io/en/latest/markdown/podman-run.1.html>), or rootless Docker
     or user namespace remapping (<https://docs.docker.com/engine/security/userns-remap/>).
     Cost: another install, for prepared users only.
  3. **Projects in a volume instead of a bind mount**, as Dev Containers' "Clone
     Repository in Container Volume" ("an isolated, local Docker named volume instead of
     binding to the local filesystem", with "improved performance on Windows and macOS",
     <https://code.visualstudio.com/remote/advancedcontainers/improve-performance>) and
     GitHub Codespaces do. Gains: no ownership problem, no paths seen twice (5.3), git
     about 14 times faster on a Mac (5.11), and stricter isolation: nothing of the host's
     disk is mounted. Costs: the files are not in Finder or Explorer; the user reaches
     them through LADO's UI, git (push, pull) or an editor that attaches to the
     container. The UI then must show the work and hand it out (files, a diff, a
     download). Cost: M/L of UI work.

  Recommendation: by default a bind mount, so the user sees the files as before, with the
  uid taken from the projects' owner on a Linux host's Docker Engine and uid 1000 kept on
  Docker Desktop; projects in a volume as an option. If isolation
  becomes the main goal, the volume is the stricter default to weigh, together with a
  container per session (5.14).

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
  1. A setting (`LADO_CONTAINER`, which the image sets, or a `--published` address) that words the warning for
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
     compose pull && docker compose up -d`). Cost: S; LADO knows it is in one by
     `LADO_CONTAINER`, which the image sets.
  2. A supervisor process (tini plus a small loop, or s6) that keeps the container up
     while the server restarts. Cost: the update still lives only until the next
     recreation.
  3. The CLIs too: updated only with a new image (they are pinned; self-update off).

**The agents' versions in the image.** Recommended: the versions LADO is tested with (each
provider's `TESTED_VERSION`, the pins of `scripts/smoke_ci.py`), not the newest at build
time, and a new image with each LADO release. Why: the image is reproducible, `lado
doctor` warns about no version, and LADO's hooks depend on each CLI's behaviour, which
changes between versions (the providers' comments name the version each claim was checked
with, AGENTS.md, How agents talk). A user may install a newer CLI into the home volume
(`npm install -g --prefix ~/.local`), and it survives a recreation. But that is a step in a
terminal, and the versions then drift from what LADO was tested with.

The four CLIs take 1.8 GB of the 2.46 GB (section 3). Images with one agent each (for
example `lado:claude`, `lado:opencode`) would be about 1.0-1.2 GB: 2.46 GB less the other three CLIs (sizes in section 3). Cost: a build matrix in
the release workflow.

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
     Cost: the user cannot open the files in a host editor directly (5.4, way 3).
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
  Mounting the host's own CLI logins (5.1) hands agents with bypassed permissions the
  host's real credentials. An agent could read and send them elsewhere. That gives up the
  isolation that is the image's gain here.
  The UI's port must stay on the host's loopback (compose.yaml), as the server inside
  listens on every address.
- **Levels of isolation**:
  1. *One container for everything* (this prototype). The agents are kept from the host,
     but not from each other: every agent of every session sees all projects under
     `/projects`, every login on the home volume and LADO_HOME's `lado.db`.
  2. *A container per session or project*. Each session's agents see only its
     repository and the logins given to it. This fits LADO better than a container per
     agent: an agent's hooks, `lado mcp` and the session loop are LADO processes beside it,
     on its tmux server and `lado.db` (5.1, "Agents on the host"). A per-agent container
     would cut those links. Cost: L. LADO would start containers (so the UI server needs
     Docker's socket or a helper on the host), and keep a session's state where its
     container and the UI both reach it. This is a direction for ROADMAP after the first
     image, not part of it (section 8).

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

### 5.16 Publishing the image

- **Cause**: the user should pull a ready image, not build one (the prototype's build took
  113 s and needs the Dockerfile).
- **Ways out**:
  1. **GitHub Container Registry, `ghcr.io/ladohq/lado`** (recommended). "GitHub Packages
     usage is free for public packages", and "Container image storage and bandwidth for
     the Container registry is currently free", with at least a month's notice before
     that changes (<https://docs.github.com/en/billing/concepts/product-billing/github-packages>).
     A workflow pushes with its own `GITHUB_TOKEN` and `permissions: packages: write`
     (<https://docs.github.com/en/packages/managing-github-packages-using-github-actions-workflows/publishing-and-installing-a-package-with-github-actions>),
     so the release workflow needs no account and no secret: LADO's CI has none
     (AGENTS.md, Commands). Cost: a job in the release workflow.
  2. **Docker Hub**. A public repository is free, but needs a Docker account or
     organisation and its token as the first secret of LADO's CI. Anonymous pulls are
     limited to 100 per 6 hours per IPv4 address or IPv6 /64 subnet, 200 for a logged-in
     free user (<https://docs.docker.com/docker-hub/usage/pulls/>), which an office
     behind one address can reach. The Docker-Sponsored Open Source programme lifts the
     limits, for projects "in active development with no pathway to commercialization"
     (<https://docs.docker.com/docker-hub/repos/manage/trusted-content/dsos-program/>);
     whether LADO fits is the maintainers' call. Gain: Docker Desktop's search finds
     images there by name.

  Recommendation: GHCR first; the same image can later also be pushed to Docker Hub for
  its search, with no change for the users of GHCR. Both need the two architectures
  (5.12). Figures as of 2026-10-14.

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
| Docker image (this report) | tmux, git, uv, Node.js, the CLIs; WSL setup by hand on Windows; the agents' reach into the host's home | Docker itself, logins inside, apt-level toolchains, paths, updates from outside | L (the image with mise and the uid fix, GHCR for two architectures, launcher, and LADO's code in tasks 1, 2, 3, 5, 7 and 8 of section 8) |
| One-command install script (`curl ... \| sh`): installs what `lado doctor` would print (brew or apt, uv, Node.js, LADO, a chosen CLI) | the typing and the order of docs/install.md, most failures of "If something goes wrong" | Homebrew on macOS, WSL on Windows, the CLI's login | S/M |
| Homebrew formula (`brew install lado` with tmux, uv, node as dependencies) | three steps on macOS | the CLI and its login; macOS and Linuxbrew only | S |
| Desktop app (ROADMAP stage 7) | the terminal entirely; the UI as an app | the runtime's dependencies, unless it bundles them (or a container) | L, planned |
| The host's agent CLI, already logged in, used by the image (section 5.1) | the login step | macOS and Windows binaries do not run in the container; Claude Code's macOS login is in the keychain; agents on the host means the native install | none to build; mounting logins costs the sandbox |
| Dev container (<https://containers.dev/>): LADO as a feature added to a project's `.devcontainer` | the toolchain problem (5.2): the project's own image | the user must use VS Code or a devcontainer CLI; per project | M |
| Container per session or project (5.14) | what one container leaves open: one session's agents reaching other projects and the logins | LADO starting containers; state shared between them and the UI | L, after the image |

**Recommendation**: make the Docker image LADO's main way in. The reason is that it
isolates the agents from the user's machine, a goal of the product, and on Windows it also
replaces the WSL setup. Its toolchains (5.2), file ownership and paths (5.3, 5.4) and
updates (5.7) are part of the first image, not later work. The one-command install script
stays as the fallback for those who will not run Docker (a company without Docker
Desktop's licence, 5.13; a project that needs the host's Docker, 5.9). It is smaller and
can come after the image. The Dev Container Feature serves projects that have their own
dev container. A container per session is the next step of isolation, on ROADMAP. The
desktop app of stage 7 can later bundle the image instead of its own installer.

## 8. Proposed tasks

Drafts; none is created in the tracker without the human's yes. Titles in Russian, as the
tracker is. In the order of the verdict: what the first image needs, the image, what makes
it usable without a terminal, then the fallback and the next steps.

1. **«lado update в контейнере»** — refuse `lado update` and the UI's update when an image
   sets `LADO_CONTAINER`, naming the image's way (5.7). Size S. Depends on nothing.
2. **«Ссылки и предупреждение UI-сервера в контейнере»** — the warning and the links of
   5.6 for a server published on the host's loopback; the picker's start folder (5.3).
   Size S. Depends on nothing.
3. **«Перенос логина Codex в агентов»** — the BACKLOG entry: carry `auth.json` into each
   Codex agent's `CODEX_HOME` (5.1). Size S/M. Depends on nothing; needed by task 4 for
   Codex.
4. **«Образ Docker для LADO»** — the image from this prototype, with:
   - a thin base and mise with its shims on the login shell's `PATH`, and the agents told
     to install a missing tool with it (5.2, H9);
   - the projects mounted at the host's path (5.3); on a Linux host's Docker Engine only,
     an entrypoint that gives `lado` the uid of the projects' owner, never an owner of 0,
     which is what Docker Desktop shows (5.4); `safe.directory` for `/projects` in the
     image's git config (H6);
   - tini, and a stop that runs `lado stop --all` (5.8);
   - a documented way to pass `CLAUDE_CODE_OAUTH_TOKEN`: `LADO_AGENT_ENV=inherit` or the
     login shell's profile (5.1);
   - the CLIs at their `TESTED_VERSION`, a new image per LADO release, and perhaps images
     with one agent each (5.7);
   - the compose file (the ssh socket line per system, 5.5), a build for amd64 and arm64
     published to GHCR by the release workflow with `GITHUB_TOKEN` (5.12, 5.16);
   - a docs/install.md section, and a smoke test of the image in CI.

   Size L. Depends on 1, 2, 3.
5. **«Мастер первого запуска в UI»** — choose an agent, log in with the CLI's link and
   code shown in the UI, choose the model (for OpenCode and Kilo the provider and model),
   written to the agent's settings (5.1, "First start and models"). Size M/L. Depends on
   nothing; useful for the native install too, and in the image after task 4.
6. **«Лаунчер Docker для не-программистов»** — a script or shortcut per system that runs
   compose, waits, and opens the UI's link. Size M. Depends on 4.
7. **«Возобновление сессий при старте контейнера»** — resume the sessions that ran when
   the container stopped (5.8). Size M. Depends on 4.
8. **«Проекты в томе Docker»** — an option of the image to keep the projects in a volume:
   cloning there from the UI, and the UI showing and handing out the work (files, diff,
   download) (5.4, way 3). Size M/L. Depends on 4.
9. **«LADO как Dev Container Feature»** — LADO and an agent CLI added to a project's own
   `.devcontainer` (5.2, way 2). Size M. Depends on 4 (the same install steps).
10. **«Установочный скрипт одной командой»** — the fallback without Docker: `install.sh`
    by the system, brew or apt, uv, Node.js, LADO, an agent CLI of the user's choice, then
    `lado doctor`. Size M. Depends on nothing.
11. **«Контейнер на сессию»** — a ROADMAP item, not a task yet: each session's agents in
    a container of their own, seeing only its repository and the logins given to it
    (5.14). Size L, with its own research first. Depends on 4 and 8.
