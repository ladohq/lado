# Claude Code on a model server: Implementation Plan

**Goal:** a Claude agent whose model is on a server runs there with tools, MCP and hooks; nothing of
the human's Claude credentials reaches the server; the key is on no disk.

**Architecture:** the rules in `model_settings.py` (`agent_servers`, `_on_server`); the launch in
`providers/claude.py`; one neutral skip of the login check in `runtime.py`; a provider's start limit
in `providers/base.py` and `opencode_family.py`.

**Tech Stack:** Python 3.10+, pytest (`-n auto`, `-m integration`, `-m smoke`), `tests/fake_model_server.py`,
`tests/fake_endpoint.py`, the fake agent.

**Spec:** `openspec/changes/claude-model-server/` and `docs/superpowers/specs/2026-11-06-claude-model-server-design.md`.

## Global Constraints

- No new dependency. Past ~15 code files (tests aside): stop and ask. The estimate is 5.
- No schema change, no `web/` change, no MCP tool, no CLI option.
- No agent CLI's global config is written beyond `claude.edit_config`'s existing first run and trust.
- A Claude agent on a built-in model starts with the same argv, settings and environment: a test
  compares them.
- No secret in `settings.json`, `mcp.json`, `lado.db`, `loop.log`, a warning or a refusal.
- Nothing in code, docs, specs or the UI names the epic's steps; `docs/epics/` is not touched.
- Live tests of Claude Code only with the human's yes. Never a real cloud in a test.

## Review Focus

1. A credential reaching the server: each row in bold of the design doc's table. Test: tasks 2, 6.
2. A built-in Claude agent changed by accident. Test: task 2.
3. A login check still holding, or dropped for a built-in model. Test: task 3.
4. `heard_at_start` losing the reason now that it holds a number. Test: task 5.

## Tasks

### 1. The server of a one-model CLI (`model_settings.py`, `providers/base.py`)

`ServerEntry.root`; `agent_servers` for `external_whole_process` (D1); `Provider.reserved_model` and
its refusal in `_on_server` (D7); `ClaudeProvider.runs_on_server`, `server_model`, `min_context`.
Tests (unit, `tests/test_model_settings.py`): one entry with the start model; none on a built-in
model; limits and the context warning; a reserved name refused at saving and at a start, usable for
OpenCode; a server without the API refused; the refusals moved to Codex, with `_runs_on`'s order.

### 2. The launch (`providers/claude.py`)

`SERVER_BLANKS`, the settings of D2, D4, D6; the keyless helper; `Launch.env`.
Tests (unit, `tests/test_providers.py`): the whole `settings.json` for a server with a key, with no
key, with and without a context; no key in any written file; the root with no `/v1`; a built-in
launch equal to today's, argv, settings and env, compared with a fixed expected value.

### 3. No login (`providers/claude.py`, `runtime.py`)

D5. Tests (unit, `tests/test_runtime.py`, `tests/test_providers.py`): session, resume and worker on a
server not refused while not logged in, a built-in one refused; `_held_for_login` holds nothing;
`first_hook_blocker` records the first run; no keychain warning.

### 4. A worker (`runtime.py` if needed)

D9. Test (integration, `tests/integration/test_claude_model_server.py`, fake agent, `tests/fake_model_server.py`):
a supervisor on a server spawns a worker on another server and one on a built-in model; each
launch's environment and settings as the spec says; `list_models` has no `blocked` for Claude Code.

### 5. The start's limit (`providers/base.py`, `opencode_family.py`, `runtime.py`)

D8. Tests: unit in `tests/test_liveness.py` (limit by provider, the reason's number, `heard_at_start`),
`tests/test_providers.py` (`tuiWait` is still `TUI_WAIT`); integration `tests/integration/test_session_loop.py`:
a silent TUI ready after its report with the agent never `waiting`.

### 6. The canary (integration and smoke)

Integration: extend `tests/integration/test_session_model_canary.py` with a Claude agent on a server:
the key in no file under `LADO_HOME` but its key file, not in `lado.db`, output or `loop.log`.
Smoke (`tests/smoke/test_smoke.py`, PROVIDER=claude, CI): `tests/fake_endpoint.py` gets an Anthropic
mode that streams a scripted shell and MCP tool call and keeps every request's headers. Real Claude
Code on it, not logged in in one test; in another with a fake login file, `ANTHROPIC_API_KEY`, and
user settings with `apiKeyHelper`, `env.ANTHROPIC_AUTH_TOKEN` and another `ANTHROPIC_BASE_URL`: every
request carries the server's key alone, and names the model alone. Hooks, MCP and a message from
LADO work. Written so that no request can leave for a real host.

### 7. Docs

`docs/install.md` (Local models: Claude Code on a server, what `/model` shows, Enter and `s`, a worker
for another model, no login, context limit, what still goes out, Ollama, LM Studio and LiteLLM as
documented, not tested); `docs/design/agents.md` (the launch, the blanks, the facts checked by hand;
the line `A real turn has nothing unconfirmed` made true: a turn can leave a second line of one paste
unconfirmed, and the agent then shows `idle` until it goes in; the start's limit by provider);
`docs/design/modules.md`, `docs/cli.md`; the comment in `claude.py` naming the version checked;
`CHANGELOG.md` under `## 0.45.0 (unreleased)`.

### 8. Regression and the change

`make lint`; `make test`; the changed integration files with `-m integration`; `openspec validate
claude-model-server --strict`, `openspec validate --specs --strict`; the archive tried on a copy of
`openspec/` before the first review; grep `openspec/specs/` for `does not run on a model server`; green
CI, smoke on Claude included. The pull request holds the human's manual check from the start: the
branch, folder, `env | grep LADO_` and `unset`, own `LADO_HOME` and `LADO_TMUX_SOCKET`; `lado
model-server probe` on LM Studio and LiteLLM, then a real session of Claude Code with a tool, an MCP
call and `/model` on each; expected results for each.
