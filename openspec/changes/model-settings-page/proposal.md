Task: LAD-187

## Why

The human saves model servers and configured models only from the terminal (`lado
model-server add|list|remove`, `lado model add|list|remove`). The epic's concept sets them
once in Settings, under names the rest of LADO refers to; the next work (a session on a
configured model) picks them in the launch window, so they must be made where the launch
window is: in the UI. Typing a CLI's model name by heart is the error the human wants gone:
the page shows what each source offers and the human ticks it.

Root cause: the store and its rules (`model_settings.py`) have no API, by "only what is
used", and the UI has no place for the human's model settings.

The human weighed three shapes of the page (the supervisor's discussion after the first
design, the cases in the epic's artifact `ux-models-cases`):

- A: two lists of explicit entries (servers, models), each added through a form, ready-made
  Claude Code chips. Long-term cost: the human types or picks every model name; a model new
  on a server is found only by asking for it.
- B (taken): sources (the agent CLIs and the saved servers) whose lists are read when
  opened, a tick per model and CLI; a ticked model is a configured model, named by default
  and renamed in place. Long-term cost: a list read per opening (a probe of up to ~10 s for
  a server), a default naming rule, and a tick that has to stay true to the entries.
- C: no entries at all, the launch window picks from the sources directly. Loses the names
  the power tables and roles refer to (the epic's concept, D18). Rejected.

Options weighed for where the page's rules live: a thin API over `model_settings.py`, each
refusal the core's line marked with its field (taken); an API with its own checks and UI
texts (two rule sets that drift); the browser probing servers itself (the key would leave
LADO's server, CORS, networks only LADO's machine sees). Held against ROADMAP and the coming
work (a session on a configured model, effort, power tables): the entries stay the one
thing the rest refers to; the page names no provider (a CLI's aliases come from its
provider's own list).

## What Changes

- Settings gets a section **Models** after Providers and environment, before Usage
  statistics, at `/settings#models`, with two tabs: **Your models** (Name, renamed by a
  click on it, Model, Runs in, From, × with Undo) and **Add models** (every LADO CLI, not
  installed ones greyed, not logged in ones marked; every saved server; `+ Add server`).
  Nothing on the page moves under the pointer: no scroll to the anchor after a change, a
  removed row keeps its place as its Undo.
- Opening a source (its whole row) reads its list now (a CLI's aliases and own list; a
  server's by a probe with its kept key), Refresh reads it again; nothing is read when the
  page opens and no list is kept. Each model has one tick; on a server the CLI is the one
  chosen in **Run in**. Ticking saves a configured model with a default name (`Claude
  Sonnet`, `gpt-5-codex`, `qwen3-8b · LM Studio · OpenCode`), unticking removes it.
- A list scrolls within a bounded height, its configured models first, with a search above
  ten models; embeddings models are hidden and counted; a configured model its source no
  longer lists shows first, ticked, marked, and is never removed by itself; a server that
  does not answer says why and its models stay.
- **Model id** only where a source's list is not whole (Claude Code's full ids, a CLI or a
  server with no list), with the launch window's live check.
- The add-server form checks the name and probes the address as the human types, without
  the key; the key goes only with Check key or Add; Add is on only for a server that
  answered.
- Adding a server probes it as `lado model-server add` does; **Change** replaces its address
  and/or key as `--replace` does (an empty key keeps the kept one); **Remove** of a server
  asks, listing its models, and removes them with it.
- `lado model-server remove <name> --with-models` removes a server and its models; without
  the flag the refusal stays, its hint naming the flag. `lado doctor` names a configured
  model its server no longer lists.
- Every refusal is the command's, in the page's words (no command to run; the human's
  manual check), under the field it concerns, in the launch window's note look.
- A new API under `/api/model-settings`, `/api/model-servers` and `/api/models`, and
  `fresh` on `GET /api/providers/{name}/models`. A server's key enters it only in the body
  of a POST and never leaves it (a canary test).
- The probe gives why a server has no list only when it has none.

## Out of scope

- Choosing a configured model in the launch window, `lado start --model <name>`, agents on
  a server, a check before the start: the next work, which uses these entries; it also
  gives the models an id to refer to (design.md D8).
- Effort, power tables, kits' and roles' weights: later work of the same epic.
- A rename in the CLI, a model's CLI, model or server changed in place, renaming a server,
  removing a key without its server: the commands stay as they are (the cases' 17); remove
  and tick again.
- A "new model" mark: it would need the previous list kept; a new model shows unticked.
- Ready-made model chips: ticking an alias of Claude Code does the same in one click.
- Probing every server when the page opens: a server that does not answer would hold the
  page; a source is read when the human opens it.
- UI texts of their own for the refusals: a second set of texts drifting from the commands'.
- Removing several models at once other than with their server.
- A second CLI for the same model of a server from the page: one tick per model; `lado
  model add` makes it, and the page shows both under one disabled tick.
- Undo of a server removed: its key is deleted with it and LADO keeps no copy of a key.

## Capabilities

### New Capabilities

- `model-settings-page`: Settings → Models, its sources and ticks, and the API it uses.

### Modified Capabilities

- `model-servers`: `lado model-server remove --with-models`; doctor names a model its
  server no longer lists; the why of a missing list only with no list.

## Impact

- Code: `src/lado/model_settings.py` (refusals with their field, `check_model`,
  `default_name`, `rename_model`, removing a server with its models), `src/lado/state.py`
  (`rename_model`, a server removed with its models in one transaction),
  `src/lado/model_servers.py` (`ProbeError.field`, the list's why), `src/lado/cli.py`
  (`--with-models`, the empty key), `src/lado/doctor.py`, `src/lado/server/app.py`,
  `src/lado/server/models.py`, `src/lado/server/launch.py` (`fresh`), new
  `src/lado/server/model_entries.py`; `web/src/Settings.tsx`, new
  `web/src/ModelSettings.tsx` and `web/src/ModelSources.tsx`, `web/src/api.ts`,
  `web/src/paths.ts`, `web/src/styles.css`; `web/openapi.json` and `web/src/api.gen.ts`
  regenerated. About 15 code files; the redesign after the human's UI remarks changes the page's two components, `styles.css`, `model_entries.py`, `models.py` and `app.py` (the form's check) of them.
- Docs: `docs/design/ui.md`, `docs/design/modules.md`, AGENTS.md's line of `server/`,
  `docs/cli.md` (`--with-models`, doctor's line), CHANGELOG.md (0.45.0, New).
- Tests: unit, integration (the key canary, `--with-models` in the real command), vitest,
  UI e2e with `tests/fake_model_server.py`.
- No schema change, no provider change. Minor release (a feature, a CLI option): 0.45.0.
