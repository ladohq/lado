Task: LAD-240

## Why

Found in the human's check of the settings pages (LAD-238, PR #256) on a real LM Studio: a model
ticked under a server is named by LADO `qwen3.8-27b · LM Studio · Kilo CLI`.

- On Model servers, Your models gives that name, then the columns Model, From and Agent CLI say
  the same three things again.
- On Agent CLIs, the Default model of Kilo CLI at 768 px shows `qwen3.8-27b · LM Studi…` beside
  the server's badge `LM Studio`, and the id `qwen3.8-27b` gives way after it.
- On a phone, a model's second line `qwen3.8-27b · LM Studio · Kilo CLI · default` repeats its
  name almost word for word.

Cause: the rule of the default name (`model_settings.default_name`, from model-settings-page,
2026-11-04) put the server, and the CLI when the server suits more than one, into every name,
as names then were the only thing that told two models apart on the CLIs' cards. Since then
every place that shows a configured model shows its server and its CLI on their own (the
table's columns, the picker's server badge, the CLI's own card), so the name only repeats them.
The behaviour is older than LAD-238 and was left out of that pull request.

Options weighed:

- A (taken): the default name is the model's id; a taken name gets what tells the new model from
  the one that holds it (` · <CLI>` or ` · <server>`), then both, then ` (2)`, ` (3)`. Where a
  model's id would stand beside its name and is the name itself, it is not shown again. Long-term
  cost: one rule in the core and one in each of three UI places; names stay unique for
  `lado model default`, `lado start --model` and `lado model remove`.
- B: the model's id, and ` (2)`, ` (3)` on a clash. Shorter, but a name alone, as the command line
  shows it, no longer says how two models differ. Long-term cost: renames by hand.
- C: names unique per agent CLI, not across CLIs, so the same model of two CLIs needs no suffix.
  A schema change (`folded` unique per CLI), and every command that takes a name without a CLI
  (`lado model remove`, rename, the API's `/api/models/{name}`) would need one. Long-term cost:
  large, for one suffix less.

## What Changes

- A model ticked or added on Model servers without a name is named by its id as the server gives
  it, whole (`qwen3.8-27b`, `qwen/qwen3-coder`), cut to 64 characters as now.
- A name taken (ignoring case) by another model gets ` · <CLI title>` when that model is of
  another CLI, ` · <server>` when it is of the same CLI; then ` · <server> · <CLI title>`; then
  ` (2)`, ` (3)` after that until free. No saved model is renamed.
- A model's id is not shown again beside or under its name where it equals the name ignoring
  case: in the model picker (Agent CLIs' Default model and the launch window, field and list), in
  a model's second line of Your models at 900 px and narrower, and in the Model fact on the
  agent's page. The Model column of Your models on a wide window stays.

## Scope

- `model_settings.default_name` and its unit tests.
- The picker (`ModelPicker.tsx`), Your models' row (`ModelSettings.tsx`), the agent's Model fact
  (`Agents.tsx`), their unit tests and a UI e2e test.
- The docs that describe these: `docs/design/ui.md`, `docs/design/modules.md`, CHANGELOG.md.

## Out of scope

- Renaming the models saved under the old long names: only the human renames a model (a click on
  its name in Your models); a rename by LADO would break `--model <name>` in the human's scripts.
- Names unique per agent CLI (option C): a schema change and a CLI argument on every command that
  takes a name, for one suffix less.
- Steering clear of a CLI's built-in model names: a default name equal to a model of the CLI's own
  list (a gateway that serves `gpt-5.5` to Codex CLI) would need the CLI's list read on every
  tick's check. Such a clash is already refused loudly by `lado model default` and `lado start
  --model` with `rename the saved one`, and the pages pick models by reference, not by name.
- The Model column of Your models on a wide window: a column of a table, not a repeat.

## Impact

- Code: `src/lado/model_settings.py`, `web/src/ModelPicker.tsx`, `web/src/ModelSettings.tsx`,
  `web/src/Agents.tsx` (on top of PR #256, LAD-238, which must be merged into main first).
- No API, MCP, CLI or schema change; a fix, in 0.45.0 (unreleased): no minor bump.
- Specs: model-settings-page (the default name, the picker, Your models on a narrow window),
  agent-model (the agent's Model fact).
