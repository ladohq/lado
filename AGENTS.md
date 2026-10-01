# LADO: notes for coding agents

LADO (Layered Agent Delegation & Orchestration) runs teams of AI coding agents.
Current stage and next steps: [ROADMAP.md](ROADMAP.md).

## Commands

```bash
uv sync                 # create .venv and install dev tools
uv run lado --version   # run the CLI from the working copy
uv run pytest           # tests
uv run ruff format      # format
uv run ruff check       # lint (add --fix to autofix)
```

CI runs `ruff format --check`, `ruff check` and `pytest` on Python 3.10 and 3.13.

Release: `uv version <X.Y.Z>`, commit, then push tag `vX.Y.Z`. The Release workflow checks the
tag against the package version and publishes to PyPI.

## Layout

- `src/lado/`: the Python package.
  - `cli.py`: the `lado` command. `doctor.py`: environment checks.
  - `runtime.py`: starts agents in tmux (worker = own git worktree and branch) and delivers
    messages to them.
  - `providers/`: agent CLIs behind one interface (`base.py`: `Provider`, `Capabilities`,
    neutral hook events; `claude.py`: Claude Code). A provider writes the agent's config,
    builds its command and translates its hook events.
  - `tmux.py`: tmux calls, on a private server (`tmux -L lado`).
  - `mcp_server.py`: MCP tools for agents (`spawn_worker`, `send_message`, `list_agents`).
  - `hooks.py`: neutral hook logic: agent status and handing over queued messages.
  - `state.py`: SQLite state in `~/.lado/lado.db` (`LADO_HOME` overrides the directory).
    Schema changes: bump `SCHEMA_VERSION` and add a step to `MIGRATIONS`.
- `tests/`: pytest tests.
- `npm/`: placeholder npm package that only reserves the name. Leave it alone.

## How agents talk

- An agent's status (busy / idle / waiting) comes from its hooks, never from screen scraping.
- A message to an idle agent is pasted into its window and counts as delivered only after
  the agent's prompt-submit hook sees it; otherwise it is queued again. A busy agent
  gets its queued messages from its turn-end hook when the turn ends.

## Try it locally

`uv run lado start <repo>` runs the working copy. Use `LADO_HOME=/tmp/some-dir` to keep test
sessions apart from the LADO you work with.

## Rules

- **Deliver fast.** Build only what the current roadmap stage needs.
- **Clean-room.** Ideas from other projects are welcome, but never copy their code, tests,
  prompt texts or file layout. Describe the behavior in your own words first, then write
  the implementation from scratch.
- **Tasks and bugs** go to the external task tracker, not to GitHub Issues.
- Python 3.10+. Standard library first; add a dependency only when it clearly saves work.
