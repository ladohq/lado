The plan with each task's tests: `docs/superpowers/plans/2026-11-05-cli-default-model.md`.

## 1. Store

- [ ] 1.1 Schema 39, `ModelRef`, `cli_defaults`, `models.id`; `schema_before` (D1, D2). Check:
  `tests/test_state.py`, `make test`.

## 2. Rules and commands

- [ ] 2.1 `choices`, `set_default`, `set_default_ref`, `clear_default`, removals with cleared
  defaults, `external_whole_process`, `lado model default`, `lado model add` with `--server`;
  `docs/cli.md`, `docs/design/modules.md` (D3, D4, D5, D7, D12). Check:
  `tests/test_model_settings.py`, `tests/test_cli_model_settings.py`.

## 3. API

- [ ] 3.1 `model-choices`, `model-defaults`, `defaults` in `model-settings`; `make web-types`,
  both generated files committed (D6). Check: `tests/test_server_model_settings.py`; the canary
  and process tests with `-m integration`.

## 4. Page

- [ ] 4.1 `ModelPicker.tsx` to the mock-up (D9). Check: `web/src/ModelPicker.test.tsx`.
- [ ] 4.2 The cards, the CLI's sources gone, what is read when, order and folding (D8, D10, D12). Check:
  `web/src/ModelSettings.test.tsx`, `web/src/ModelSources.test.tsx`, `make web`.
- [ ] 4.3 Removing a default: the question, Undo, the server's question (D5, D11). Check: the same
  vitest files.

## 5. End to end and docs

- [ ] 5.1 UI e2e and integration. Check: `uv run pytest -m ui tests/ui/test_models_section.py`,
  `uv run pytest -m integration -n auto tests/integration/test_model_settings_process.py`.
- [ ] 5.2 `docs/design/ui.md`, `CHANGELOG.md`; the trial archive on a copy of `openspec/`, its
  result in the pull request. Check: `make lint`, `make test`, `openspec validate --specs
  --strict`.
