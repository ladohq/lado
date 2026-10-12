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

```bash
lado start <repo>       # a supervisor for a git repository (with at least one commit), in tmux
lado ui                 # the web UI in your browser
```

`lado start --help` lists the options (`--provider`, `--kit`, `--permission-mode`). `lado ls`
shows the sessions and their agents, `lado attach <session>` their tmux windows, `lado stop
<session>` ends one (`lado start` resumes it).

## Update

```bash
lado update             # the latest version; lado update X.Y.Z for another one
```

`lado ls`, `lado doctor` and the web UI say when a newer LADO is out (they look on PyPI at
most once a day; `LADO_NO_UPDATE_CHECK=1` switches that off). `lado update` shows its plan
(the versions, the installer's command, the sessions and the UI server it restarts) and
asks `Update? [y/N]` (`--yes` skips the question; without a terminal it is required). Then
it stops the running sessions and the UI server, installs exactly that version with the
installer LADO came with (`uv tool install lado==X.Y.Z`, or `pipx install --force`), checks
the installed version and resumes the sessions and the server with the installed `lado`.
Runs, gates, branches and worktrees stay; agents start a new conversation, and a busy
agent loses its current turn. A LADO installed otherwise (pip in a venv, a working copy or
a git address, also through uv tool or pipx) is not upgraded: `lado update` prints the commands to run by hand. If an update does not
finish, `lado ls` names the sessions left stopped and the `lado start` that resumes each.
Going back to an older version works the same way (`lado update 0.20.0`), as far as that
version accepts the database: an older LADO refuses a newer `lado.db`.

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

## License

MIT (placeholder; to be confirmed before the first release).
