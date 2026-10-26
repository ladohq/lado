# LADO: notes for coding agents

LADO (Layered Agent Delegation & Orchestration) runs teams of AI coding agents.
Current stage and next steps: [ROADMAP.md](ROADMAP.md). This file is the project's map, at
most 200 lines (`tests/test_agents_md.py`); the details are in the documents of Read more.

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
make test               # unit tests (uv run pytest -n auto)
make test-integration   # uv run pytest -m integration -n auto: real tmux, git and processes, no LLM
make test-js            # node --test: the OpenCode-family plugin (Kilo, OpenCode)
make web                # the web UI: npm ci, stale-types check, tsc, vitest, build into src/lado/server/static
make web-types          # web/openapi.json and web/src/api.gen.ts from the server's API (commit both)
make test-ui            # uv run pytest -m ui: Chromium against a real lado server, fake agent
make dist               # uv build, and check that the sdist and the wheel ship the web UI
make check              # lint, the plugin, the web UI, then unit, integration and UI tests one after another
make test-live          # uv run pytest -m live: real agent CLIs and models; PROVIDER=claude|codex|kilo|opencode
make test-smoke         # uv run pytest -m smoke: real agent CLIs, a local endpoint instead of a model; PROVIDER=...
make docker             # LADO's image lado:local from the working copy: the web UI's bundle, one wheel, docker build
make test-container     # uv run pytest -m container -n0: the image with real Docker, no model (make docker first)
```

The web UI needs Node (npm) to build; users of the wheel do not. `make browser` (part of
`make check` and `make test-ui`) installs Playwright's Chromium.

Unit and integration tests run in parallel, one pytest-xdist worker per CPU; each test has
its own `LADO_HOME`, tmux server and repos, so tests must not share a fixed path, port or
file. To debug serially: `make test PYTEST_ARGS=-n0` (or `PYTEST_ARGS="-n0 -k gate -x"`).
One heavy test run per machine at a time: `make check`, `make test`, `make test-integration`
and `make test-ui` wait for a machine-wide lock (`scripts/check_lock.py`;
`LADO_CHECK_LOCK=0` runs without it). The rest of the test setup: docs/testing.md.

Try it locally: `uv run lado start <repo>` runs the working copy; use
`LADO_HOME=/tmp/some-dir` and `LADO_TMUX_SOCKET=lado-dev` to keep test sessions apart from
the LADO you work with. Every command's behaviour: [docs/cli.md](docs/cli.md).

## Layout

One line per module; each module's behaviour in detail: [docs/design/modules.md](docs/design/modules.md).

- `src/lado/`: the Python package.
  - `cli.py`: the `lado` command (`console.py` its console script, refusing native Windows).
  - `doctor.py`: `lado doctor`'s environment checks and the system facts of the UI.
  - `bug_report.py`: the bug report of `lado bug-report` and the UI; sends nothing.
  - `update.py`: PyPI's releases, the daily update check, the installer, the update result.
  - `self_update.py`: `lado update` (stop, back up, install, resume, roll back).
  - `uninstall.py`: `lado uninstall`.
  - `telemetry.py`: LADO's error journal and, with the human's yes, usage statistics.
  - `runtime.py`: sessions and agents in tmux, workers' worktrees, message delivery.
  - `clone.py`: a repository from its git URL (`lado start <git-url>`, the UI's clone).
  - `scratch.py`: a new or empty folder made a repository (`lado start --new`, From scratch).
  - `projects.py`: the workspace (`LADO_REPOS`, else `~/workspace`) and projects in it.
  - `providers/`: the agent CLIs behind one interface: `base.py`, `claude.py`, `codex.py`,
    `opencode_family.py` (with `opencode_plugin.js`), `kilo.py`, `opencode.py`, `gitpaths.py`.
  - `tmux.py`: tmux calls on LADO's private server (`tmux -L lado`).
  - `gui_session.py`: where a process runs on macOS (the keychain's graphical session).
  - `agent_env.py`: an agent's environment, from the user's login shell.
  - `interpreter.py`: `run_module`, the one way LADO starts a Python process of its own.
  - `mcp_exec.py`: a kit's MCP server whose secrets never go on disk.
  - `text.py`: the one rule of a line of visible text.
  - `terminal.py`: an agent's terminal for the UI.
  - `kits.py`: kits (roles, skills, MCP servers, flows), lookup, install, resolve; `builtin_kits/`.
  - `gitcache.py`: the git cache of kits and packs; all git commands for kits.
  - `marketplaces.py`: kit marketplaces.
  - `flows.py`: the flow format and its validator; `runs.py`: flow runs, steps, gates.
  - `mcp_server.py`: the MCP tools agents use (`lado mcp`).
  - `artifacts.py`: artifacts, a session's named documents; `artifacts_local.py` its store;
    `images.py` image sizes.
  - `hooks.py`: neutral hook logic: status, hand-over, the forgotten-reply check.
  - `state.py`: SQLite state in `~/.lado/lado.db`. A schema change: bump `SCHEMA_VERSION`,
    add a step to `MIGRATIONS` and update `tests/agent_helpers.previous_schema`.
  - `fingerprint.py`: a read-only agent's git fingerprint.
  - `log.py`: `lado log`; `stats.py`: `lado stats`.
  - `loop.py`: the session loop, `lado loop <session>`.
  - `server/`: the UI server (`lado server`, `lado ui`): `app.py`, `auth.py`, `feed.py`,
    `models.py`, `terminals.py`, `clones.py`, `launch.py`, `run.py`; `static/` the bundle.
- `web/`: the web UI (React, TypeScript, Vite). `openapi.json` and `src/api.gen.ts` are made
  by `make web-types` and committed.
- `tests/`: unit tests; `integration/` (fake agent), `ui/` (browser), `live/` (real CLIs),
  `smoke/` (real CLIs, no model), `container/` (the image), `js/` (the plugin);
  `agent_helpers.py`, `real_clis.py`, `fake_endpoint.py`, `leftovers.py` shared helpers.
- `scripts/`: the test-run lock and groups, CI's smoke and container cells, release checks,
  the secret field's font.
- `docker/`: LADO's image (`Dockerfile`, `compose.yaml`, entrypoint, profile).
- `npm/`: placeholder npm package that only reserves the name. Leave it alone.

## How agents talk

Agents talk only through LADO's MCP tools; status comes from hooks; messages go through
one queue per agent with confirmation and retries. The whole protocol, with each CLI's
facts checked by hand: [docs/design/agents.md](docs/design/agents.md). Read it before a
change of `runtime.py`, `hooks.py`, `loop.py`, `mcp_server.py`, `agent_env.py` or
`providers/`.

## Testing

Seven layers; each change gets tests at the lowest layer that can catch its bugs:

1. **Unit** (`make test`): pure logic, tmux replaced by a recorder. Default for everything.
2. **Integration** (`make test-integration`): real tmux, git, hooks, `lado mcp` and SQLite
   with the fake agent instead of an LLM. Required for behaviour that crosses processes.
3. **Plugin tests** (`make test-js`): provider plugins run under Node with a fake client.
4. **UI e2e** (`make test-ui`, marker `ui`): Chromium against a real `lado server`; only
   what needs a browser.
5. **Smoke** (`make test-smoke`, marker `smoke`): each real CLI, a local 401 endpoint
   instead of a model. Not in `make check`; in CI.
6. **Live e2e** (`make test-live`, marker `live`): real CLIs and models. Not in CI: at
   release; Claude Code only with the human's yes.
7. **Container** (`make test-container`, marker `container`): LADO's image with real
   Docker. Not in `make check`; in CI.

Isolation: tests use a temp `LADO_HOME` and their own tmux server
(`LADO_TMUX_SOCKET=lado-test-...`), never the default `lado` socket, and never the user's
agent configs; `tests/conftest.py` clears LADO's variables, switches the update check and
statistics off. Layers, fixtures, CI and the Windows probe in full: [docs/testing.md](docs/testing.md).

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
- **Share, don't copy.** Share skills through a kit's `dependencies.skills` (a pack pinned
  to a version), never by copying them; a kit without agents shares its packs with the
  whole session. Roles are not shared through dependencies: kits are combined in a session
  (`--kit a --kit b`). Adding a first agent to a kit without agents makes its packs
  private to it, and the other kits' agents lose them (loudly only when their `skills:`
  names one).
- **One lead, one rule.** If exactly one kit of a session has a supervisor (`supervisor:`
  in its kit.yaml), it leads; otherwise LADO's built-in supervisor leads with each kit
  supervisor's rules as a skill `lead-<kit>`, named loudly with the
  `--without agent:<name>@<kit>` that makes another the lead. A kit with skills or roles only never changes who leads; the order of the kits
  never matters.
- **No hardcoded paths.** Resources refer to each other by relative paths or `${KIT_DIR}` /
  `${SKILL_DIR}`, never by absolute or home-directory paths.
- **Never touch the user's global agent config.** Configure each agent process on its own.
- **Native over injected.** Use each CLI's own way of loading skills, MCP servers and hooks
  instead of pasting their text into the prompt.
- **Explicit lookup.** No hidden fallbacks to global locations; show where each resolved
  piece came from. Kits are looked up among the installed ones (lado.db), then built-in,
  never in a session's repository; a kit's packs come only from the addresses in its own
  `kit.yaml`.
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
- **Keep this file a map.** Add to it only what an agent needs in any task; behaviour goes
  to the documents of Read more or the module's docstring, true to the code in the same
  pull request.

Release and versions: every minor release is first a release candidate, and main is frozen
until the final (only fixes for the RC). Each change users see adds a line to CHANGELOG.md
under `## X.Y.Z (unreleased)`. Bump the minor for a feature, an MCP tool or CLI change or a
schema migration, the patch for fixes and docs only. The rest: [docs/release.md](docs/release.md).
Vulnerability reports: [SECURITY.md](SECURITY.md).

## Read more

- [docs/design/agents.md](docs/design/agents.md): how agents talk (environment, status,
  turns, messages, the session loop, read-only roles).
- [docs/design/modules.md](docs/design/modules.md): each module and folder in detail.
- [docs/testing.md](docs/testing.md): the test infrastructure, CI, the Windows probe and
  the test layers in full.
- [docs/cli.md](docs/cli.md): how the `lado` commands behave.
- [docs/design/ui.md](docs/design/ui.md): the web UI and its server.
- [docs/design/artifacts.md](docs/design/artifacts.md): artifacts.
- [docs/design/projects.md](docs/design/projects.md): projects and the workspace.
- [docs/release.md](docs/release.md): releases and what must be green before one.
- [openspec/specs/](openspec/specs/): the living specs of each capability.
