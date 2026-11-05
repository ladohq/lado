Task: LAD-200

## Why

Settings → Models keeps a CLI's own models as entries the human ticks and names, next to the
models of the human's servers. A CLI's own models need no keeping: LADO reads them from the
CLI whenever it asks, and the list adds to what the CLI offers, it never limits it. What the
human lacks is the choice the next work rests on: one model an agent CLI runs on unless
something says otherwise, built-in or on a server, picked from one list.

Root cause: the store has one kind of model, an entry with an optional server, so a CLI's
own model can be referred to only by saving it first, and an entry is referred to by a name
the human may change. There is no reference to a model, and no place that computes what a
CLI can run.

Options weighed for what the store keeps:

- A: built-in and external models both as entries, a default pointing at an entry (today's
  store). Long-term cost: every built-in model used must be ticked first; a second list of
  what the CLI already knows, which drifts when the CLI changes.
- B (taken): only external models are entries; a CLI's full list is computed (its own list
  read live, plus the external models ticked for it) and never stored; a model reference is
  external (an entry's id) or built-in (a CLI and the CLI's name). One source of truth. Cost:
  custom names of built-in models go, and a list read for each picker's opening.
- C: no entries at all, references hold a server and a model. Loses the names and the ticks
  of a server's model × CLI, which are the human's list of models per CLI.

Options weighed for the page, both drawn in the mock-up: two blocks, the CLI's cards above Your
models (each CLI twice on the page, a checked block untouched); one block, a CLI's card holding
its default and its models (taken by the human, #3395: no second card per CLI; the whole list of
external models stays in `lado model list`).

Options weighed for the picker: a picker per place (three components that drift), or one
component over one list (taken): the launch window and the power table's rows reuse it.

## What Changes

- `lado model add` takes external models only: `--server` is required.
- A default model per agent CLI, kept as a model reference: `lado model default` prints them,
  `lado model default <cli> <model>` sets one, `lado model default <cli> --clear` clears it.
- A CLI's full list is computed in one place of the core and served by one API route, a
  list that cannot be read saying why.
- Settings → Models: the ticks of a CLI's own models, their names and the blocks Your models
  and Models of your agent CLIs go. One block Your agent CLIs takes their place: a card per
  agent CLI with `Default model`, one picker (the CLI's own settings, your models, built-in
  models, a search for a long list, `Other name…` only for a CLI with no full list, with the
  session model's warning) and, under it, the external models of that CLI, renamed and removed
  there. The block of servers, Add, Change and the key's handling do not change.
- Removing a server or a model a default uses names it in the confirmation and clears the
  default; a built-in default the CLI's list lost shows on the card and stays.
- Schema 39: `models.id`, a model's server required, table `cli_defaults`. Rows without a
  server are dropped: they exist only on stands of this work's branch.

## Out of scope

- Applying a default to agents, the launch window, an agent's config: the next change; here
  the default is kept and shown, and the page promises no session uses it. A picker with
  nothing to run on would be a second design of the same launch.
- `list_models` and `spawn_worker(model=…)`: they need sessions on references first.
- Effort next to the picker: its own change, on top of the picker.
- The key form's polish: unrelated to the store; the servers' block stays as it was checked.
- The power table: only a sketch in the mock-up, so the picker fits it later.
- `lado doctor` on a default: nothing runs on a default yet, so it has nothing to warn of.

## Impact

- `state.py` (schema 39), `model_settings.py`, `cli.py`, `providers/base.py`,
  `providers/opencode_family.py` (one attribute); `doctor.py` unchanged.
- `server/model_entries.py`, `server/models.py`, `server/app.py`; `web/openapi.json`,
  `web/src/api.gen.ts`.
- `web/src/ModelSettings.tsx`, `web/src/ModelSources.tsx`, a new `web/src/ModelPicker.tsx`,
  `web/src/api.ts`, `web/src/styles.css`.
- `docs/cli.md`, `docs/design/ui.md`, `docs/design/modules.md`, `CHANGELOG.md`.
- Version: a minor (a CLI change and a schema migration), within 0.45.0 (unreleased).
