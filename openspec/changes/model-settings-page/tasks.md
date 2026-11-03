The plan with each task's tests: `docs/superpowers/plans/2026-11-03-model-settings-page.md`.

## 1. Core

- [x] 1.1 `model_settings.py`, `model_servers.py`, `cli.py`: `field` on `Refused` and
  `ProbeError` at every raise; `check_model`; the empty key in `check_key`; the probe's
  `models_why` empty when the versioned list gives the models (D2, D3, D9, D11). Check:
  `tests/test_model_settings.py`, `tests/test_model_servers.py`, the CLI tests unchanged.
- [x] 1.2 `default_name` and `add_model(name=None)`; `rename_model` in `state.py` and
  `model_settings.py` (D4, D8). Check: `tests/test_model_settings.py`, `tests/test_state.py`.
- [x] 1.3 A server removed with its models: `state.remove_model_server_with_models(id)`,
  `model_settings.remove_server(…, with_models, removed)`, `lado model-server remove
  --with-models` and the refusal's hint; `docs/cli.md` (D7). Check:
  `tests/test_model_settings.py`, `tests/test_state.py`, `tests/test_cli_model_settings.py`,
  `uv run pytest -m integration -n auto tests/integration/test_model_settings_process.py`.
- [x] 1.4 doctor names a model its server no longer lists; `docs/cli.md`'s doctor line
  (D12). Check: `tests/test_doctor.py`.

## 2. API

- [x] 2.1 `server/model_entries.py`, the routes in `server/app.py`, the models in
  `server/models.py`, `fresh` in `server/launch.py`, `SECRET_ROUTE`, the kept probes (D1,
  D5, D9, D10); `make web-types`, both generated files committed. Check:
  `tests/test_server_model_settings.py`, the existing `tests/test_server_*.py`.
- [x] 2.2 The key canary through a real `lado server`. Check: `uv run pytest -m integration
  -n auto tests/integration/test_model_settings_canary.py`.

## 3. Page

- [x] 3.1 `ModelSettings.tsx`: the section in `Settings.tsx`, `MODELS_ANCHOR`, the API
  functions in `api.ts`, Your models (table, ✎ rename, Remove, marks), the add-server form
  with the key in `SecretField` only, refusals under their fields (D13). Check:
  `web/src/ModelSettings.test.tsx`, `make web`.
- [x] 3.2 `ModelSources.tsx`: the sources, reading a list on opening and Refresh, ticks
  and a server's columns, several models of one tick, search, embeddings, missing models,
  a server that does not answer, Other model… with the live check, Change, Remove with
  its models (D5, D6, D13). Check: `web/src/ModelSources.test.tsx`, `make web`.
- [x] 3.3 UI e2e of the section, the phone width, screenshots for the pull request. Check:
  `uv run pytest -m ui tests/ui/test_models_section.py`.

## 4. Docs and regression

- [x] 4.1 `docs/design/ui.md` (Settings' sections, a section Models),
  `docs/design/modules.md`, AGENTS.md's `server/` line, CHANGELOG.md under `## 0.45.0
  (unreleased)`, `### New`. Check: `uv run pytest tests/test_agents_md.py -n0`.
- [x] 4.2 Regression: `make lint`, `make test`, `make web`, the changed integration and UI
  files with their markers, `openspec validate model-settings-page --strict`, `openspec
  validate --specs --strict`, a trial archive on a copy of `openspec/` validated there (the
  result in the pull request), green CI; the manual check in the pull request.

## 5. After the human's manual check (D15)

- [x] 5.1 Remove of a server takes only the models it named (`confirmed`, `state.ModelsChanged`).
  Check: `tests/test_state.py`, `tests/test_model_settings.py`, `tests/test_server_model_settings.py`,
  `web/src/ModelSources.test.tsx`.
- [x] 5.2 The plain-http warning under Key before Add (`POST /api/model-servers/check`); stale
  result lines and refusals go; Add off while the check refuses; a gone model's other ticks off;
  a model's column at least 10em at a phone's width. Check: `tests/test_server_model_settings.py`,
  the vitest files, `tests/ui/test_models_section.py`.
- [x] 5.3 Default names: ` · <CLI>` on a server several CLIs suit, `[1m]` as ` 1M`. Check:
  `tests/test_model_settings.py`.
- [x] 5.4 The page's refusals name no command (`page`, `page_hint`); the CLI's lines unchanged.
  Check: `tests/test_server_model_settings.py`, `tests/test_cli_model_settings.py`.
- [x] 5.5 Undo of a model removed by its tick or Remove. Check: the vitest files,
  `tests/ui/test_models_section.py`.

## 6. The page after the human's UI remarks (D16)

- [x] 6.1 The form's check as the human types: `POST /api/model-servers/check` with name,
  address, `key_typed`, the key only on Check key; name, same address, plain http, the
  probe, `kind` in `ProbeInfo`; `make web-types`; the canary sends a key through it (D16.5).
  Check: `tests/test_server_model_settings.py`, `uv run pytest -m integration -n auto
  tests/integration/test_model_settings_canary.py`.
- [x] 6.2 Tabs Your models / Add models with the count; a card per CLI, its models by name,
  the empty card's line and link; the anchor scrolled once; rename on the name (Enter,
  blur, Esc, no buttons); × and the Undo row in place (D16.1, 6, 7, 12).
  Check: `web/src/ModelSettings.test.tsx`, `make web`.
- [x] 6.3 Sources: whole-row toggle with the framed arrow, `<n> added`, the cut address,
  ✎ and 🗑 icons, one of list / Change / Remove at a time, ↻ above the list; a CLI's model
  one tick, a server's model its list of CLIs under its row; a bounded list with the configured
  first and its count; embeddings hidden and counted; Model id only where the list is not
  whole; the form with its live notes, Check key and Add on by the check; a server removed
  leaves its row (D16.2–4, 8–13). Check: `web/src/ModelSources.test.tsx`, `make web`.
- [x] 6.4 UI e2e: no scroll after a tick, a removal, an add and a remove of a server
  (`scrollY` and the acted element's top unchanged); Kilo-sized list (300 models from the
  fake CLI list) bounded; rename by Enter and Esc; the add form's check against
  `tests/fake_model_server.py`; 390 px without sideways scroll; screenshots for the pull
  request. Check: `uv run pytest -m ui tests/ui/test_models_section.py`.
- [x] 6.5 Agent CLI in the UI (D17): the labels in `Launch.tsx`, `Providers.tsx`,
  `SystemPanel.tsx`, `logins.SETTINGS`, the Docker headers, the docstrings that name the
  section; the tests quoting them; `docs/cli.md`, `docs/install.md`, `docs/design/*.md`.
  Check: `make test`, `make web`, `uv run pytest -m ui tests/ui/test_launch.py
  tests/ui/test_providers_section.py`, `tests/test_docker.py`.
- [x] 6.6 `docs/design/ui.md`'s section Models as built; the manual check in the pull
  request updated; regression as 4.2.

## 7. The page after the design review (D18)

- [x] 7.1 `ModelCheck.name` (the default name for a check without a name) and
  `ModelServerCheck.replace` (the server's own name not taken) in `server/models.py` and
  `server/model_entries.py`; `make web-types`, both generated files committed (D18.7, 10).
  Check: `tests/test_server_model_settings.py`.
- [x] 7.2 `web/src/useScrollAnchor.ts`: the anchor noted before a render and the scroll by
  its moved top after it, on `.content` above 900 px and the window at or under it (D18.3).
  Check: `web/src/useScrollAnchor.test.tsx`.
- [x] 7.3 `ModelSettings.tsx` without tabs: the intro, the three blocks with their counts;
  Your models' cards only for agent CLIs with models, the line of those without, names
  wrapped, From `the agent CLI`; × with `Removed <name>. Undo`, Undo going after `UNDO_MS`
  and the row staying until the next change; focus after ×, Undo and Esc (D18.1, 2, 4, 12).
  Check: `web/src/ModelSettings.test.tsx`, `make web`.
- [x] 7.4 `ModelSources.tsx`: Model servers before Models of your agent CLIs; rows with the
  chevron, the badges and the second line; the address on hover and focus, wrapped under 600
  px; untick without Undo; `would be <name>` from `checkModel`; the page's memory of
  unticked renamed models and their re-tick; `Unticking removes <name>.`; the found panel,
  Key's label and line; `Open a model to tick…`; Change's live check; Remove's question
  and button (D18.5–11). Check: `web/src/ModelSources.test.tsx`, `make web`.
- [x] 7.5 `styles.css`: `--row`, `--list-rows`, `--gap-block`; the phone's 44 px targets
  and rows, a server's list of up to 20 models unbounded (D18.13, 14). Check: `make web`,
  7.6.
- [x] 7.6 UI e2e (`tests/ui/test_models_section.py`, reworked): the acted element's top
  unchanged to 0 px after a tick in the middle of a 300-model list, Add server, Remove of a
  server, × and Undo, Undo running out while the focus is in Models of your agent CLIs, a
  list's read ending above; rename by Enter and Esc; the form's check and found panel against
  `tests/fake_model_server.py`; 390 px: no sideways scroll, 44 px targets, an unbounded list
  of 12; screenshots for the pull request. Check: `uv run pytest -m ui
  tests/ui/test_models_section.py`.
- [ ] 7.7 `docs/design/ui.md`'s section Models as built; the manual check in the pull request
  names the three blocks and the new Undo; regression as 4.2.
