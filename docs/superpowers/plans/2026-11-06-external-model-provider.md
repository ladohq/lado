# An external model provider: Implementation Plan

**Goal:** agents on a cloud provider know their limits, a refusal reads in LADO's words and ends the
turn, no repeat goes on without end, and the key is in no text of LADO's.

**Architecture:** reading in `model_servers.py`; the rule of the output and the table of refusals in
`providers/base.py`; each CLI's status in `providers/claude.py`, `opencode_family.py` and the plugin;
the warning in `model_settings.py`, its words in `server/model_entries.py`.

**Tech Stack:** Python 3.10+, pytest (`-n auto`, `-m integration`, `-m smoke`), Node's test runner for
the plugin, `tests/fake_model_server.py`, `tests/fake_endpoint.py`, the fake agent.

**Spec:** `openspec/changes/external-model-provider/` and
`docs/superpowers/specs/2026-11-06-external-model-provider-design.md`.

## Global Constraints

- No new dependency. Past ~15 code files (tests aside): stop and ask. The estimate is 8.
- No schema change, no API field, no MCP tool, no CLI option, no new screen.
- Local servers and agents with no external model work as today: a test holds each of them.
- No key in a config, `lado.db`, output, log or error text.
- Tests never reach a real provider. A real request costs the human's money: only with their yes.
- Live tests of Claude Code only with the human's yes.
- Nothing in code, docs, specs or the UI names the epic's steps; `docs/epics/` is not touched.

## Review Focus

1. A key that survives in a line, a body, an event or a log, also cut in two. Test: tasks 2, 5.
2. A built-in Claude agent changed by accident. Test: task 2.
3. A local server warned about, or its limits changed. Test: task 1.
4. A refusal read as temporary, or a temporary error read as a refusal. Test: task 2.

## Tests by requirement

| Requirement | Layer | Tests |
|---|---|---|
| LADO reads a model's context from its server | unit | `tests/test_model_servers.py`: each scenario |
| A known context goes to the agent's config / to a Claude agent | unit, integration | `tests/test_providers.py`; `test_local_model_limits.py` on a cloud-shaped list |
| A start on a public server with no known context is warned about | unit, integration | `tests/test_model_settings.py`, `tests/test_server_launch.py`; a start |
| A provider's refusal reads in LADO's words | unit, JS, integration | `tests/test_providers.py`, `tests/js/`, `test_provider_refusals.py` |
| A Claude agent's refusal is read from its last message | unit | `tests/test_providers.py`, the three forms and a built-in agent |
| A refusal is never a temporary error | unit, integration | `tests/test_providers.py`; no `resume_at` after a 402 |
| No repeat without end on a refusal | smoke | `tests/smoke/test_smoke.py`, 401 and 429 per CLI, with `Retry-After: 1` |
| A server's key is in no error | unit, integration, smoke | a key at the cut; canary in `test_provider_refusals.py`; the fake echoes it per CLI |
| A Claude agent on a server repeats within a limit | unit, smoke | `tests/test_providers.py`; the count of requests |
| A late answer is not a missing API | unit, integration | `tests/test_model_servers.py`; `test_model_server_probe.py` on a fake that holds a POST |
| A request LADO's server did not answer promises nothing | web unit | `web/src/ModelCards.test.tsx` by the constant |

Regression run: `make lint`, `make test`, the changed files under `tests/integration/` with
`-m integration`, `make test-js`, `make web`, `openspec validate --specs --strict`, the trial archive;
the smoke tests of this change here, the rest in CI.

## Tasks

### 1. Limits (`model_servers.py`, `providers/base.py`, `model_settings.py`, `server/model_entries.py`)

D1, D2, D3. Write the failing unit tests from the scenarios, then the reading, `output_room`,
`is_local` and the warning. Then a start on a cloud-shaped list in `test_local_model_limits.py`.
The existing test that a model of unknown context says nothing stays, on a local address.

### 2. Refusals (`providers/base.py`, `claude.py`, `opencode_family.py`, `opencode_plugin.js`)

D4-D8. `KEY_VARIABLE` moves first. Unit tests of `refusal_line` and `without_keys`; the plugin's test
of `status`; `turn_error`; Claude's three forms, a form unknown, a built-in agent with the same event
as today, `transient` false for a 402 of kind `unknown` and true for `server_error`;
`CLAUDE_CODE_MAX_RETRIES` in the settings and in no built-in launch. Then
`tests/integration/test_provider_refusals.py`: a fake agent's failed turn through the real hooks, the
line in the chat, the body, no resume, the canary over `lado.db` and the logs. Confirm there that
`base.MODEL_SERVER` reaches Claude's hook; if it does not, D4's other way.

### 3. The probe (`model_servers.py`, `model_settings.py`)

D9. The fake holds one POST past the ceiling, then answers; then always. Unit tests with short
ceilings, an integration test through `lado model-server probe` and `lado model add`.

### 4. The UI's line (`web/src/api.ts`, `docs/design/ui.md`)

D10. `make web`. A screenshot of the line for the design QA.

### 5. Smoke (`tests/fake_endpoint.py`, `tests/smoke/test_smoke.py`)

D11. A status mode with a body and `Retry-After: 1`; per CLI on 401 and 429: the turn ends, the agent
is idle, the count stops growing, the line is LADO's, and the key the fake echoes is in no text.
Run them here on the real CLIs, then CI.

### 6. Documents

`docs/install.md` by the design doc; `docs/design/agents.md` (refusals, the status, the key, the
repeats, the facts of the table above), `docs/design/modules.md`, `docs/design/ui.md`, `docs/testing.md`
(the fake's mode), `docs/cli.md` (the `not:` line). One CHANGELOG line under `## 0.45.0 (unreleased)`
in `### New`: **Run agents on a cloud provider.** The manual check goes into the pull request's first
description, with the design doc's steps.
