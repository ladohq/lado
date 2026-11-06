The plan with each task's tests: `docs/superpowers/plans/2026-11-06-external-model-provider.md`.

## 1. Limits

- [x] 1.1 `_listed_limits` reads the providers' fields (D1). Check: `tests/test_model_servers.py`.
- [x] 1.2 `Limit.output_room` for a large context (D2). Check: `tests/test_providers.py`.
- [x] 1.3 `is_local`, the warning on an unknown context, its peek (D3). Check:
  `tests/test_model_settings.py`, `tests/test_server_launch.py`.
- [x] 1.4 A start on a cloud-shaped list has `limit` in the config. Check:
  `tests/integration/test_local_model_limits.py` with `-m integration`.

## 2. Refusals

- [x] 2.1 `base.REFUSALS`, `refusal_line`, `without_keys`, `KEY_VARIABLE` moved (D5, D8). Check:
  `tests/test_providers.py`.
- [x] 2.2 The plugin's `status`; `turn_error` (D4). Check: `make test-js`, `tests/test_providers.py`.
- [x] 2.3 Claude's `parse_event`, never temporary (D4, D6). Check: `tests/test_providers.py`.
- [x] 2.4 `CLAUDE_CODE_MAX_RETRIES` (D7). Check: `tests/test_providers.py`.
- [x] 2.5 A refusal through the hooks, the chat's line, no resume, the key in no text. Check: a new
  `tests/integration/test_provider_refusals.py` with `-m integration`.

## 3. The probe

- [x] 3.1 A late POST asked again, `Probe.late`, `lines`, the warning (D9). Check:
  `tests/test_model_servers.py`.
- [x] 3.2 The refusal of `lado model add` and a start. Check: `tests/test_model_settings.py`,
  `tests/integration/test_model_server_probe.py` with `-m integration`.

## 4. The UI's line

- [x] 4.1 `LADO_DOWN` (D10). Check: `make web`.

## 5. Smoke

- [x] 5.1 The fake endpoint's status mode, 401 and 429 per CLI, the key echoed. Check: `-m smoke` of
  the new tests with the real CLIs here, then CI.

## 6. Documents

- [x] 6.1 `docs/install.md`: the cloud provider's section, F1's line and context, cost.
- [x] 6.2 `docs/design/agents.md`, `docs/design/modules.md`, `docs/design/ui.md`, `docs/testing.md`,
  `docs/cli.md`; CHANGELOG.md under 0.45.0.
- [x] 6.3 `make lint`, `make test`, `openspec validate --specs --strict`, the trial archive.

## 7. The human's check on a real provider

- [x] 7.1 Any 4xx but 408 is a refusal on all three CLIs, a 400 about the key a refused key, the
  context's words first (D12). Check: `tests/test_providers.py`, `-m smoke` with cloud.ru's 400.
- [x] 7.2 A Claude agent on a server asks for at most 16384 of output, with its window (D13). Check:
  `tests/test_providers.py`, `-m smoke` on a context of 131072, seen red at 32000.
- [x] 7.3 A Claude agent on a server names no effort (D14). Check: `tests/test_providers.py`,
  `-m smoke` with the user's `effortLevel`.
- [x] 7.4 Only a resume told counts (D15). Check: `tests/test_liveness.py`.
