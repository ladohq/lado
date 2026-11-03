The plan with each task's tests: `docs/superpowers/plans/2026-11-03-model-settings-page.md`.

## 1. Core

- [ ] 1.1 `model_settings.py` and `model_servers.py`: `field` on `Refused` and `ProbeError`
  set at every raise; `check_model` (the checks of `add_model` without the save, an
  optional probe); `check_key` refuses an empty key (`cli._server_key` uses it); the
  probe's `models_why` empty when the versioned list gives the models (D2, D3, D5, D8).
  Check: `tests/test_model_settings.py`, `tests/test_model_servers.py`, the CLI tests
  unchanged.
- [ ] 1.2 `Provider.ready_models`; Claude Code declares Claude Haiku · haiku, Claude Sonnet
  · sonnet, Claude Opus · opus (D7). Check: the providers' unit tests (aliases, others
  none).

## 2. API

- [ ] 2.1 `server/model_entries.py`, the routes in `server/app.py`, the models in
  `server/models.py`, `SECRET_ROUTE` with `model-servers`, the kept probes (D1, D4, D5,
  D6, D7); `make web-types` and both generated files committed. Check:
  `tests/test_server_model_settings.py`.
- [ ] 2.2 The key canary through a real `lado server`. Check:
  `uv run pytest -m integration -n auto tests/integration/test_model_settings_canary.py`.

## 3. Page

- [ ] 3.1 `web/src/ModelSettings.tsx`: the section in `Settings.tsx`, `MODELS_ANCHOR`, the
  API functions in `api.ts`, the servers block (add, row, Check, Change, Remove), refusals
  under their fields, the key in `SecretField` only (D9). Check:
  `web/src/ModelSettings.test.tsx`, `make web`.
- [ ] 3.2 Your models: the table, the add form with suggestions and the live check, Remove,
  the ready-made chips and Add both / Add all three (D9, D10). Check:
  `web/src/ModelSettings.test.tsx`, `make web`.
- [ ] 3.3 UI e2e of the section, the phone width, screenshots for the pull request. Check:
  `uv run pytest -m ui tests/ui/test_models_section.py`.

## 4. Docs and regression

- [ ] 4.1 `docs/design/ui.md` (Settings' sections, a section Models), `docs/design/modules.md`,
  AGENTS.md's `server/` line, CHANGELOG.md under `## 0.45.0 (unreleased)`, `### New`.
  Check: `uv run pytest tests/test_agents_md.py -n0`.
- [ ] 4.2 Regression: `make lint`, `make test`, `make web`, the changed integration and UI
  files with their markers, `openspec validate model-settings-page --strict`, `openspec
  validate --specs --strict`, a trial archive on a copy of `openspec/` validated there (the
  result in the pull request), green CI; the manual check in the pull request.
