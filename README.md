# LADO

**Layered Agent Delegation & Orchestration**

LADO runs teams of AI coding agents. Supervisors split work into tasks and hand them to specialist agents; the agents coordinate, and a human approves the key decisions. It is built for work that is too large for a single agent session.

> **Status: early development, usable.** `lado start <repo>` runs a team of agents, `lado ui`
> opens the web UI; kits and flows work. Expect changes between versions; see
> [ROADMAP.md](ROADMAP.md) for what is done and what comes next.

## The name

*Lado* is short for **L**ayered **A**gent **D**elegation & **O**rchestration.

In Russian, *лад* (lad) means harmony or being in tune, the way a well-run team works. The same root gives *наладить*: to set up, to get something working.

## What works now

- **Delegation.** A supervisor agent breaks work down and starts worker agents, each in its
  own git worktree and branch, all in tmux on your machine.
- **Messages.** Agents send each other tasks and reports through LADO, and can write to you
  or ask you.
- **Providers.** Claude Code, Codex CLI, Kilo CLI and OpenCode, chosen per session and per
  worker.
- **Kits.** Agent roles, skills, MCP servers and flows in a git repository or a folder,
  installed with `lado kits add` or from a marketplace ([Kits guide](docs/kits.md)).
- **Flows.** Steps, outcomes and human gates that LADO enforces, not the agent; you answer a
  gate with `lado answer`, in a tmux popup or in the web UI.
- **Artifacts.** Named, versioned documents of a session (a design, a plan, a review) that
  agents write and read, and you read in the web UI.
- **Task trackers as kits.** Kits for Jira Server and YouGile give agents a `tracker` skill
  to read, create, move and comment on tasks.
- **Web UI** (in progress). `lado ui`: sessions, agents and their terminals, messages, gates,
  flow runs, kits.

## Planned

- **Desktop app** that bundles the UI and LADO.
- **Conversations that survive a restart** of a session or an update.
- **ACP runtime.** Agents driven over the Agent Client Protocol instead of tmux.

## Install

Two ways, Docker first:

- **Docker** (recommended): LADO, tmux, git and the four agent CLIs at the versions LADO is
  tested with, in one container. The agents see only your workspace folder and the keys you
  give them, not the rest of your computer; you install nothing but Docker, and an update
  is one line. You work in the web UI. macOS and Linux; Codex's login is not carried yet.
- **PyPI** (`uv tool install lado`): LADO on your computer, with the agent CLIs and logins
  you already have; the agents run as you and reach what you can. You work in the terminal
  (tmux) and the web UI. macOS, Linux, and Windows inside WSL2.

What each one needs and how they differ: [docs/install.md](docs/install.md).

### Docker

A variable set in your shell beats the same one in `.env`; look first, and unset what you
find:

```bash
env | grep -E '^(LADO|COMPOSE)_'      # left from an earlier try? unset each name printed
unset LADO_VERSION LADO_PROJECTS LADO_PORT LADO_IMAGE COMPOSE_PROJECT_NAME
```

Then a folder of its own with the compose file of the latest release:

```bash
mkdir ~/lado-docker && cd ~/lado-docker
curl -fLO https://github.com/ladohq/lado/releases/latest/download/compose.yaml
```

Next to it, a file `.env`:

```ini
LADO_VERSION=<version>              # the latest release's number, from the releases page
LADO_PROJECTS=/Users/you/workspace  # your workspace folder, the only one the agents see
LADO_GIT_NAME="Your Name"           # git's identity for the agents' commits
LADO_GIT_EMAIL=you@example.com
```

`<version>` is the newest on the [releases page](https://github.com/ladohq/lado/releases),
without `v`. Then start it and open the link it prints:

```bash
docker compose up -d
docker compose exec lado lado ui --no-open   # the UI's link with its token
```

Logins, the agents' tokens (an optional `secrets/`), ssh, update and the rest:
[docs/install.md#docker](docs/install.md#docker).

### PyPI

LADO needs tmux, git, [uv](https://docs.astral.sh/uv/) and one agent CLI: Claude Code,
Codex, Kilo or OpenCode.

**macOS**

```bash
brew install tmux uv
uv tool install lado
```

**Linux** (Debian, Ubuntu)

```bash
sudo apt install -y git tmux curl
curl -LsSf https://astral.sh/uv/install.sh | sh && source ~/.local/bin/env
uv tool install lado
```

**Windows**: LADO runs inside WSL2. In cmd, as administrator:

```
wsl --install -d Ubuntu-24.04
```

then open Ubuntu and follow the Linux steps.

Then install an agent CLI, log in to it once, and check:

```bash
lado doctor             # says what is missing, with the command to install it
```

Step by step for each system, agent CLIs included, and what to do when something fails:
[docs/install.md](docs/install.md). Without uv, `pip install lado` works too.

## Quick start

In Docker, open the UI's link and press **Launch**; the commands below run there as
`docker compose exec lado lado ...`. From PyPI:

```bash
lado start <repo>       # a supervisor for a git repository (with at least one commit), in tmux
lado start <git-url>    # or clone one first, into ~/lado/<repo> (--branch NAME, or give a folder)
lado start --new <dir>  # no repository yet: a new or empty folder, made one with an empty commit
lado ui                 # the web UI in your browser
```

`lado start <repo> --prompt "Take LAD-19 and design it with me"` (or `--prompt-file FILE`,
`-` for stdin) gives the supervisor its first task as your message; it answers in the web
UI's chat. `lado start --help` lists the options (`--provider`, `--kit`, `--permission-mode`). `lado ls`
shows the sessions and their agents, `lado attach <session>` their tmux windows, `lado stop
<session>` ends one (`lado start` resumes it).

## Update

How you update depends on how you installed LADO. Either way LADO tells you when a newer
version is out: `lado ls` and `lado doctor` print `LADO X.Y.Z is available`, and the web UI
shows `↑ X.Y.Z` next to `live` in its top bar.

### Docker

A new version is a new image and its own `compose.yaml`. In the folder of your
`compose.yaml`, keep a copy of yours, download the new version's in place of it, set the
new version in `.env` (`LADO_VERSION=<version>`), then start:

```bash
cp compose.yaml compose.yaml.bak
curl -fLO https://github.com/ladohq/lado/releases/download/v<version>/compose.yaml
docker compose up -d     # pulls that version's image and replaces the container
```

`.env`, `secrets/` and the home volume stay; a change you made to `compose.yaml` by hand
must be carried over to the new one (`diff compose.yaml.bak compose.yaml`). Several LADOs:
update each in its own folder.

Your sessions stop with the old container and resume in the new one (each agent starts a
new conversation and a busy one loses its current turn, so update while your agents are
idle); LADO upgrades its database after a backup; logins, kits and history stay on the
home volume, and your workspace is not touched. `lado update` and the web UI's **Update…** do not update a
container: they say a new image does. Back to the version before:
[docs/install.md](docs/install.md#go-back-to-the-version-before).

### PyPI

**In the terminal**

```bash
lado update             # the latest version (lado update X.Y.Z for another one)
```

It shows what it will do and asks `Update? [y/N]` before it starts.

**In the web UI**

Click `live` in the top bar, then **Update…**. The window shows the same plan;
**Restart and update** starts it. The page waits while the server restarts, then says
how the update went.

**What happens to your work**

The update restarts your running sessions and the UI server. Runs, gates, branches and
worktrees stay; each agent starts a new conversation, and a busy agent loses its current
turn, so update while your agents are idle. If the new version does not start, LADO
puts back the one you had.

Installed with pip, from a git checkout or a git address? Then LADO cannot update
itself: `lado update` and the web UI show the commands to run by hand.

More (going back to an older version, an update that stops half way, the log):
[docs/install.md](docs/install.md#update).

To remove LADO: in Docker, `docker compose down` and its home volume by name
([docs/install.md](docs/install.md#remove-it)); from PyPI, `lado uninstall` stops
everything, cleans up after it and removes the program
([docs/install.md](docs/install.md#uninstall)).

## Kits

**A kit is a team you can install.** Roles, skills, tools and the way of working that
made one project go well, packed into a git repository, so the next project starts
where the last one ended instead of from a blank prompt.

- **Start with a team that already knows the job.** `sdlc` takes your tracker's tasks
  from design to a merged pull request, with you approving the design and the merge.
- **Mix and match.** Combine a process kit with a tracker kit (`sdlc` +
  `tracker-jira-server`), and switch off any role, skill, flow or tool per session.
- **Any agent CLI.** One kit runs on Claude Code, Codex, Kilo and OpenCode alike.
- **Versioned like code.** A kit is a release `vX.Y.Z` with pinned skill packs: the team
  behaves the same tomorrow, and `lado kits update` moves it on when you choose.
- **Build your own by talking.** The `kit-builder` kit interviews you about your process,
  writes the kit, and a critic checks it before you tag it.
- **Share it.** Publish a kit in a marketplace, and your team installs it with one command.

```bash
lado kits add sdlc -m official                     # a kit of the official marketplace
lado kits add tracker-jira-server -m official
lado start . --kit sdlc --kit tracker-jira-server  # a session with that team
```

Or open `lado ui`, then Kits. Everything else (finding and installing kits, writing one,
releasing new versions, combining them in a session, marketplaces) is in the
**[Kits guide](docs/kits.md)**.

## Marketplaces

**Your team's own list of kits.** A marketplace is a git repository that names the kits
your team trusts, so everyone installs them by name instead of passing addresses around.

- **One command for everyone.** `lado marketplaces add team <git-url>` once, then
  `lado kits add <kit> -m team`; the UI's Kits page lists its kits with their roles,
  flows and versions.
- **You decide what is in it.** Only the kits you reviewed are listed; a pull request to
  the list is your review step.
- **Private is fine.** LADO clones it with your own git access, so it can live next to
  your code.
- **Nothing to host.** No server: a repository with one YAML file, and an optional CI job
  that keeps its index fresh.

How to make one, its index and how to propose a kit to the official marketplace:
**[Marketplaces guide](docs/marketplaces.md)**.

## The web UI

```bash
lado ui                 # starts the UI server of this machine and opens the browser
lado server stop        # ends it
```

By default the server listens on 127.0.0.1 only. To open the UI of LADO on a remote host from
another machine, the safe way is an SSH tunnel, with the server left on 127.0.0.1:

```bash
ssh -L 8000:127.0.0.1:8000 remote-host    # then, on the remote host: lado ui --no-open
```

Open the printed link on your machine. Or let the server listen on every address of the
remote host:

```bash
lado ui --no-open --host 0.0.0.0    # prints the link for other machines too
```

It warns: whoever reaches the server with the token can run commands as you, and the
token travels unencrypted (plain HTTP). Do this only on a network you trust. A TLS proxy in
front of it (Caddy, `tailscale serve`, nginx) works if it keeps the `Host` header.

On a Mac, LADO started over ssh (`lado start`, `lado ui`, `lado update`) runs its agents in
your graphical session, where Claude Code reads its login from the Keychain: you must be
logged in on the Mac (at its screen or through Screen Sharing). With nobody logged in, LADO
warns, and Claude Code's agents need a token in your login shell instead:
`CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`. `lado doctor` shows where LADO and its
tmux server run (Graphical session).

## Usage statistics

LADO asks you once, in the UI and in `lado start` / `lado ui`, whether it may send its
maintainers anonymous usage statistics and its own errors; nothing is sent before you say
yes, and never a path, a name, a message or a key. `lado telemetry show` prints exactly what
would go, `lado telemetry off` or `DO_NOT_TRACK=1` switches it off. What is sent and where:
[docs/telemetry.md](docs/telemetry.md).

Found a bug? `lado bug-report` (or **Report a bug** in the UI's left menu) prints a report
with no paths or names and a link to a new GitHub issue filled in with it; nothing is sent
until you submit that issue.

## License

MIT (placeholder; to be confirmed before the first release).
