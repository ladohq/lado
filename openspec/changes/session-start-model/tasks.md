The plan with each task's tests: `docs/superpowers/plans/2026-11-05-session-start-model.md`.

## 1. Core

- [x] 1.1 `PowerRow` forms, tolerant `from_json`, `DEFAULT_MODEL`, `CLI_CHANGED`, `report_model`
  (D1, D2, D12). Check: `tests/test_state.py`.
- [x] 1.2 `start_model`, `session_row`, `check_start`, `agent_servers`, `shown`, names left out
  (D3, D4, D5, D7, D10, D13). Check: `tests/test_model_settings.py`.
- [x] 1.3 `runtime.start_session`, `spawn_worker`, `_changes`, `cli.py` help and warnings, refusals'
  tails, `list_agents`, `lado ls` (D3-D5, D11, D13). Check: `tests/test_runtime.py`,
  `tests/test_cli.py`, `tests/test_mcp_server.py`.
- [x] 1.4 `LADO_LAUNCH_VARS` (D16). Check: `tests/test_agent_env.py`; the test of the other CLI
  fails before and passes after: `uv run pytest -m integration -n0
  tests/integration/test_session_model.py::test_a_worker_of_another_cli_runs_its_default_and_says_so`.

## 2. Providers

- [x] 2.1 `runs_on_server`, `AgentSpec.servers`, `model_source`, `server_model`, `on_server`, the
  family's config, keys, `--model` (D6-D9). Check: `tests/test_providers.py`.
- [x] 2.2 Smoke of OpenCode and Kilo CLI on two fake servers, with `--agent plan`, and the first run
  in the container. Check: `tests/smoke/test_smoke.py` in CI.

## 3. End to end

- [x] 3.1 The start model's cases, all ticked models in each case, refusals, LADO's own resume,
  a silent other server. Check: `uv run pytest -m integration -n auto
  tests/integration/test_session_model.py tests/integration/test_session_model_server.py`.
- [x] 3.2 The key canary with a worker of another CLI. Check: `uv run pytest -m integration -n auto
  tests/integration/test_session_model_canary.py`.

## 4. API

- [x] 4.1 `session-model/check`, `NewSession`, `Resume`, `SessionInfo`, `ModelInfo` (D14);
  `make web-types`, both files committed. Check: `tests/test_server_launch.py`,
  `tests/test_server_agents.py`, `make web`.

## 5. UI

- [x] 5.1 `ModelPicker` in the window, `Launch.tsx`, new tab, "agent CLI" (D15, D17). Check:
  `web/src/ModelPicker.test.tsx`, `web/src/Launch.test.tsx`, `make web`.
- [x] 5.2 The agent's page (D13). Check: `web/src/Agents.test.tsx`.
- [x] 5.3 Settings' words, `lado doctor` (D18). Check: `web/src/ModelSettings.test.tsx`,
  `tests/test_doctor.py`.
- [x] 5.4 UI e2e of the field, refusals, Resume, the page at 390 px; a screenshot of each changed
  screen as a run artifact; the stand's script for design QA. Check: `uv run pytest -m ui
  tests/ui/test_launch_model.py`.

## 6. Docs

- [ ] 6.1 `docs/install.md` (local models, `host.docker.internal`), `docs/cli.md`,
  `docs/design/ui.md`, `docs/design/agents.md`, `docs/design/modules.md`; CHANGELOG under
  `## 0.45.0 (unreleased)`, `### New`. Check: read against the code; `tests/test_agents_md.py`.

## 7. Before review

- [ ] 7.1 The plan's regression run; `openspec validate session-start-model --strict`, `openspec
  validate --specs --strict`; a trial archive on a copy of `openspec/`, its result in the pull
  request, with the manual check's steps (LM Studio on localhost, an external LiteLLM, Docker).
