# Settings → Models: external models and a default per agent CLI — design

Task LAD-200. The change: `openspec/changes/cli-default-model/` (proposal, deltas
`configured-models`, `model-settings-page`, `model-servers`, design.md D1-D12). The approved
shape: one block of cards (#3395), the answers of #3358. The mock-up: the flow run
`ui-design/model-picker` (`mockup.html`, `spec`, `critique`).

## What the human sees

The section has two blocks. **Your agent CLIs**: a card per agent CLI, its head the title and
login, its row `Default model` a picker, under it `Your models <n>` with the CLI's external
models, the default first, folded above five, renamed in place and removed by ×. **Model servers** as it was. Nothing on the page
says sessions use the default: they do not yet.

The picker lists `<CLI>'s settings`, YOUR MODELS, BUILT-IN, and `Other name…` for a CLI with no
full list. A pick saves at once. A list that cannot be read says why and leaves the external
models and `Other name…`.

## How it fits

- Store: `models.id`, `models.server NOT NULL`, `cli_defaults` (schema 39).
- Core: `model_settings.choices`, `set_default`, `set_default_ref`, `clear_default`; removal
  clears a default in its transaction.
- Commands: `lado model default [<cli> [<model>|--clear]]`; `lado model add` needs `--server`.
- API: `model-choices`, `model-defaults`; `defaults` in `model-settings`.
- UI: `ModelPicker.tsx`; cards in `ModelSettings.tsx`; the CLI sources leave `ModelSources.tsx`.

## Against the roadmap and the principles

- Next changes: a session takes a `ModelRef`; the launch window and the power row take
  `ModelPicker`; a tool for the supervisor takes `model_settings.choices`. None changes the store.
- Neutral core: every CLI goes through `Provider.model_list`, and the one difference of
  processes is `Provider.external_whole_process`. All four providers work; `Other name…`
  follows the list, not a CLI's name.
- One source of truth: a CLI's list is read, never kept; a default holds an id.
- No silent drops: a removal says what it cleared; a lost built-in default stays and warns; a
  list unread says why.
- Only what is used: no `project` on `model-choices`, no picker props for places not built yet,
  no `as_default`.

## Test layers

| What | Layer |
|---|---|
| migration, references, `choices`, `set_default`, removals | unit: `tests/test_state.py`, `tests/test_model_settings.py` |
| `lado model add`, `default`, `remove`, `model-server remove` | unit: `tests/test_cli_model_settings.py` |
| routes | unit: `tests/test_server_model_settings.py` |
| picker and cards | vitest: `web/src/ModelPicker.test.tsx`, `ModelSettings.test.tsx`, `ModelSources.test.tsx` |
| a real server, fake agent, key canary | integration: `tests/integration/test_model_settings_process.py`, `test_model_settings_canary.py` |
| the page in Chromium | UI e2e: `tests/ui/test_models_section.py` |
