# LADO

**Layered Agent Delegation & Orchestration**

LADO runs teams of AI coding agents. Supervisors split work into tasks and hand them to specialist agents; the agents coordinate, and a human approves the key decisions. It is built for work that is too large for a single agent session.

> **Status: early development.** Nothing is ready to use yet. This repository reserves the name and will hold the first working version.

## The name

*Lado* is short for **L**ayered **A**gent **D**elegation & **O**rchestration.

In Russian, *лад* (lad) means harmony or being in tune, the way a well-run team works. The same root gives *наладить*: to set up, to get something working.

## Planned

- **Hierarchical delegation.** Supervisor agents break work down and assign it to worker agents.
- **Governed workflows.** Phases, gates, and human approval points are enforced by the system, not left to the agent's discretion.
- **Collaboration.** Agents pass tasks, messages, and artifacts to each other.
- **Provider-agnostic.** Use the CLI coding agents you already have.
- **Runs anywhere.** Works on a local machine, with a path to remote and cloud execution.

## Install

```bash
uv tool install lado    # or: pip install lado
lado doctor             # checks tmux and the agent CLIs (Claude Code, Kilo CLI)
```

There is nothing else to run yet; see [ROADMAP.md](ROADMAP.md).

## Kits

A kit is a team: agent roles, flows and skills, in a folder with a `kit.yaml`. It takes
skill packs from outside, pinned to a version, and may name the LADO it needs:

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
lado kits add https://github.com/<owner>/<kits>@v1.0.0   # or a local folder
lado start . --kit default --kit my-team
```

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

Names are shared in a session: a flow of kit-b that calls `reviewer` then gets kit-a's.
A kit's supervisor is no role: `--without agent:<name>` that names one is read as
`agent:<name>@<its kit>` (so sessions of older LADOs resume as before); when several kits'
supervisors have that name, give the kit.

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
