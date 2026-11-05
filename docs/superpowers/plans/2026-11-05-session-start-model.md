# A session on a model reference: Implementation Plan

**Goal:** an agent starts on the session's model, else its CLI's default, else as before; OpenCode
and Kilo CLI keep every ticked external model beside their own; loud checks before a start.

**Architecture:** row forms in `state.py`; the rules in `model_settings.py`; `runtime.py` calls
them; `providers/` put servers into the agent; thin API in `server/`; `ModelPicker` in the window.

**Tech Stack:** Python 3.10+, FastAPI and pydantic, React + TypeScript (Vite, vitest), Playwright,
pytest (`-n auto`, `-m integration`, `-m ui`), `tests/fake_model_server.py`.

**Spec:** `openspec/changes/session-start-model/` and
`docs/superpowers/specs/2026-11-05-session-start-model-design.md`; mock-up: run artifact
`mockup-session-model.html`, then `ui-design/model-picker` and `ui-design/launch-model`.

## Global Constraints

- No new Python or npm dependency. Past ~25 code files (tests and generated files aside): stop and
  ask whether it is still this task.
- The server check uses the probe's timeout; no new wait. No agent CLI's global config is touched.
- Nothing in code, docs, specs or the UI names the epic's steps or `docs/epics/`; `docs/epics/` is
  not touched.
- UI texts exact as in the delta; every refusal is the core's. The key canary stays green.

## Review Focus

1. A key in anything but the launch's environment: `repr` of `AgentSpec`, a warning, a refusal, a
   log line, the feed. Test: task 7.
2. `--model ''` against no `--model` through CLI, API and window, new and resumed. Test: tasks 3, 9.
3. A default that changes between a check and a launch, and a worker of another CLI. Test: task 6.
4. A model id with a slash through `on_server` and `shown`. Test: task 4.
5. A stale check answer after the agent CLI changed in the window. Test: task 9.

## Tasks

### Task 1: rows and sources (D1, D2, D12)

Files: `src/lado/state.py`. Tests, `tests/test_state.py`: each row form round trip; a row of two
keys reads as built-in; an unknown key; a missing key; a row no object; a top level no object; no
JSON; `report_model` gives `cli-changed`, keeps a first report and a `same` name; `source_words`.

### Task 2: the rules (D3-D5, D7, D10, D13)

Files: `src/lado/model_settings.py`, `src/lado/model_servers.py` (the base URL). Tests,
`tests/test_model_settings.py`: the order of `start_model` for row, settings, default, none, another
CLI's table, gone, unreadable; `session_row` for `''`, a built-in, an external, another CLI's;
`check_start` per verdict with no request where none is due; `agent_servers` grouping, no key, an
unreadable key, `{env:` and `{file:` left out; `shown` with an entry, without, a removed server.

### Task 3: runtime and CLI (D3-D5, D11, D13)

Files: `src/lado/runtime.py`, `cli.py`, `mcp_server.py`. Tests, `tests/test_runtime.py`,
`tests/test_cli.py`, `tests/test_mcp_server.py`: every scenario of the delta that needs no process:
resume words, the refusals' tails, the provider's change, `lado ls`, `list_agents`.

### Task 4: providers (D6-D9)

Files: `src/lado/providers/base.py`, `opencode_family.py`. Tests, `tests/test_providers.py`:
config per server, key-less server, label, saved name, `model` and `--model` together, none without
a model, `--prompt` kept, `on_server` with a slash, Claude and Codex take nothing, `repr` holds no
key.

### Task 5: inherit mode (D16)

Files: `src/lado/agent_env.py`, `runtime.py`. Tests: `tests/test_agent_env.py`; the integration test
of the other CLI, changed to assert after the worker's first hook, red before and green after.

### Task 6: end to end

Tests, `tests/integration/test_session_model.py`, new `test_session_model_server.py`: built-in,
external and nothing chosen each with all ticked models in the config; a default; a default changed
before a resume; `--model ''` past a default; a refusal stores nothing; LADO's own resume stays
stopped with the reason; a silent other server; a worker of another CLI on its default; a report of
`lado-<id>/<model>` becomes `changed in the agent CLI` with the saved name.

### Task 7: the canary

Tests, new `tests/integration/test_session_model_canary.py`: the key's value in no file under
`LADO_HOME` but its key file, nor in `lado.db`, output, logs, the error journal, API answers, a worker
of another CLI; present in the agent's environment.

### Task 8: API (D14)

Files: `src/lado/server/app.py`, `launch.py`, `models.py`, `model_entries.py`; `make web-types`.
Tests: `tests/test_server_launch.py`, `tests/test_server_agents.py`.

### Task 9: the window (D15, D17)

Files: `web/src/ModelPicker.tsx`, `Launch.tsx`, `api.ts`, `styles.css`. Tests:
`web/src/ModelPicker.test.tsx`, `web/src/Launch.test.tsx` (`findByRole` for the list): the sending
table of D15, notes, refusals, a stale answer, Resume, focus after a new tab.

### Task 10: the agent's page, Settings, doctor (D13, D18)

Files: `web/src/Agents.tsx`, `ModelSettings.tsx`, `src/lado/doctor.py`. Tests:
`web/src/Agents.test.tsx`, `web/src/ModelSettings.test.tsx`, `tests/test_doctor.py`.

### Task 11: smoke and UI e2e

Tests: `tests/smoke/test_smoke.py` (OpenCode and Kilo CLI on two fake servers, a request per server
with its key, `--agent plan`, the first run in the container); `tests/ui/test_launch_model.py` (the
field, refusals, Resume, the agent's page, 390 px). A screenshot of each changed screen as a run
artifact. The stand's script for design QA goes with the build report.

### Task 12: docs and regression

`docs/install.md`, `docs/cli.md`, `docs/design/ui.md`, `docs/design/agents.md`,
`docs/design/modules.md`, CHANGELOG. Regression run: `make lint`, `make test`, `make web`, `make
test-js` when the plugin changed, each changed test file with its marker, `openspec validate
session-start-model --strict`, `openspec validate --specs --strict`, a trial archive on a copy of
`openspec/`. The pull request carries the manual check from the start: branch, folder, commands,
what to expect, `env | grep LADO_` and `unset`, own `LADO_HOME` and `LADO_TMUX_SOCKET`, `make web`.
