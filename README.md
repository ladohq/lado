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
- **Providers.** Claude Code, Kilo CLI and OpenCode, chosen per session and per worker.
- **Kits.** Agent roles, skills, MCP servers and flows in a git repository or a folder,
  installed with `lado kits add` or from a marketplace.
- **Flows.** Steps, outcomes and human gates that LADO enforces, not the agent; you answer a
  gate with `lado answer`, in a tmux popup or in the web UI.
- **Web UI** (in progress). `lado ui`: sessions, agents and their terminals, messages, gates,
  flow runs, kits.

## Planned

- **Artifacts.** Named, versioned documents of a session (design, plan, review) shown in the UI.
- **Desktop app** that bundles the UI and LADO.
- **Conversations that survive a restart** of a session or an update.
- **ACP runtime.** Agents driven over the Agent Client Protocol instead of tmux.
- **Task trackers** (YouGile, Jira) as kits.

## Quick start

```bash
uv tool install lado    # or: pip install lado
lado doctor             # checks tmux and the agent CLIs: any of Claude Code, Kilo CLI, OpenCode
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

A kit is a team: agent roles, flows and skills, in a git repository (or a folder) with a
`kit.yaml` at its root. Its versions are the repository's tags `vX.Y.Z` (pre-releases such
as `v1.3.0-rc.1` too), and `version` in kit.yaml must say the same. It takes skill packs
from outside, pinned to a version, and may name the LADO it needs:

```yaml
name: my-team
version: 1.0.0
supervisor: lead        # the agent of this kit that leads a session; optional
dependencies:
  lado: ">=0.19"
  skills:
    superpowers: https://github.com/obra/superpowers@v6.4.1
```

```bash
lado kits add https://github.com/<owner>/my-team   # the latest release; @v1.0.0 for that one
lado kits add ./my-team                            # a local folder, read in place
lado kits add lado-dev -m official                 # a kit of a marketplace
lado kits outdated                                 # newer versions of the installed kits
lado kits update my-team                           # to the latest release
lado kits check . --tag "$TAG"                     # a kit's CI: what add would say of that tag
lado start . --kit default --kit my-team
```

A kit from anywhere but the official marketplace (github.com/ladohq/marketplace) or a
folder shows what it installs, its MCP servers too, and asks first (`--yes` to skip).
Marketplaces are git repositories with a `marketplace.yaml` that maps kit names to their
repositories:

```bash
lado marketplaces                                  # list them
lado marketplaces add team https://github.com/<owner>/marketplace
lado marketplaces update                           # fetch their latest lists
lado marketplaces disable official                 # remove works for the others
```

The UI's Kits page (`lado ui`, then Kits) does the same: the installed kits, the kits the
enabled marketplaces offer, the updates (checked only with its button) and the
marketplaces. Each install and update shows the plan the CLI prints before it asks.

What the page shows of a marketplace's kits comes from an `index.json` at the
marketplace's root, which its CI builds from the kits; LADO reads it from the marketplace's
clone, never the network. Version 1:

```json
{
  "index": 1,
  "kits": {
    "lado-dev": {
      "address": "https://github.com/ladohq/kit-lado-dev.git",
      "latest": "v0.9.1",
      "commit": "4be21c0…",
      "lado": ">=0.20",
      "description": "Develop LADO itself.",
      "agents": {"supervisor": "the first line of the role's description"},
      "skills": ["lado-checks"],
      "flows": ["feature", "fix"],
      "mcp": {"playwright": "npx @playwright/mcp"}
    }
  }
}
```

`latest` is the latest release (no pre-release) and `commit` its commit, `lado` the kit's
`dependencies.lado`, `mcp` each MCP server's command on one line. Only `address` is
required, and it must be the one `marketplace.yaml` gives; keys LADO does not know are
passed over, so the CI may add some without a new version; a higher `index` needs a newer
LADO. `marketplace.yaml` stays the list of names and addresses: an entry of a kit it does
not list is left out. Without `index.json` the page shows each kit's name and address.

Who leads a session: if exactly one of its kits has a supervisor, that one; otherwise
LADO's built-in supervisor. Then each kit's supervisor hands its rules to the built-in one
as a skill `lead-<kit>`: its prompt, and where to read the skills its `skills:` names, in
that kit's versions (copies the lead reads but does not load as its own skills, so two kits
may take two versions of one skill). Its MCP servers are not passed on, and a supervisor
without `skills:` passes none: LADO warns about both. Such a supervisor's `skills:` is
checked as if it led, so a skill its kit does not have stops the start. `lado start` and
`lado kits show` print who leads; `lado kits show` lists the lead skills. The supervisor starts workers with
`spawn_worker(role=...)`; the role may be left out only when the session has one.

`--without kind:name` switches off an agent, flow, skill or MCP server (kinds `agent`,
`flow`, `skill`, `mcp`) in the whole session. `--without kind:name@kit` switches it off in
that kit only, before the kits are combined: so two kits with a role of the same name, or
each with its supervisor, run together:

```bash
lado start . --kit default --kit my-team --without agent:supervisor@default
lado start . --kit kit-a --kit kit-b --without agent:reviewer@kit-b
```

A kit may use a skill that another kit of the session brings: it lists it under `expects`.
LADO installs `dependencies` with the kit; what a kit expects, another kit of the session
must bring. A process kit whose roles use the skill `tracker` of whichever tracker kit the
project uses:

```yaml
name: sdlc
version: 1.0.0
expects:
  skills: [tracker]    # a kit of the session must provide it
  commands: [openspec] # a CLI the kit's agents run, on their PATH
dependencies:
  lado: ">=0.30"       # the first LADO that reads expects.commands (expects.skills: 0.29)
```

```bash
lado kits check .                                  # passes alone: expects skills: tracker
lado start . --kit sdlc --kit tracker-jira-server  # the tracker kit provides tracker
```

`lado kits check` and `lado kits show` take the expected skills as there; `lado kits show`
says which kit provides each. A session in which no kit provides one, or whose `--without`
switches it off, does not start, and the error says why.

`expects.commands` names the external CLIs a kit cannot work without, each as PATH finds
it (`openspec`, `uv`; no path, spaces or arguments). LADO checks only that each is on the
agents' PATH, the one of your login shell that agents start with: not its version, nor
whether it is logged in or set up (the kit's own text checks that). `lado start`, a
resume and each new worker look again; when one is missing, nothing starts, and one error
names every missing command, its kit and the agents' PATH. A command that only some
projects of the kit need (a code host's CLI chosen by the project's settings) does not
belong there. `lado kits check` lists them (`expects commands: openspec`) and warns about
one that is not on its own PATH, since a kit is also checked where it does not run (a
marketplace's CI); `lado kits show` gives each one's place on the agents' PATH. LADO does
not check the commands of a kit's MCP servers yet: list one there too to have it checked.

Names are shared in a session: a flow of kit-b that calls `reviewer` then gets kit-a's.
A kit's supervisor is no role: `--without agent:<name>` that names one is read as
`agent:<name>@<its kit>` (so sessions of older LADOs resume as before); when several kits'
supervisors have that name, give the kit.

An agent of a kit lists its MCP servers (stdio only) in its frontmatter:

```yaml
mcp:
  db:
    command: ["${KIT_DIR}/bin/db-mcp", "--read-only"]
    env: {DB_TOKEN: "${DB_TOKEN}", MODE: ro}
```

`${KIT_DIR}` is the kit's folder. `${NAME}` in `env` is a variable of the agent's
environment (your login shell's, as a new terminal sees it): a missing one stops the agent's
start. Its value is never written to disk: the agent's CLI starts such a server through
LADO's wrapper (`lado.mcp_exec`), whose arguments name the variables only; the
wrapper takes the values from the environment the CLI passes on and starts the server.
`lado doctor` warns about config folders under `LADO_HOME/agents/` that no running agent
uses: an older LADO wrote such values there.

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

## License

MIT (placeholder; to be confirmed before the first release).
