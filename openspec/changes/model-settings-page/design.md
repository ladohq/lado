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
| `POST /api/model-servers/check` | `ModelServerCheck{name, address, key: str \| None, key_typed: bool}` | `ServerCheck{probe: ProbeInfo \| None, refusals: [EntryRefused], warnings, notes}`: the form's check as the human types (D16.5); probes the address, with `key` only when the human pressed Check key |
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
After the human's manual check (their answer at #2935): on a server several CLIs suit (by
its saved APIs, `model_servers.suiting`, not by which are installed, so a name does not
change when a CLI is installed) every name gets ` · <CLI title>`, so the first ticked one
says its CLI too; an alias's `[1m]` reads ` 1M` (`Claude Opus 1M`).

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

The page computes each tick from `ModelSettings.models`: on when a model of the source has
the same model (on a CLI: that CLI and no server; on a server: that server, any CLI).
Ticking POSTs `ModelAdd{name: null, …}`, on a server with the CLI of Run in; unticking
DELETEs the one model it stands for; with several such models the tick is on and disabled,
its title naming them, and they are removed in Your models. Run in offers the server's
`ProbeInfo.clis` (the APIs it proves now) that `/api/providers` says are installed (D16.2).
A configured model whose model the read list lacks is shown first, ticked, marked. Why: one
source of truth (the entries); no second store of ticks.

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

The key travels only in the body of a POST: `ModelServerAdd.key` of `POST
/api/model-servers` (add and Change) and `ModelServerCheck.key` of `POST
/api/model-servers/check` (Check key, D16.5). `SECRET_ROUTE` becomes `r"/api/((projects/[^/]+/secrets|providers/[^/]+/variables)/|model-servers(/|$))"`
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

`web/src/ModelSettings.tsx`: the section (`id="models"`, `MODELS_ANCHOR` in `paths.ts`),
its two tabs (D16.1), Your models (table, rename in place, ×, Undo rows). `web/src/
ModelSources.tsx`: the sources, a source's list with its ticks, Run in, search, the
embeddings line, missing models, Model id, Refresh, the add-server form, Change and Remove
of a server. It reuses `SecretField`, the `.tab-bar`/`.tab-item`/`.tab-count`, `.field`,
`.launch-grid`, `.field-note` classes, `useDebounced`/`MODEL_DEBOUNCE`, `messageOf`,
`ApiError.detail`. `Settings.tsx` renders it between `Providers` and `StatisticsSetting`.
The page reads `GET /api/model-settings` on opening and after each change of its own; no
change-feed event. New CSS only for what the classes lack, in `styles.css` with tokens
only. The look is the clickable mock-up's (`mockup-models-clickable.html`). Why: one look
with the launch window and the project page (LAD-176's remarks, the human's remarks #2949).

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

### D15. After the human's manual check

- The page's lines name no command: `Refused` and `ProbeError` carry `page` and `page_hint`
  (None: the command's), `model_check.Verdict` a refusal's `page`; `model_entries` answers
  them, the CLI prints `str(exc)` and `hint` as before. `probe(key_where=…)` says where the
  UI takes a key (`enter it in Key`; a saved server's `Change sets its key`).
- A model removed (its tick or Remove) offers Undo for `UNDO_MS`: `POST /api/models` with
  its name, CLI, model and server, so the add's checks run again.
- Remove of a server sends the models it named (`confirmed`); D7.
- The plain-http warning before Add: `POST /api/model-servers/check` (D1's table).
- Names on a server several CLIs suit say their CLI; D4.

Why: the human's manual check of the page (#2935: the three choices by the recommendation).

### D16. The page after the human's UI remarks

The human's twelve remarks on the built page (#2949) and their answers (#2950: a clickable
mock-up first; #2969: 1A, 2A, 3A) change the page, not the core's rules or the commands.

1. **Tabs, not two blocks one above the other.** Your models and Add models are tabs of the
   section, the first named with the number of models. A tick then adds no row above the
   pointer; the number in the tab is the only thing that changes outside the list. The
   other layout weighed (sources above, Your models under them) is in the mock-up too; it
   keeps both in sight but puts the human's models under a long list. Why: remarks 2, 11.
2. **One tick per model; Run in for a server.** A model entry stays "how to run an agent":
   CLI, the CLI's model, server (#2969, 1A; the concept's Q3a). A server's columns of CLIs
   give way to one tick and a choice Run in above the list; a second CLI for the same
   server model is the command's (`lado model add`). Why: remark 5, the human's answer.
3. **Model id only where a list is not whole** (#2969, 2A): Claude Code (its aliases are its
   only list; it takes full ids LADO cannot check), a CLI whose `model_list` gives `models
   is None`, a server whose probe gives no list. Codex, Kilo, OpenCode and a server with a
   list have none: their checks refuse a name outside the list. Why: remarks 1, 6.
4. **Embeddings hidden and counted** (#2969, 3A): `ProbeInfo.embeddings` is not listed; a
   line counts them. Why: remark 9.
5. **The form checks as the human types.** `POST /api/model-servers/check` takes the name,
   the address, `key_typed` and the key only after Check key; it runs `check_name`, the
   name taken, `server_to_add`'s same-address notes, the plain-http warning and the probe
   (`model_servers.probe`, the command's: 5 s a request); `kind` comes back in `ProbeInfo`.
   The page sends it `MODEL_DEBOUNCE` after the last keystroke and drops an answer to an
   older request. Add stays the command's probe and save: a server that changed between the
   check and Add is refused at Add. Why: remark 10; the key goes only on the human's act.
6. **Nothing moves under the pointer.** The anchor `#models` scrolls the page once, when it
   opens, never after a reload of the entries (the cause of remark 11: `scrollIntoView` on
   every change of the entries while the hash was `#models`). A removal keeps its row's
   height as the Undo row; a server added takes the form's place; a server removed leaves a
   one-line row; a confirmation and Change open under their row. A list's order is set at
   reading, never by a tick. Why: remarks 2, 11.
7. **Rename on the name itself.** The name is a button with a frame on hover and the title
   `Click to rename`; the field fills the cell; Enter or blur saves, Esc restores; no ✎, no
   Save/Cancel. Why: remark 3.
8. **A list's height is bounded**: about nine rows, scrolled within; search above ten
   models; the configured ones first. Why: remark 4.
9. **The row of a source**: the whole row toggles, a framed arrow turns; `<n> added`, then
   the login state or the address, cut with `…` and whole in the title; the buttons never
   wrap (a grid of the row and its buttons; under 600 px the buttons get a line of their
   own). Why: remarks 8, 12.
10. **Run in is a `.field` select** of the launch window's size and font. Why: remark 7
    (the CLI choice of Other model… inherited the browser's font).
11. **A server removed is not undone**: its key file goes with it, and LADO keeps no copy of
    a key; the confirmation says so. Models removed one by one keep their Undo.

## Risks / Trade-offs

- Opening a server's source takes up to ~10 s for one that hangs: the source says
  `reading the models…` and the rest of the page stays usable.
- A tick shown from a list read seconds ago may meet a server changed since: ticking probes
  again and a refusal shows in the tick's row.
- The form's check probes a server while the human types: at most one check runs at a
  time per form and an older answer is dropped; a slow server shows `checking …` up to the
  command's time.
- An Undo row of a model removed by its tick is in Your models, not in Add models; the tick
  itself undoes it there.
- A change made from the CLI while the page is open shows on the next opening.
- `default_name` makes long names on servers with long model ids; the name is cut to 64
  characters and can be renamed.
