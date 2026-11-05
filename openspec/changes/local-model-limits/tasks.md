The plan with each task's tests: `docs/superpowers/plans/2026-11-05-local-model-limits.md`.

## 1. First, the risk

- [x] 1.1 Prove `client.session.abort` ends OpenCode's overflow loop in the TUI, by hand, on a fake of a
  small context (D6). Check: the requests stop, `session.idle` comes. Failing: report `redesign`.

## 2. Limits

- [ ] 2.1 `model_servers.context_limits`, `Limit` (D1). Check: `tests/test_model_servers.py`.
- [ ] 2.2 `ServerEntry.limits`, `agent_servers` reads the servers at once (D2). Check:
  `tests/test_model_settings.py`.
- [ ] 2.3 `server_provider` writes `limit`, the rule of `output` (D3). Check: `tests/test_providers.py`.
- [ ] 2.4 `Provider.min_context`, `context_warning`, the window (D4, D5). Check:
  `tests/test_model_settings.py`, `tests/test_server_model_settings.py`.

## 3. Honest ends

- [x] 3.1 The plugin's stop (D6, D7). Check: `make test-js`.
- [ ] 3.2 No reply check on a failed turn (D8). Check: `tests/test_runtime.py`.

## 4. Start

- [ ] 4.1 npm's switches (D9). Check: `tests/test_providers.py`.
- [ ] 4.2 `kv.json` (D10). Check: `tests/test_providers.py`.

## 5. The flake

- [ ] 5.1 LAD-210's cause and fix (D11). Check: `web/src/ModelCards.test.tsx` under load, 50 runs.

## 6. End to end

- [ ] 6.1 A start on a small model warns, and a failed turn has no mark, through the fake agent. Check:
  `uv run pytest -m integration -n auto tests/integration/test_local_model_limits.py`.
- [ ] 6.2 The key canary with the limits' read. Check: `uv run pytest -m integration -n auto
  tests/integration/test_session_model_canary.py`.
- [ ] 6.3 Smoke: both real CLIs take a config with `limit`. Check: `tests/smoke/`, in CI.

## 7. Docs and the change

- [ ] 7.1 `docs/install.md`, `docs/design/agents.md`, `docs/design/ui.md`, `docs/design/modules.md`,
  CHANGELOG under `## 0.45.0 (unreleased)`. Check: `grep -n "32K" docs/install.md`.
- [ ] 7.2 The purpose of the new specs; a trial archive on a copy, its result in the pull request. Check:
  `openspec validate --specs --strict`.
- [ ] 7.3 The pull request's manual check, with the human's list of the plan. Check: it is in the
  description from the start.
