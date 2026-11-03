## 1. Test server

- [x] 1.1 `tests/fake_model_server.py`: answers by the `anthropic-version` header, the
  profiles `litellm` and `anthropic-versioned`, LM Studio's typed models with an
  embeddings model (D6). Check: `tests/test_fake_model_server.py`, the tests counting
  `lmstudio`'s models updated.

## 2. Probe

- [x] 2.1 `model_servers.py`: `anthropic-version` per request, the second `GET
  /v1/models` in the second wave (D1); `_kind` and `_models` by the plain list first (D2);
  the module docstring's request count. Check: `tests/test_model_servers.py` (requests and
  headers on each profile, LiteLLM `OpenAI-compatible`, the Anthropic list with the header,
  the old header test replaced).
- [x] 2.2 `Probe.embeddings` and the `(embeddings)` mark in `lines` (D3). Check:
  `tests/test_model_servers.py`.

## 3. Settings

- [x] 3.1 `model_settings._on_server`: the embeddings refusal before the list's verdict
  (D3). Check: `tests/test_model_settings.py`.
- [x] 3.2 `model_settings.same_address` and the `same address as model server` lines of
  `add_server`, the replaced server left out (D4). Check: `tests/test_model_settings.py`.
- [x] 3.3 `model_settings.remove_models` and the one-command hint of `remove_server` (D5).
  Check: `tests/test_model_settings.py`.

## 4. Commands

- [x] 4.1 `cli.py`: `lado model remove <name>…` (`nargs="+"`), the `same address` lines of
  `lado model-server add` on stdout before `Saved`/`Replaced` (D4, D5). Check:
  `tests/test_cli_model_server.py`, `tests/test_cli_model_settings.py`.

## 5. Integration

- [ ] 5.1 `tests/integration/test_model_server_probe.py`: `litellm` in its own process is
  `type: OpenAI-compatible`. `tests/integration/test_model_settings_process.py`: the
  embeddings model refused, the same address named, several models removed then their
  server; the key canary scans the new lines. Check: `uv run pytest -m integration -n auto
  tests/integration/test_model_server_probe.py tests/integration/test_model_settings_process.py`.

## 6. Docs and regression

- [ ] 6.1 `docs/cli.md` (the probe's requests and header, the type, the `(embeddings)` mark,
  the embeddings refusal, the same-address line, `lado model remove` with several names and
  the removal's hint); CHANGELOG.md: the lines **Find out what a model server is** and
  **Save model servers and models under names** under `## 0.45.0 (unreleased)`, `### New`,
  amended, `### Fixed` untouched. Check: reading against the spec.
- [ ] 6.2 Regression and the trial archive: `make lint`, `make test`, the integration files
  of 5.1 with their marker; `openspec validate model-settings-checks --strict`, `openspec
  validate --specs --strict`; in a copy of `openspec/` outside the tree `openspec archive
  model-settings-checks --yes` and `openspec validate --specs --strict`, the result in the
  PR's description.
- [ ] 6.3 The PR's manual check from its first version: branch, folder, `env | grep LADO_`
  and `unset`, own `LADO_HOME` and `LADO_TMUX_SOCKET`, steps on LM Studio
  (`10.73.10.235:1234`: the embeddings mark and refusal, a second name on the same
  address, several models removed, then the server) and on LiteLLM 1.105.1 (`probe`, `add
  --replace` of a saved one, `lado model-server list` and `lado doctor` showing
  `OpenAI-compatible`).
