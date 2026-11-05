The plan with each task's tests: `docs/superpowers/plans/2026-11-05-worker-model.md`.

## 1. Core

- [ ] 1.1 The source `supervisor` and its words (D9). Check: `tests/test_state.py`.
- [ ] 1.2 `worker_start` and `_name_cli`: how a name finds its CLI, each refusal, a free name,
  `model=""` (D1-D4). Check: `tests/test_model_settings.py`.
- [ ] 1.3 `cli_models`: what `list_models` gives, no request to a server (D7). Check:
  `tests/test_model_settings.py`.

## 2. Spawn and tools

- [ ] 2.1 `runtime._worker_start`, `spawn_worker(model=…)`, the check at every spawn, the refusal's
  way out; `runs.spawn_worker` passes `model` on (D5, D6, D10). Check: `tests/test_runtime.py`,
  `tests/test_runs.py`.
- [ ] 2.2 The MCP tools `list_models` and `spawn_worker(model=…)`, the supervisor's text, the
  descriptions (D7, D8, D11). Check: `tests/test_mcp_server.py`.

## 3. End to end

- [ ] 3.1 The fake agent's command with a model; through `lado mcp`: a worker on a model, of another
  CLI, of a run; each refusal leaves nothing; a silent server within the probe's timeout. Check: `uv
  run pytest -m integration -n auto tests/integration/test_worker_model.py`.
- [ ] 3.2 The key canary with a worker on a keyed server. Check: `uv run pytest -m integration -n
  auto tests/integration/test_session_model_canary.py`.

## 4. Docs and the change

- [ ] 4.1 `docs/design/agents.md`, `docs/design/modules.md`, `docs/cli.md`, CHANGELOG's line under
  `## 0.45.0 (unreleased)`, `### New`. Check: `grep -n "local checks only" docs/design/agents.md`
  finds nothing, `make lint`.
- [ ] 4.2 The trial archive on a copy of `openspec/`, its result and the manual check in the pull
  request's description. Check: `openspec validate --specs --strict` on the copy.
