## Context

The epic branch has the store and the commands of the human's model settings:
`model_settings.py` (`check_name`, `server_to_add`, `add_server(name, address, key, *,
replace, warn, note)`, `remove_server`, `add_model(name, cli, model, server_name, env)`,
`_on_server`, `remove_models`, `server_key`, `has_key`, `clis`, `Refused(text, hint)`),
`model_servers.py` (`address`, `probe(text, key, command)`, `Probe`, `ProbeError(text,
hint)`, `lines`, `clis`, `plain_http_warning`, `NOT_CARRIABLE`), `model_check.py`,
`state.py` (`model_servers` with an id; `models` keyed by `folded`, the name casefolded,
no id; schema 38) and `cli.py`. No API reads them. The launch window's Model field
(`Launch.tsx`: `SuggestField`, `ModelNote`, `MODEL_DEBOUNCE`, `GET
/api/providers/{name}/models`, its lists kept a minute in `server/launch.py`) checks a CLI's
model as typed. A project's secrets are typed in `SecretField` (`ProjectVariables.tsx`),
sent in a body; `server/app.py` keeps a 422 on `SECRET_ROUTE` from repeating it. Settings
(`Settings.tsx`) is one page of sections; Providers and environment reads each CLI's install
and login (`GET /api/providers/logins`, a snapshot of `provider_check`).

The human's answers: the first design's #2875 (the section's place, nothing asked on
opening, Change as `--replace`, refusals as the commands' lines, the dots field for the
key), then option B with the cases of the epic's `ux-models-cases` and #2890: rename in
place, references by the entry not its name; removing a server removes its models after a
confirmation, the CLI with `--with-models`; no "new model" mark; no ready-made chips.

## Goals / Non-Goals

Goals: the human sees what each source offers and ticks it; names, renames and removes
configured models; adds, changes and removes servers with the commands' rules and lines;
the key goes in and never out. Non-goals: the proposal's Out of scope.

## Decisions

### D1. The API

Thin routes in `app.py` over a new module `src/lado/server/model_entries.py`, under the
token (`guard` reads, `guard.changes` changes):

| Route | Body | Answer |
|---|---|---|
| `GET /api/model-settings` | | `ModelSettings{models: [ConfiguredModelInfo], servers: [ModelServerInfo]}` |
| `POST /api/model-servers` | `ModelServerAdd{name, address, key: str \| None, replace: bool}` | `ModelServerAdded{server, probe: ProbeInfo, notes, warnings}` |
| `POST /api/model-servers/check` | `ModelServerCheck{address, key: bool}` | `ModelCheck`: the plain-http warning before an Add (the human's manual check: it came only after the key was sent); asks no server, takes no key |
| `POST /api/model-servers/{name}/probe` | | `ProbeInfo`, probed now with the kept key |
| `DELETE /api/model-servers/{name}?with_models=true&confirmed=…` | | `ModelSettings` |
| `POST /api/models` | `ModelAdd{name: str \| None, cli, model, server: str \| None}` | `ModelAdded{model: ConfiguredModelInfo, check: ModelCheck}` |
| `POST /api/models/check` | `ModelAdd` | `ModelCheck{kind, text, field}` (200 also for a refusal) |
| `PATCH /api/models/{name}` | `ModelRename{name}` | `ModelSettings` |
| `DELETE /api/models/{name}` | | `ModelSettings` |
| `GET /api/providers/{name}/models?fresh=true` | | as now; `fresh` skips the kept list and keeps the new one |

`ModelServerInfo{name, address, kind, has_key}` (the saved row, no request; the page shows
`key: yes`); `ConfiguredModelInfo{name, cli, cli_title, model, server: str | None}`;
`ProbeInfo{models: [str] | None, models_why, embeddings, apis_why, clis: [CliApi{name,
title, api}]}`, only what the page shows (the CLIs that cannot use a server, the type and
the address a probe found are the command's alone). A refusal is a 400 whose
`detail` is `EntryRefused{message, hint, field, warnings}`. `GET` with no `lado.db` answers
empty lists and makes none (`database()`); a change makes it, as the commands do. Names go
in the path encoded whole. The CLI sources need no route of their own: their install and
login come from `/api/providers` and `/api/providers/logins`, their lists from the launch
window's route with `fresh`. Why: one route per action keeps "the page does what the
command does" checkable; nothing in `GET` asks a server (#2875, 2).

### D2. A refusal names its field, set by the core

`model_settings.Refused` and `model_servers.ProbeError` get `field: str` (`name`,
`address`, `key`, `cli`, `server`, `model` or `""`), set where raised: names and their
taken lines → `name`; `check_key`, `NOT_CARRIABLE` → `key`; asks for / refused the key →
`key`; does not answer, TLS, unknown server, an address the probe does not take →
`address`; `add_model`'s unknown CLI → `cli`; empty, embeddings, not in a list → `model`;
the server not saved, no API, not answering, lacking the CLI's API → `server`; removals and
disk errors → `""`. The CLI ignores it. Why: each refusal under its field without a second
copy of the rules mapping texts to fields; texts stay the commands'.

### D3. `check_model`: a model's checks without the save

`model_settings.check_model(name, cli, model, server_name, env, *, probe=None) -> Checked`
runs `add_model`'s checks in their order (the name only when given) and returns
`Checked(provider, model, server, verdict, aliases)`; `add_model` calls it and saves.
`probe: Callable[[state.ModelServer], Probe] | None` lets the page's live check use a kept
probe (D5); `add_model` gives none, so a server is probed now. Why: the live note and a
tick or Add never disagree on a rule.

### D4. A model's default name, set by the core

`model_settings.default_name(provider, model, server, aliases) -> str`: an alias, the first
word of the CLI's title and the alias with its first letter capitalised (`Claude Sonnet`);
a model of a CLI's own list, the model; on a server, `<model> · <server name>`; a name taken
(ignoring case) gets ` · <CLI title>`, then ` (2)`, ` (3)`, … and is cut to the name's 64
characters before its suffix. `add_model` takes `name=None` and names the model so.
Why: a tick needs a name without a form; the rule lives once, so the CLI could use it later.

### D5. Lists read now; a server's probe kept a minute for the live check only

Opening a source and Refresh read now: a CLI's list through `GET
/api/providers/{name}/models?fresh=true` (it replaces the kept list), a server's through
`POST /api/model-servers/{name}/probe`, which also keeps the probe in `model_entries` for a
minute by `(server.id, server.address)`, under a lock, a failed probe not kept. `POST
/api/models/check` (Other model…'s note, at every settled keystroke) uses a kept probe or
probes and keeps it; ticking, Other model's Add, add and Change probe now. The page keeps
no list after the source closes. Why: the cases' "read again at every opening" (a new model
shows), and a probe of up to eight requests and ~10 s not repeated per keystroke.

### D6. The tick is derived from the entries

The page computes each tick from `ModelSettings.models`: on when a model has the same CLI,
model and server. Ticking POSTs `ModelAdd{name: null, …}`; unticking DELETEs the one model
it stands for; with several such models the tick is on and disabled, its title naming
them, and they are removed in Your models. The columns of a server are its `ProbeInfo.clis`
(the APIs it proves now) that `/api/providers` says are installed. A configured model whose
model the read list lacks is shown first, ticked, marked. Why: one source of truth (the
entries); no second store of ticks.

### D7. A server removed with its models

`state.remove_model_server(id, with_models=False)`: with it, one transaction deletes the
models on the server, then the server; `model_settings.remove_server(name, with_models=False,
removed=callback)` reports each model removed, then removes the key folder as now. Without
it the refusal stays, its text as now and its hint `or remove them with it: lado
model-server remove "<name>" --with-models`. `cli.py` adds `--with-models`; the page always
sends `with_models=true` after its confirmation, which names the models from
`ModelSettings`, and `confirmed=` for each of them: the transaction removes nothing
(`state.ModelsChanged`, a refusal) when the server has other models by then, and the page
reads the entries and asks again. Why: #2890, 2; the refusal remains the CLI's guard
against a slip; the human's manual check found a model added from the CLI after the page
asked removed unconfirmed.

### D8. Renaming without an id now

`state.rename_model(name, new)` updates `name` and `folded` of the row in one statement
(`NameTaken` on a clash); `model_settings.rename_model(name, new)` checks the new name as a
name and refuses a taken one with the model's name-taken line (field `name`). The models
table has no id: its key is the casefolded name. Nothing refers to a model yet, so a rename
needs no migration now. The first change that stores a reference to a model (the launch
window's choice, the power tables) SHALL add `models.id` with a migration 38 → 39 that
gives each existing row an id, and refer by it. Why: #2890, 1 asks that references hold the
entry, not its name; "only what is used" leaves the column to the change that first uses it.

### D9. The key's way in

The key travels only in `ModelServerAdd.key`, the body of `POST /api/model-servers` (add
and Change). `SECRET_ROUTE` becomes `r"/api/((projects/[^/]+/secrets|providers/[^/]+/variables)/|model-servers(/|$))"`
so a 422 there repeats nothing of its body. `null` is no key (add) or the kept key
(Change); `""` is refused with the command's `the key is empty`, moved from
`cli._server_key` into `model_settings.check_key` so both share it (field `key`). No answer
type has a key field; `EntryRefused` is built from texts that never hold the key. Why: the
spec's key rule and the canary of LAD-116 and the previous change.

### D10. Warnings and notes of add

`add_server`'s `warn` and `note` callbacks collect into `warnings` and `notes`; both go into
`ModelServerAdded`, `warnings` into `EntryRefused` too. The page shows `warnings` under Key
and `notes` in the server's source. Why: the core separates them already.

### D11. The probe's why only with no list

`model_servers.probe`: when the plain list gives none and the versioned one gives models,
`models_why` is `""`. Why: E1 of the previous change's review; `ProbeInfo` shows it.

### D12. doctor names a model gone from its server

`doctor.check_model_servers`: for each server that answered with a list, each configured
model on it whose model the list lacks adds `model "<name>" (<model>) is not in <server>'s
list of models` and makes the line WARN. Why: the cases' 7; the probe is already made.

### D13. The page

`web/src/ModelSettings.tsx` (new): the section (`id="models"`, `MODELS_ANCHOR` in
`paths.ts`, scrolled to as Providers' anchor is), Your models (table, ✎ rename, Remove),
the add-server form. `web/src/ModelSources.tsx` (new): the sources, a source's list with
its ticks, search, embeddings, missing models, Other model…, Refresh, Change and Remove of a
server. It reuses `SecretField`, `SuggestField` (Other model…'s suggestions are the read
list), the `.field`, `.launch-grid`, `.field-note`, `.project-vars`, `.project-edit`
classes, `useDebounced`/`MODEL_DEBOUNCE`, `messageOf`, `ApiError.detail`. `Settings.tsx`
renders it between `Providers` and `StatisticsSetting`. The page reads `GET
/api/model-settings` on opening and after each change of its own; no change-feed event. New
CSS only for what the classes lack (sources, a list's columns, the search, phone layout), in
`styles.css` with tokens only. The search shows above more than ten models. Why: one look
with the launch window and the project page (LAD-176's remarks).

### D14. Tests

Unit: `tests/test_model_settings.py` (fields; `check_model` equals `add_model`'s checks;
`default_name`; `rename_model`; `remove_server(with_models=True)`), `tests/test_state.py`
(`rename_model`, removal with models in one transaction), `tests/test_model_servers.py`
(the why), `tests/test_doctor.py` (the missing model), `tests/test_cli_model_server.py`
(`--with-models`, the hint), new `tests/test_server_model_settings.py` (every route against
`tests/fake_model_server.py`; `fresh`; the kept probe; GET asks nothing and makes no
`lado.db`; the 422 on the secret route). Integration: new
`tests/integration/test_model_settings_canary.py` (a real `lado server`, the fake model
server in its own process: the key canary) and a `--with-models` case in
`tests/integration/test_model_settings_process.py`. Vitest: `web/src/ModelSettings.test.tsx`,
`web/src/ModelSources.test.tsx`. UI e2e: new `tests/ui/test_models_section.py`. Why:
AGENTS.md's lowest layer each; the canary and the real command cross processes.

## Risks / Trade-offs

- Opening a server's source takes up to ~10 s for one that hangs: the source says
  `reading the models…` and the rest of the page stays usable.
- A tick shown from a list read seconds ago may meet a server changed since: ticking probes
  again and a refusal shows in the tick's row.
- The refusals name CLI commands on a page (`run lado model-server add … --key`): accepted
  by the human (#2875, 5).
- A change made from the CLI while the page is open shows on the next opening.
- `default_name` makes long names on servers with long model ids; the name is cut to 64
  characters and can be renamed.
