The plan with each task's tests: `docs/superpowers/plans/2026-11-07-codex-model-server.md`.

## 1. Who can use a server

- [x] 1.1 `Provider.refuses_server`, `base.LM_STUDIO`, `suiting(apis, kind)` and its callers, the
  `not:` line (D6). Check: `tests/test_model_servers.py`, `tests/test_cli_model_server.py`.
- [x] 1.2 `lado model add`, `check_launch`, `blocked`; `runs_on_server` and its refusal gone (D6).
  Check: `tests/test_model_settings.py`, `tests/test_cli_model_settings.py`, `tests/test_providers.py`.
- [x] 1.3 `ProbeInfo.cli_notes`, `Found`, `make web-types` (D7). Check: `make web`,
  `tests/test_server_model_settings.py`, a test in `web/src/`.

## 2. The launch

- [x] 2.1 The provider entry, the model and the provider in a profile, the key in the environment,
  `launched_on` (D1). Check: `tests/test_codex.py`.
- [x] 2.2 `needs_login`, `first_hook_blocker` on a server (D2). Check: `tests/test_codex.py`.
- [x] 2.3 Web search, the carried effort (D3). Check: `tests/test_codex.py`.
- [x] 2.4 The catalogue, its warning (D4). Check: `tests/test_codex.py`.
- [x] 2.5 The context (D5). Check: `tests/test_codex.py`.
- [x] 2.6 A start and a worker on a server through the fake agent, the key in no file. Check: a new
  `tests/integration/test_codex_model_server.py` with `-m integration`.

## 3. A failed turn

- [x] 3.1 `without_keys(text, keys)` (D10). Check: `tests/test_providers.py`.
- [x] 3.2 Reading the error, each row of D9's table (D9). Check: `tests/test_codex.py`.
- [x] 3.3 `failed_turn`: the offset, a line in writing, a later turn, a built-in agent (D8). Check:
  `tests/test_codex.py`.
- [x] 3.4 `runtime.check_turns`, the loop's pass, `hooks.handle` (D8). Check: `tests/test_runtime.py`.
- [x] 3.5 The line in the chat, idle, no resume, once after a loop's restart, the key echoed. Check:
  `tests/integration/test_codex_model_server.py` with `-m integration`.

## 4. Smoke

- [x] 4.1 A Responses stream in `tests/fake_endpoint.py`: a shell call, an MCP call, usage. Check:
  its unit test.
- [x] 4.2 Real Codex on it: tools, a turn, the catalogue taken, a compaction. Check: `-m smoke` of the
  new tests with the real CLI here, then CI.
- [x] 4.3 Real Codex on 401 and 429, the key echoed, the journal's format held. Check: the same.

## 5. Documents

- [x] 5.1 `docs/install.md`: Codex on a server, what was checked, what Codex cannot do, the line that a
  model can fail with no error. Check: read against D1-D11.
- [x] 5.2 `docs/cli.md`, `docs/design/agents.md`, `docs/design/ui.md`, `docs/design/modules.md`,
  `docs/testing.md`, `BACKLOG.md`'s entry (it now holds for a built-in model only). Check: grep for
  `does not run on a model server` and `no session of theirs starts`.
- [x] 5.3 CHANGELOG.md under `## 0.45.0 (unreleased)`. Check: docs/release.md's rules by hand.

## 6. The end

- [x] 6.1 `make lint`, `make test`, `make web`, the changed tests with their markers,
  `openspec validate codex-model-server --strict`, `openspec validate --specs --strict`, a trial
  archive in a copy, before the first review.
- [x] 6.2 At archive, the new capability's Purpose replaces the placeholder `openspec archive` writes,
  or `openspec validate --specs --strict` fails: `A Codex agent whose model is on a model server runs
  there with its tools, MCP servers and hooks, and nothing of the human's Codex login reaches that
  server.` The trial archive puts the same text in its copy. Check: the trial archive passes.
