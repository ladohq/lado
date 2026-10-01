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

## License

MIT (placeholder; to be confirmed before the first release).
