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

The Makefile wraps these (`make help` lists the targets):

```bash
make lint               # ruff format --check + ruff check
make fmt                # ruff format + ruff check --fix
make test               # unit tests (uv run pytest)
make test-integration   # uv run pytest -m integration: real tmux, git and processes, no LLM
make test-js            # node --test: the Kilo plugin
make check              # lint and all three test suites; run before a release
```

Integration tests (`tests/integration/`) run a fake agent (`fake_agent.py`, provider "fake")
instead of a real agent CLI. They use a temp `LADO_HOME` and their own tmux server
(`LADO_TMUX_SOCKET=lado-test-...`), and refuse to run otherwise. Tests never use the default
`lado` tmux socket.

CI runs `ruff format --check`, `ruff check`, the unit and integration tests on Python 3.10 and
3.13, and the Node tests.

Release: `uv version <X.Y.Z>`, commit, then push tag `vX.Y.Z`. The Release workflow checks the
tag against the package version and publishes to PyPI.

## Layout

- `src/lado/`: the Python package.
  - `cli.py`: the `lado` command. `doctor.py`: environment checks.
  - `runtime.py`: starts agents in tmux (worker = own git worktree and branch) and delivers
    messages to them.
  - `providers/`: agent CLIs behind one interface (`base.py`: `Provider`, `Capabilities`,
    `Launch`, neutral hook events; `claude.py`: Claude Code; `kilo.py`: Kilo CLI, with
    `kilo_plugin.js`, the Kilo plugin that runs LADO's hooks). A provider writes the agent's
    config, returns its argv and env and translates its hook events. The provider is chosen
    per session (`lado start --provider`) and per worker (`spawn_worker(provider=...)`).
  - `tmux.py`: tmux calls, on a private server (`tmux -L lado`; `LADO_TMUX_SOCKET` overrides
    the socket name and is passed on to agents).
  - `kits.py`: kits (agent roles, skills, MCP servers): lookup, `include`, `--without`,
    validation. A provider gets an `AgentSpec` (prompt, skill folders, MCP servers), never
    the kit itself. `builtin_kits/`: kits shipped with LADO (`default`: supervisor + worker).
    LADO's own instructions to agents stay in `runtime.py` and are appended to the role.
  - `mcp_server.py`: MCP tools for agents (`spawn_worker`, `send_message`, `list_agents`).
  - `hooks.py`: neutral hook logic: agent status and handing over queued messages.
  - `state.py`: SQLite state in `~/.lado/lado.db` (`LADO_HOME` overrides the directory).
    Schema changes: bump `SCHEMA_VERSION` and add a step to `MIGRATIONS`.
- `tests/`: pytest tests; `tests/integration/`: integration tests with a fake agent;
  `tests/js/`: Node tests of the Kilo plugin.
- `npm/`: placeholder npm package that only reserves the name. Leave it alone.

## How agents talk

- An agent's status (busy / idle / waiting) comes from its hooks, never from screen scraping.
- A message to an idle agent is pasted into its window and counts as delivered only after
  the agent's prompt-submit hook sees it; otherwise it is queued again. A busy agent
  gets its queued messages from its turn-end hook when the turn ends.

## Try it locally

`uv run lado start <repo>` runs the working copy. Use `LADO_HOME=/tmp/some-dir` and
`LADO_TMUX_SOCKET=lado-dev` to keep test sessions apart from the LADO you work with.

## Testing

Four layers; each change gets tests at the lowest layer that can catch its bugs:

1. **Unit** (`make test`): pure logic, tmux replaced by a recorder. Default for everything.
2. **Integration** (`make test-integration`): real tmux, git, hooks, `lado mcp` and SQLite
   with the fake agent instead of an LLM. Required for behaviour that crosses processes.
3. **Plugin tests** (`make test-js`): provider plugins run under Node with a fake client.
4. **Live e2e** (`make test-live`, marker `live`): real agent CLIs and real models, one short
   scenario per provider. Never in the default run. Kilo runs nightly in CI on free models;
   Claude Code runs locally. Run it after changing a provider or before a release.

Before a release: `make check` and `make test-live` pass.

## Design principles

LADO borrows ideas from other orchestrators but must not repeat their mistakes:

- **Events, not screens.** Agent status comes from hooks, plugins or a protocol, never from
  reading the terminal.
- **Neutral core.** Nothing above `providers/` depends on one agent CLI. A new feature works
  with at least two providers or says clearly where it does not.
- **No silent drops.** If a kit, role or option asks for something a provider cannot do,
  fail or warn loudly. Never ignore it quietly.
- **One source of truth.** Derive what exists from the files themselves; do not keep a
  second list of the same things that can drift.
- **Share, don't copy.** Reuse a skill or role through `include`, never by copying it.
- **No hardcoded paths.** Resources refer to each other by relative paths or `${KIT_DIR}` /
  `${SKILL_DIR}`, never by absolute or home-directory paths.
- **Never touch the user's global agent config.** Configure each agent process on its own.
- **Native over injected.** Use each CLI's own way of loading skills, MCP servers and hooks
  instead of pasting their text into the prompt.
- **Explicit lookup.** No hidden fallbacks to global locations; show where each resolved
  piece came from.
- **Only what is used.** Add a field, option or engine feature when a real kit needs it.
- **Tested end to end.** Behaviour that crosses processes (tmux, hooks, MCP) gets an
  integration test with the fake agent.

## Rules

- **Deliver fast.** Build only what the current roadmap stage needs.
- **Clean-room.** Ideas from other projects are welcome, but never copy their code, tests,
  prompt texts or file layout. Describe the behavior in your own words first, then write
  the implementation from scratch.
- **Tasks and bugs** go to the external task tracker, not to GitHub Issues.
- Python 3.10+. Standard library first; add a dependency only when it clearly saves work.
