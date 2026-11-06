The plan with each task's tests: `docs/superpowers/plans/2026-11-06-claude-model-server.md`.

## 1. Core

- [x] 1.1 `ServerEntry.root`, `agent_servers` for a CLI of one model per process (D1). Check:
  `tests/test_model_settings.py`.
- [x] 1.2 `reserved_model` and its refusal; `runs_on_server`, `server_model`, `min_context` of Claude
  Code; refusals moved to Codex (D1, D6, D7). Check: `tests/test_model_settings.py`.

## 2. Launch

- [x] 2.1 `SERVER_BLANKS` and the agent's settings, with and without a key or a context (D2-D4, D6).
  Check: `tests/test_providers.py`.
- [x] 2.2 A built-in launch unchanged. Check: `tests/test_providers.py`.
- [x] 2.3 No login: `needs_login`, `first_hook_blocker`, `keychain_login`, `check_login` (D5). Check:
  `tests/test_runtime.py`, `tests/test_providers.py`.

## 3. Start limit

- [ ] 3.1 `Provider.start_silence`, the reason by its limit, `heard_at_start` (D8). Check:
  `tests/test_liveness.py`, `tests/integration/test_session_loop.py` with `-m integration`.

## 4. End to end

- [ ] 4.1 A worker on another server and on a built-in model (D9). Check:
  `tests/integration/test_claude_model_server.py` with `-m integration`.
- [ ] 4.2 The canary with a Claude agent. Check: `tests/integration/test_session_model_canary.py` with
  `-m integration`.
- [ ] 4.3 `tests/fake_endpoint.py`'s Anthropic mode and the smoke tests on real Claude Code. Check:
  `make test-smoke PROVIDER=claude` in CI.

## 5. Docs and regression

- [ ] 5.1 `docs/install.md`, `docs/design/agents.md` with its wrong line, `docs/design/modules.md`,
  `docs/cli.md`, `CHANGELOG.md`. Check: read against the code.
- [ ] 5.2 `make lint`, `make test`, the changed tests with their markers, both `openspec validate`, the
  archive tried on a copy, green CI. Check: their exit statuses.
- [ ] 5.3 The manual check in the pull request's description. Check: the human runs it.
