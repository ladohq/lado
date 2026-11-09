## Context

`model_settings.default_name` (PR #256's branch, `src/lado/model_settings.py`) names a model
ticked or added on Model servers without a name: `<model> · <server>`, ` · <CLI title>` added
when the server suits more than one CLI, a taken name trying ` · <CLI title>`, then
` · <CLI title> (2)`, … each cut to `MAX_NAME` (64) before its suffix. Names are unique ignoring
case across all CLIs (`models.folded`): `lado model default <cli> <name>`, `lado start --model
<name>`, `lado model remove <name>` and `/api/models/{name}` find a model by it. The pages show a
configured model's name with its id (`ModelPicker`'s `mp-id` / `mp-sub`), its server (badge,
column) and its CLI (column, or the card it is on).

## Decisions

D1. The default name is the model as the server gives it, whole, vendor prefix included
(`qwen/qwen3-coder`): two vendors' models of one short name stay apart, and the name matches what
`lado model-server probe` and the CLI's `/model` list print. Cut to 64 characters as before.

D2. A taken name grows by what tells the new model from the one that holds it, looked up with
`state.model(candidate)`: held by another CLI's model → ` · <CLI title>`; by the same CLI's model
(so another server, or a model the human named so) → ` · <server>`; then ` · <server> · <CLI
title>`; then that with ` (2)`, ` (3)`, … Each candidate is cut to 64 before its suffix, as now.
The server-suits-several-CLIs branch (`model_servers.suiting`) goes: the CLI is added only on a
clash. Nothing already saved is renamed: the first model keeps the short name.

D3. "The model is its name" is one comparison, `model.casefold() == name.casefold()` (the
core's `folded`; in TypeScript the files' `fold`), made where each place renders, not a new field
of the API: the name and the model are already in every answer that shows them, and a field would
be a second source of the same fact. Where the model is left out: the picker's field (`mp-id`) and
row (`mp-sub`), the narrow Your models line (`mx-model`, and the ` · ` before `mx-from`), the
agent's Model fact. The field's `title`, the row's `aria-label` and the wide table's Model column
keep it.

D4. A default name equal to a model of the CLI's own list is not avoided: knowing the list costs
the CLI's run (`provider.model_list`) on every tick's check. Such a clash is refused loudly where a
name is read (`check_default`: `is both a saved model of <CLI> and one of its own; rename the saved
one`), and the pages pick by reference (`set_default_ref`), so it does not stop the UI.

## Neutral core

`default_name` takes the CLI's title from its provider and asks nothing of a CLI; it works for all
four providers alike. No provider code changes.

## Tests by layer

- Unit (`tests/test_model_settings.py`): the rule of D1 and D2, every suffix, the cut, the case.
- Web unit (Vitest: `ModelPicker.test.tsx`, `ModelSettings.test.tsx`, `Agents.test.tsx`): D3 in
  each place, a model named otherwise still showing its id.
- UI e2e (`tests/ui/test_models_section.py`, marker `ui`): the reported screens at 768 and 390 px
  and the tick's `as <name>`, against a real `lado server`; only what needs a layout.
- No integration test: nothing crosses processes.
- Regression run: `make test`, `make web`, the changed `tests/ui/` files; CI runs the rest.
