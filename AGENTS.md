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
make test-live          # uv run pytest -m live: real agent CLIs and models; PROVIDER=kilo|claude
```

Integration tests (`tests/integration/`) run a fake agent (`fake_agent.py`, provider "fake")
instead of a real agent CLI. They use a temp `LADO_HOME` and their own tmux server
(`LADO_TMUX_SOCKET=lado-test-...`), and refuse to run otherwise. Tests never use the default
`lado` tmux socket.

Live tests (`tests/live/`) run the real CLIs with the same isolation; a test skips when its CLI
is missing or not logged in. Models: Claude Code on `haiku`, Kilo on `kilo/kilo-auto/free`
(override with `LADO_LIVE_CLAUDE_MODEL` / `LADO_LIVE_KILO_MODEL`). The Claude test uses a fixed
repo path and answers Claude Code's workspace trust dialog, so Claude Code records one trusted
folder for it.

CI runs `ruff format --check`, `ruff check`, the unit and integration tests on Python 3.10 and
3.13, and the Node tests.
Live tests are not in CI: run them locally.

Release: `uv version <X.Y.Z>`, commit, then push tag `vX.Y.Z`. The Release workflow checks the
tag against the package version and publishes to PyPI.

Versions (0.x): bump the minor (0.7.0) for new features, an MCP tool or CLI change that older
agents cannot use, or a database schema migration; running sessions must be restarted after
such an upgrade. Bump the patch (0.7.1) for fixes and docs only: no new feature, no API or
schema change.

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
  - `sources.py`: kit sources (`lado sources`): a local folder read in place, or a git
    repository cloned into `LADO_HOME/sources/<name>`; registered in `LADO_HOME/sources.yaml`.
    Only the `Source` classes know a kind; `kits.py` asks a source for its directory.
  - `mcp_server.py`: MCP tools for agents (`send_message`, `read_messages`, `list_agents`;
    the supervisor also gets `spawn_worker` and `finish_worker`).
  - `hooks.py`: neutral hook logic: agent status and handing over queued messages.
  - `state.py`: SQLite state in `~/.lado/lado.db` (`LADO_HOME` overrides the directory).
    Schema changes: bump `SCHEMA_VERSION` and add a step to `MIGRATIONS`. The `events`
    table records what each agent did (`spawned`, `status` changes via `set_status`,
    `finished`); events and messages go with their session. How long an agent has had its
    status (`lado ls`, `list_agents`) comes from its latest `status` or `spawned` event.
  - `log.py`: `lado log`: a session's messages and events merged into one time-ordered feed.
- `tests/`: pytest tests; `tests/integration/`: integration tests with a fake agent;
  `tests/live/`: live tests with real agent CLIs; `tests/js/`: Node tests of the Kilo plugin.
  `tests/agent_helpers.py`: isolation guard and polling shared by integration and live tests.
- `npm/`: placeholder npm package that only reserves the name. Leave it alone.

## How agents talk

- An agent's status (busy / idle / waiting) comes from its hooks, never from screen scraping.
- A message is a one-line `summary` (at most 200 characters; a longer or multi-line one is
  refused) and an optional `body` with the details. Only one short line per message reaches
  the recipient: `[from <sender>] <summary>`, plus ` (#<id>, <n> lines: call read_messages)`
  when there is a body. `read_messages` returns the caller's delivered, unread bodies and
  marks them `read`. The supervisor's window is also the human's chat, so it stays quiet:
  the supervisor does not relay reports, and the details are in `lado log`.
- A message to an idle agent is pasted into its window and counts as delivered only after
  the agent's prompt-submit hook sees its line; otherwise it is queued again. A busy agent
  gets its queued messages from its turn-end hook when the turn ends.
- Agents talk only through LADO's MCP tools. A CLI's own agent messaging is switched off
  (Claude Code: `SendMessage` and `ListAgents` are denied in the agent's settings, and the
  `lado` MCP server has `alwaysLoad`, so its tools are not hidden behind tool search), and so
  is self-updating (Kilo: `autoupdate: false` and `KILO_DISABLE_AUTOUPDATE=1`).

## Try it locally

`uv run lado start <repo>` runs the working copy. Use `LADO_HOME=/tmp/some-dir` and
`LADO_TMUX_SOCKET=lado-dev` to keep test sessions apart from the LADO you work with.

`lado log <session>` shows what happened in a session: messages between agents (one line
with their delivery state and summary, the body indented below) and agent events (spawned,
status changes). `--agent NAME` keeps one agent's
lines, `-n N` the last N entries, `--follow` keeps printing new ones until Ctrl-C.
With `--follow` a message is printed once, with the state it had then; a later delivery
is not printed again.

`lado finish <session> <agent>` ends a worker whose branch is merged into the session repo's
current branch: it closes the window, removes the worktree and branch, and drops the agent
from `lado ls` (its messages and events stay in `lado log`, with a `finished` event). It
refuses an unmerged branch or uncommitted changes; `--discard` ends the worker anyway and
throws that work away. The supervisor does the same with the MCP tool `finish_worker`.

## Testing

Four layers; each change gets tests at the lowest layer that can catch its bugs:

1. **Unit** (`make test`): pure logic, tmux replaced by a recorder. Default for everything.
2. **Integration** (`make test-integration`): real tmux, git, hooks, `lado mcp` and SQLite
   with the fake agent instead of an LLM. Required for behaviour that crosses processes.
3. **Plugin tests** (`make test-js`): provider plugins run under Node with a fake client.
4. **Live e2e** (`make test-live`, marker `live`): real agent CLIs and real models, one short
   scenario per provider: a worker commits a file, reports to the supervisor and gets a
   message; then the session stops and no process is left. Never in the default run and
   not in CI: run it locally after changing a provider or before a release.

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
