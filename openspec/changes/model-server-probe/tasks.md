The plan with each task's tests: `docs/superpowers/plans/2026-11-02-model-server-probe.md`.

## 1. Core

- [ ] 1.1 `Provider.server_api` and the three API constants in `providers/base.py`; Claude
  Code, Codex and the OpenCode family declare theirs (D5). Check: `tests/test_providers.py`.
- [ ] 1.2 `tests/fake_model_server.py`: a fake model server in-process and as a script, with
  profiles (OpenAI-compatible, Ollama, LM Studio, Anthropic-compatible, Responses only,
  models only, unknown, key required, redirect, hanging, list failing) that records each
  request with its headers. Check: `tests/test_fake_model_server.py`.
- [ ] 1.3 `src/lado/model_servers.py`: the address (D2), the six requests with their
  limits and no redirect (D1, D3, D6), the type (D4), the rule (D5), the key's headers
  (D7), `Probe` and `ProbeError` with the texts of D8, the container's hint. Check:
  `tests/test_model_servers.py`.

## 2. Command

- [ ] 2.1 `lado model-server probe <address> [--key]` and `lado model-server` alone in
  `cli.py`: the output of D9, the key read as a secret and refused on the command line,
  exit codes 0, 1, 2 (D7, D9). Check: `tests/test_cli_model_server.py`.
- [ ] 2.2 Integration: the real `lado model-server probe` against the fake server in its
  own process; a canary key in no output, file of `LADO_HOME` or `lado.db`; an address
  that does not answer; the container's hint. Check:
  `uv run pytest -m integration -n auto tests/integration/test_model_server_probe.py`.

## 3. Docs and regression

- [ ] 3.1 `docs/cli.md` (the command, its output, its messages, the key),
  `docs/design/modules.md` (`model_servers.py`), AGENTS.md's Layout line, CHANGELOG's
  line under `## 0.45.0 (unreleased)`, `### Added`. Check: `tests/test_agents_md.py`,
  reading.
- [ ] 3.2 Regression and the trial archive: `make lint`, `make test`, the integration file
  with its marker; `openspec validate model-server-probe --strict`; in a copy of
  `openspec/` outside the tree `openspec archive model-server-probe --yes` and
  `openspec validate --specs --strict`, the result in the pull request's description.
  Check: the commands' exit codes.
