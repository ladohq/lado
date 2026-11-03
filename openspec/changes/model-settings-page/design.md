## Context

The epic branch has the store and the commands of the human's model settings:
`model_settings.py` (`check_name`, `server_to_add`, `add_server(name, address, key, *,
replace, warn, note)`, `remove_server`, `add_model(name, cli, model, server_name, env)`,
`_on_server`, `remove_models`, `server_key`, `has_key`, `clis`, `Refused(text, hint)`),
`model_servers.py` (`address`, `probe(text, key, command)`, `Probe`, `ProbeError(text,
hint)`, `lines`, `clis`, `plain_http_warning`, `NOT_CARRIABLE`), `model_check.py`
(`check`, `verdict`, `Verdict`), `state.py` (`ModelServer`, `ConfiguredModel`, their reads
and writes, schema 38) and `cli.py` (`lado model-server add|list|remove`, `lado model
add|list|remove`). No API reads them. The launch window's Model field (`Launch.tsx`:
`SuggestField`, `ModelNote`, `MODEL_DEBOUNCE`, `GET /api/providers/{name}/models`) checks a
CLI's model as it is typed. A project's secrets are typed in `SecretField`
(`ProjectVariables.tsx`), sent in the body of a PUT; `server/app.py` keeps a 422 on
`SECRET_ROUTE` from repeating its body. Settings (`Settings.tsx`) is one page of sections:
Appearance, Notifications, Providers and environment, Usage statistics.

The human's answers (question #2875): the section Models in Settings with an anchor; no
server asked on opening, Check on demand; Change as `--replace`; ready-made models for
Claude Code only (haiku, sonnet, opus, one click each, Add all three); refusals as the
commands' lines; the dots field for the key; models removed one at a time; the Model
field's suggestions and live check as the launch window's, embeddings models left out of
the suggestions.

## Goals / Non-Goals

Goals: the human adds, checks, changes and removes servers and models from Settings with
the commands' rules and lines, each refusal under its field; the key goes in and never
out. Non-goals: the proposal's Out of scope.

## Decisions

### D1. The API

All under the token (`guard` for reads, `guard.changes` for changes), in a new module
`src/lado/server/model_entries.py` called by thin routes in `app.py`:

| Route | Body | Answer |
|---|---|---|
| `GET /api/model-settings` | | `ModelSettings{servers: [ModelServerInfo], models: [ConfiguredModelInfo], ready: [ReadyModel]}` |
| `POST /api/model-servers` | `ModelServerAdd{name, address, key: str \| None, replace: bool}` | `ModelServerAdded{server: ModelServerInfo, probe: ProbeInfo, notes: [str], warnings: [str], replaced: bool}` |
| `POST /api/model-servers/{name}/probe` | | `ProbeInfo` (probed now with the kept key) |
| `DELETE /api/model-servers/{name}` | | `ModelSettings` |
| `POST /api/models/check` | `ModelAdd{name, cli, model, server: str \| None}` | `ModelCheck{kind, text}` plus `field` (D3) |
| `POST /api/models` | `ModelAdd` | `ModelAdded{model: ConfiguredModelInfo, check: ModelCheck}` |
| `DELETE /api/models/{name}` | | `ModelSettings` |

`ModelServerInfo{name, address, kind, clis: [str] (titles), has_key}` (the saved row, no
request); `ConfiguredModelInfo{name, cli, cli_title, model, server: str | None}` (the
server's name); `ReadyModel{cli, cli_title, name, model}` (D7); `ProbeInfo{address,
added_scheme, kind, models: [str] | None, models_why, embeddings: [str], apis_why, clis:
[{title, api}], not_clis: [{title, api}]}`. A refusal is a 400 whose `detail` is
`EntryRefused{message, hint, field, warnings}`; an unknown server or model name on a
`DELETE` or a probe is that 400 too, with `field` `""` (the commands' own "no model server
… is saved" line). `GET` with no `lado.db` answers empty lists and makes none
(`database()`); a change makes it as the commands do. A server's name goes in the path
encoded whole (`encodeURIComponent`), as session names do.

Why: one route per command keeps "the page does what the command does" checkable; `GET`
lists without asking any server (the human's answer 2); the probe of one server is its own
route so Check and the Model field's suggestions share it.

### D2. A refusal names its field, set by the core

`model_settings.Refused` and `model_servers.ProbeError` get an attribute `field: str` (one
of `name`, `address`, `key`, `cli`, `server`, `model`, `""`), set where they are raised:

- `check_name` → `name`; the server's and model's name taken → `name`; `check_key` and
  `NOT_CARRIABLE` → `key`.
- `ProbeError`: asks for a key and refused the key → `key`; does not answer, TLS failed,
  unknown server → `address`. `model_servers.address`'s `ValueError` → `address` (the route
  maps it).
- `add_model`: the CLI unknown → `cli`; the model empty, embeddings, not in a list →
  `model`; the server not saved, speaking no API, not answering (`_on_server`'s re-raise
  of a `ProbeError`), lacking the CLI's API → `server`.
- `remove_server`, `remove_models`, the meanwhile-cases and the key file's disk errors →
  `""`.

The CLI ignores `field`: its output does not change. Why: the page shows each refusal
under its field (the human's answer 5, the task's "under the fields") without a second
copy of the rules in the API or TypeScript mapping texts to fields; texts stay the
commands' (one source of truth).

### D3. A model's check without the save

`model_settings.add_model` is split: `check_model(name, cli, model, server_name, env, *,
probe=None) -> (provider, model, server, Verdict)` runs every check of `add_model` in its
order and raises `Refused`; `add_model` calls it and saves. `probe` is a function
`(server) -> Probe` the caller may give (D4); `add_model` gives none, so the server is
probed now, as the spec requires. `POST /api/models/check` answers `check_model`'s verdict,
or its refusal as `ModelCheck{kind: "refused", text, field}` with status 200 (a check that
finds a refusal is an answer, not a failed request). Why: the live note and Add can never
disagree on a rule; only the age of a server's probe may differ (D4).

### D4. A server's probe kept a minute for the Model field

`model_entries` keeps the last `Probe` of each server by `(id, address)` for 60 seconds
(the launch window's `MODEL_LIST_KEPT`), under a lock; `POST
/api/model-servers/{name}/probe` (Check, the field's suggestions) probes now and replaces
it; `POST /api/models/check` uses a kept one or probes and keeps it; `POST /api/models`,
`POST /api/model-servers` and Change always probe now. A failed probe is not kept. Why: the
note is asked at every settled keystroke (`MODEL_DEBOUNCE`), and a probe is up to eight
requests and ~10 s; Add still checks against the server as it is.

### D5. The key's way in

The key travels only in `ModelServerAdd.key`, the body of `POST /api/model-servers`
(add and Change). `SECRET_ROUTE` also matches `/api/model-servers` so a 422 there repeats
nothing of its body. `null` is no key (add) or the kept key (Change); `""` is refused with the command's line
`the key is empty`, moved from `cli._server_key` into `model_settings.check_key` so both
share it, under `key` (the page sends `null` for an empty field).
No answer type has a key field; `EntryRefused` is built from `Refused`/`ProbeError` texts,
which never hold the key (the commands' rule). The access log has paths only. Why: the
spec's key rule and LAD-116's canary pattern; a POST body is not logged by uvicorn.

### D6. Warnings and notes of add

`add_server`'s `warn` and `note` callbacks collect into `warnings` and `notes` lists; both
go into `ModelServerAdded`, and `warnings` into `EntryRefused` too (the plain-http warning
is printed before the probe, also when it then fails). The page shows `warnings` under Key
and `notes` under the server's row. Why: the core already separates them; the page must
show them where the spec says without parsing texts.

### D7. Ready-made models are a provider's declaration

`Provider.ready_models: tuple[tuple[str, str], ...] = ()` in `providers/base.py`, each a
(name, model); `ClaudeProvider.ready_models = (("Claude Haiku", "haiku"), ("Claude Sonnet",
"sonnet"), ("Claude Opus", "opus"))`, each in `ALIASES` (a unit test holds it). `GET
/api/model-settings` lists, for each provider that declares some and whose CLI is installed
(`doctor.provider_status`, the check `/api/providers` makes, run only for these
providers), each one no saved model of that CLI has with the same model. The page adds one
with `POST /api/models` (no server); Add all three is those POSTs in order, each refusal
kept. Why: neutral core (nothing above `providers/` names Claude Code; another CLI gets
chips by declaring them); one rule of "saved" (the same CLI and model, not the name, so a
renamed copy hides the chip).

### D8. The probe's why only with no list

`model_servers.probe`: when the plain list gives none and the one asked with
`anthropic-version` gives models, `models_why` is `""`. Why: the review of the previous
change found the stale why (E1); `ProbeInfo` shows it, the CLI never did (`lines` prints it
only with no list).

### D9. The page

`web/src/ModelSettings.tsx` (new): `ModelSettings` (the section, `id="models"`,
`MODELS_ANCHOR` in `paths.ts`, scrolled to as Providers' anchor is), `YourModels` (table,
chips, the add form), `ModelServers` (rows, the add form, Change, Check, Remove). It reuses
`SecretField` (exported from `ProjectVariables.tsx`), `SuggestField`, the `.field`,
`.launch-grid`, `.field-note` classes and `useDebounced`/`MODEL_DEBOUNCE` from
`Launch.tsx`, and `messageOf`. Refusals arrive as `ApiError.detail` (`EntryRefused`) and are
put under the field `detail.field` names. Rows and notes follow Providers' `.pv` rows and
the project page's `.project-vars` table and in-row Remove. `Settings.tsx` renders it
between `Providers` and `StatisticsSetting`. CLI select options from `GET /api/providers`
(installed or not). The page reads `GET /api/model-settings` on opening and after each of
its changes; it has no change-feed event (changes made from the CLI show on the next
opening). New CSS only for what the classes lack (the row's buttons, the chips' line, the
phone layout), in `styles.css` with tokens only. Why: the human asked for the launch
window's look of fields and notes (LAD-176); reuse keeps one look.

### D10. Embeddings left out of the suggestions in the page

The page builds the Model field's suggestions from `ProbeInfo.models` minus
`ProbeInfo.embeddings`; the rule that refuses an embeddings model stays in the core (D3).
Why: a display filter on the core's own answer, not a second rule; a typed one is refused
with the core's line.

### D11. Tests

Unit: `tests/test_model_settings.py` (fields of each refusal, `check_model` equals
`add_model`'s checks), `tests/test_model_servers.py` (the why, `ProbeError.field`),
`tests/test_providers*.py` (Claude's ready models are aliases; others none), new
`tests/test_server_model_settings.py` (every route against `tests/fake_model_server.py`
in-process: answers, refusals with fields, warnings and notes, the kept probe, GET makes
no request and no lado.db, the 422 on the secret route repeats nothing). Integration: new
`tests/integration/test_model_settings_canary.py`, a real `lado server` and the fake model
server in its own process: the key canary over answers, server log, error journal and every
file of `LADO_HOME`. Vitest: `web/src/ModelSettings.test.tsx` (empty, rows, refusals under
fields, chips, Change keeps an empty key as null, the key field emptied). UI e2e: new
`tests/ui/test_models_section.py` (add a server against the fake model server, a model with
suggestions, a refusal under its field, ready-made chips with a fake Claude installed,
remove refused and done, phone width). Why: AGENTS.md's lowest layer each; the canary
crosses processes.

## Risks / Trade-offs

- A probe takes up to ~10 s on a server that hangs: Add shows `checking the server…` and
  stays disabled; the request runs in the server's thread pool.
- The refusals name CLI commands on a page (`run lado model-server add … --key`): accepted
  by the human (answer 5) as for a project's secrets.
- A server added from the CLI while the page is open shows only after reopening (no event).
- The live check may say ✓ from a probe up to a minute old while Add, probing again,
  refuses: the refusal shows under its field then.
