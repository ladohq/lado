# Settings → Models: external models and a default per agent CLI: Implementation Plan

**Goal:** the store keeps only external models, each agent CLI has a default model kept as a
reference, and Settings → Models shows a card per CLI with one picker over a computed list.

**Architecture:** schema 39 and `ModelRef` in `state.py`; the rules in `model_settings.py`; thin
routes through `server/model_entries.py`; `ModelPicker.tsx` and the cards in `ModelSettings.tsx`.

**Tech Stack:** Python 3.10+, FastAPI and pydantic, React + TypeScript (Vite, vitest), Playwright,
pytest (`-n auto`, `-m integration`, `-m ui`), `tests/fake_model_server.py`.

**Spec:** `openspec/changes/cli-default-model/` and
`docs/superpowers/specs/2026-11-05-cli-default-model-design.md`; the mock-up, its spec and
critique: flow run `ui-design/model-picker`, the layout of variant B.

## Global Constraints

- No new Python or npm dependency. Past ~25 code files (tests and generated files aside): stop
  and ask whether it is still this task.
- A CLI's list is read with `base.run_list`'s timeout; no new wait. No agent CLI's global config
  is touched.
- The block of servers, Add, Change and the key's handling do not change; the key canary stays
  green.
- No session reads a default. The page says nothing of sessions using it.
- Nothing in code, docs, specs or the UI names the epic's steps or `docs/epics/`.
- UI texts exact as in the delta; the rest as the mock-up's spec; every refusal is the core's.

## Review Focus

1. A default on a model of a server removed through `lado model-server remove --with-models`
   while the page is open: the card shows the settings and the line after the next reload.
   Test in task 6.
2. A `lado.db` of schema 38 with a default-less model on a server and one without: the first
   keeps every field, foreign keys pass. Test in task 1.
3. A name with different case and a name of another CLI on a CLI with no list (Claude Code): the
   entry is refused, not saved as an other name. Test in task 2.
4. A list read that answers after the human moved on (a second picker open, the page left): the
   stale answer changes nothing. Test in task 5.
5. The picker at the bottom of the page and on a phone: the list stays in view and the page does
   not scroll sideways. Test in task 7.

---

### Task 1: The schema and the reference

**Files:** Modify `src/lado/state.py`, `tests/agent_helpers.py`; Test `tests/test_state.py`.

**Produces:** `state.ModelRef`, `state.cli_defaults() -> list[ModelRef]`,
`state.set_cli_default(ref)`, `state.clear_cli_default(cli) -> bool`, `ConfiguredModel.id`,
`state.model_by_id(id)`; `state.add_model(id, name, cli, model, server)`.

- [ ] Write the tests: from `previous_schema()` a row with a server keeps its fields and gets an
  id, a row without one is gone; the CHECK refuses both and neither; a default survives a rename.
- [ ] Run them: `uv run pytest tests/test_state.py -n0 -k "model or default"`; they fail.
- [ ] Implement D1 and D2; `schema_before` undoes step 38 (rebuild `models` without id, drop
  `cli_defaults`), `MODELS_TABLE_38` in `MIGRATIONS[37]`.
- [ ] Run them and `make test`; commit.

### Task 2: The rules and the commands

**Files:** Modify `src/lado/model_settings.py`, `src/lado/cli.py`, `src/lado/providers/base.py`,
`src/lado/providers/opencode_family.py`, `docs/cli.md`, `docs/design/modules.md`; Test
`tests/test_model_settings.py`, `tests/test_cli_model_settings.py`.

**Consumes:** task 1. **Produces:** `model_settings.choices`, `set_default`, `set_default_ref`,
`clear_default`, `remove_models(names, removed, cleared)`, `remove_server(…, cleared=…)`,
`Provider.external_whole_process`.

- [ ] Write the tests, one per scenario of `configured-models` and `model-servers`: add without
  `--server`; `default` table; external, built-in, clash, other CLI's entry on Claude Code, not
  installed, warning, refused, clear, clear with none, model with `--clear`; removals print the
  cleared line; `choices` for a full list, aliases, a timeout.
- [ ] Run them; they fail.
- [ ] Implement D3, D4, D5, D7, D12's core part; `lado model default` in `cli.py` with `model`
  and `--clear` exclusive (exit 2).
- [ ] Run them and `make test`; update `docs/cli.md`; commit.

### Task 3: The API

**Files:** Modify `src/lado/server/model_entries.py`, `src/lado/server/models.py`,
`src/lado/server/app.py`, `web/openapi.json`, `web/src/api.gen.ts`, `web/src/api.ts`; Test
`tests/test_server_model_settings.py`.

**Consumes:** task 2. **Produces:** the routes of D6.

- [ ] Write the tests: each route, a refusal as `EntryRefused` with its field, `listing` with
  `defaults`, no request to a server on `GET /api/model-settings`, `fresh`.
- [ ] Run them; they fail. Implement D6. `make web-types`; commit both generated files.
- [ ] Run `uv run pytest -m integration -n auto tests/integration/test_model_settings_canary.py
  tests/integration/test_model_settings_process.py`; commit.

### Task 4: The picker

**Files:** Create `web/src/ModelPicker.tsx`, `web/src/ModelPicker.test.tsx`; Modify
`web/src/styles.css`, `web/src/modelFakes.ts`.

**Consumes:** task 3. **Produces:** `<ModelPicker cli value where="settings" onPick onError />`.

- [ ] Write the vitest tests, one per scenario of the picker's requirements: order, empty groups,
  search above ten, `Other name…` by `other_name`, reading, unread list, no ↻ on aliases, the
  whole-process line by `whole_process`, opening upward near the window's end, the keyboard
  (Esc twice in a search, Tab closes without a pick).
- [ ] Run `npx vitest run src/ModelPicker.test.tsx` in `web/`; it fails. Implement to the
  mock-up. Run it; commit.

### Task 5: The cards

**Files:** Modify `web/src/ModelSettings.tsx`, `web/src/ModelSources.tsx`,
`web/src/ModelSettings.test.tsx`, `web/src/ModelSources.test.tsx`, `web/src/styles.css`.

**Consumes:** task 4.

- [ ] Write the tests: cards in order, not installed, models on the card, the default first,
  folded above five and kept through a reload of the entries, lead
  with and without models, the background read of a built-in default only, a stale read dropped,
  a lost built-in default, an unread list with `Check again`, a silent server and a model gone from it on picker opening.
- [ ] Run them; they fail. Implement D8, D10, D12's page part. Run `make web`; commit.

### Task 6: Removing a default

**Files:** Modify `web/src/ModelSettings.tsx`, `web/src/ModelSources.tsx`, their tests.

- [ ] Write the tests: × and untick ask only for a default; Cancel and Esc; Undo restores model
  and default (D11), a refused second call in the row; the server's question names defaults; the
  card's line after a server removed, gone at the next change.
- [ ] Run them; they fail. Implement. Run them; commit.

### Task 7: End to end, docs

**Files:** Modify `tests/ui/test_models_section.py`, `tests/integration/test_model_settings_process.py`,
`docs/design/ui.md`, `CHANGELOG.md`, `AGENTS.md` only if a module line changes.

- [ ] UI e2e with `uv run pytest -m ui tests/ui/test_models_section.py`: set a built-in default,
  an external one, `Other name…`, a long list searched, a removal with Undo, phone width without
  sideways scroll, the picker at the page's end in view.
- [ ] Integration: `lado model default` and `remove` across processes with the fake server.
- [ ] `docs/design/ui.md` Models rewritten to the two blocks; `CHANGELOG.md` under `## 0.45.0
  (unreleased)`, `### New`, the entry `Set models in Settings` revised.
- [ ] `make lint`, `make test`, `make web`, `openspec validate --specs --strict`,
  `openspec validate cli-default-model --strict`; a trial archive on a copy of `openspec/`, its
  result in the pull request; the regression run of the changed tests with their markers; commit.
