# Settings → Models: Implementation Plan

**Goal:** in Settings → Models the human opens a source (an agent CLI or a saved model
server), sees its models read now and ticks them; ticked models are configured models,
named by default, renamed in place, removed; servers are added, changed and removed with
their models, under the commands' rules and lines; the key goes into the API and never out.

**Architecture:** the core (`model_settings.py`, `model_servers.py`, `state.py`) marks each
refusal with its field and gets `check_model`, `default_name`, `rename_model` and removing a
server with its models; `cli.py` gets `--with-models`, `doctor.py` a line for a model its
server no longer lists; a new `server/model_entries.py` holds the API's logic and the kept
probes, called by thin routes in `server/app.py`; `server/launch.py` reads a CLI's list
`fresh` on request; the page is `web/src/ModelSettings.tsx` (section, Your models, add
server) and `web/src/ModelSources.tsx` (sources, ticks), on the existing components.

**Tech Stack:** Python 3.10+ standard library, FastAPI and pydantic, React + TypeScript
(Vite, vitest), Playwright, pytest (unit `-n auto`, integration `-m integration`, UI `-m
ui`), `tests/fake_model_server.py`.

**Spec:** `openspec/changes/model-settings-page/` (proposal, deltas `model-settings-page`
and `model-servers`, design.md D1-D14) and
`docs/superpowers/specs/2026-11-03-model-settings-page-design.md`; the mock-up is the run's
artifact `mockup-models-sources.html`; the cases are the epic's `ux-models-cases`.

## Global Constraints

- No new Python or npm dependency; no schema change (the models' id comes with the first
  reference, D8); no provider change; nothing above `providers/` names a provider.
- Every refusal text is the core's, verbatim; the page adds no text to a refusal.
- UI texts exact as in the delta: `Your models`, `Sources`, `No models yet. Without them
  each agent runs on its CLI's default model. Tick models in Sources below.`, `not
  installed`, `not logged in`, `reading the models…`, `↻ Refresh`, `+ Add server`,
  `checking the server…`, `Saved model server "<name>".`, `same address as model server
  "<name>"`, `(embeddings)`, `not in the server's list`, `not in <CLI title>'s list`, `not in
  <source>'s list of models`, `<CLI title> is not installed`, `Other model…`, `Change`, `New
  key`, `Remove <name>?`, `Remove <name> and its <n> models: <name>, <name>?`.
- CLI texts exact: the refusal's hint `or remove them with it: lado model-server remove
  "<name>" --with-models`; doctor's `model "<name>" (<model>) is not in <server>'s list of
  models`.
- The key: only in `ModelServerAdd.key` (POST body); in no answer, log, error journal,
  change feed, `lado.db` or file of `LADO_HOME` but `model-servers/<id>/key`; in the page
  only in its `SecretField`, emptied after a send, on Cancel and when the form closes.
- A probe from the page takes no longer than the command's (5 s per request, two waves).
- `make web-types` after any API model change; commit `web/openapi.json` and
  `web/src/api.gen.ts`.
- CHANGELOG.md: one line under `## 0.45.0 (unreleased)`, `### New`.
- No step numbers of the epic, no link to `docs/epics/` in code, docs or specs.
- Unit suites with `-n auto`; integration files with `-m integration`; UI files with `-m
  ui`; single node ids with `-n0`.

## Review Focus

- A tick that lies: after a refused tick, a removed model, a rename, or a model added from
  the CLI meanwhile, the tick must follow `ModelSettings.models` re-read after each change
  (Task 7 vitest: tick → refusal → tick off; remove in Your models → tick off).
- A default name that collides three times or exceeds 64 characters with its suffix (Task 2:
  `default_name` with a 70-character model id on a server and three takers).
- A server opened twice quickly, or closed while its probe runs: the late answer must not
  fill a closed source or overwrite a newer read (Task 7: the latest request wins, as
  `Providers.tsx` does).
- The key in a 422, an `EntryRefused`, the server log or the journal (Task 5 canary, Task 4
  unit).
- Removing a server whose models change between the confirmation and the DELETE: the core
  removes what refers to it at that moment, in one transaction (Task 3 unit with a model
  added after the listing).

---

### Task 1: Refusals with their field, `check_model`, the empty key, the list's why (D2, D3, D9, D11)

**Files:** modify `src/lado/model_settings.py`, `src/lado/model_servers.py`,
`src/lado/cli.py` (`_server_key` relies on `check_key` for the empty key); test
`tests/test_model_settings.py`, `tests/test_model_servers.py`; the CLI tests stay green
unchanged.

**Interfaces (produces):** `Refused(text, hint="", field="")`, `ProbeError(text, hint="",
field="")`; `check_model(name: str | None, cli, model, server_name, env, *, probe=None) ->
Checked` with `Checked(provider, model: str, server: state.ModelServer | None, verdict:
model_check.Verdict, aliases: tuple[str, ...])`; `add_model` = `check_model` + save;
`check_key("")` raises `Refused("the key is empty", field="key")`.

- [ ] Tests first: one per raise site asserting `exc.field` (the list is design.md D2);
  `test_check_model_runs_add_models_checks` (same text and field for every refusal case,
  nothing saved on success, the verdict `add_model` returns);
  `test_check_model_uses_the_probe_given` (a stub probe: the fake server gets no request);
  `test_versioned_list_has_no_why` (profile `anthropic-versioned`: models `claude-x`, why
  `""`; a 500 both ways keeps `GET /v1/models: 500`).
- [ ] Implement; `uv run pytest -n auto tests/test_model_settings.py
  tests/test_model_servers.py tests/test_cli_model_settings.py tests/test_cli_model_server.py`.
- [ ] Commit `Refusals of model settings name their field, and a model's check runs without
  saving (LAD-187)`.

### Task 2: Default names and renaming (D4, D8)

**Files:** modify `src/lado/model_settings.py`, `src/lado/state.py`; test
`tests/test_model_settings.py`, `tests/test_state.py`.

**Interfaces (produces):** `default_name(provider, model, server: state.ModelServer | None,
aliases: tuple[str, ...]) -> str`; `add_model(name: str | None, …)` names a model
`default_name` when `name` is None; `state.rename_model(name, new) -> bool` (`NameTaken` on a
clash); `model_settings.rename_model(name, new) -> state.ConfiguredModel` (Refused: no such
model, field `""`; the new name by `check_name`, field `name`; taken, field `name`, the
model's name-taken line).

- [ ] Tests first: `Claude Sonnet` for Claude Code's `sonnet`; `Claude Sonnet[1m]` for
  `sonnet[1m]`; `gpt-5-codex` for a Codex model of its list (a fake provider with no
  aliases); `qwen3-8b · LiteLLM` on a server; taken → `qwen3-8b · LiteLLM · Codex CLI`, then
  `(2)`, `(3)`; a 70-character model id on a server gives a name of 64 characters ending in
  its suffix; taken compared ignoring case. Rename: to a new name; to the same name in
  another case (allowed: itself); to another's name (refused, nothing changes); to an empty
  or 65-character name (refused); unknown model.
- [ ] Implement (`UPDATE models SET name = ?, folded = ? WHERE folded = ?`); run the two
  files with `-n auto`; commit `Configured models get a default name and are renamed in
  place (LAD-187)`.

### Task 3: A server removed with its models (D7)

**Files:** modify `src/lado/state.py`, `src/lado/model_settings.py`, `src/lado/cli.py`,
`docs/cli.md`; test `tests/test_state.py`, `tests/test_model_settings.py`,
`tests/test_cli_model_server.py`, `tests/integration/test_model_settings_process.py`.

**Interfaces (produces):** `state.remove_model_server(id, with_models=False) -> list[str]`
(the names of the models removed, in name order; `sqlite3.IntegrityError` without
`with_models` while a model refers to it); `model_settings.remove_server(name, *,
with_models=False, removed: Callable[[str], None] = lambda _: None) -> str`.

- [ ] Tests first: the refusal's text as before and its hint naming `--with-models`; with
  it, each model removed and reported, then the server and its key folder; a model added
  between a listing and the removal is removed too (one transaction); `lado model-server
  remove lms --with-models` prints `Removed model "coder-oc".`, `Removed model "sp".`,
  `Removed model server "lms".` and exits 0; the integration file gets the same case
  against the fake server in its own process.
- [ ] Implement; `docs/cli.md` names `--with-models`; run the unit files with `-n auto` and
  `uv run pytest -m integration -n auto tests/integration/test_model_settings_process.py`;
  commit `lado model-server remove --with-models removes a server with its models (LAD-187)`.

### Task 4: doctor names a model gone from its server (D12)

**Files:** modify `src/lado/doctor.py`, `docs/cli.md`; test `tests/test_doctor.py`.

- [ ] Test first: `Локальная Qwen` (`qwen3-8b`) on a fake server that lists only
  `gemma-3-12b` → `[WARN] Model servers:` holds `model "Локальная Qwen" (qwen3-8b) is not in
  LM Studio дома's list of models`, exit status as without it; a server with no list or not
  answering names no model so.
- [ ] Implement in `probed` (models on the server from `state.models()`); run; commit
  `lado doctor names a configured model its server no longer lists (LAD-187)`.

### Task 5: The API (D1, D5, D9, D10)

**Files:** create `src/lado/server/model_entries.py`; modify `src/lado/server/app.py`
(routes, `SECRET_ROUTE`), `src/lado/server/models.py` (`ModelSettings`, `ModelServerInfo`,
`ConfiguredModelInfo`, `ProbeInfo`, `CliApi`, `ModelServerAdd`, `ModelServerAdded`,
`ModelAdd`, `ModelAdded`, `ModelRename`, `EntryRefused`; `ModelCheck` gets `field: str =
""`), `src/lado/server/launch.py` (`provider_models(…, fresh=False)`); regenerate
`web/openapi.json`, `web/src/api.gen.ts`; test `tests/test_server_model_settings.py` (new),
`tests/test_server_providers.py` (`fresh`).

**Interfaces (produces):** `model_entries.listing()`, `add_server(given)`,
`probe_server(name)`, `remove_server(name, with_models)`, `check_model(given)`,
`add_model(given)`, `rename_model(name, given)`, `remove_model(name)`, `KEPT = 60`; each
refusal raised as `model_entries.Refusal(EntryRefused)`, turned into a 400 by `app.py`; the
routes of design.md D1.

- [ ] Tests first (in-process fake model server, temp `LADO_HOME`):
  `test_listing_empty_makes_no_db`; `test_listing_asks_no_server`;
  `test_add_server_lmstudio` (kind, embeddings, CLIs); `test_add_server_same_address_note`;
  `test_add_server_plain_http_warning` (an unreachable `.invalid` host with a key: the
  warning in the refusal's `warnings`); `test_add_server_refusals_carry_fields` (closed port
  → `address`, `forbidden` without key → `key`, taken → `name` with no request);
  `test_change_keeps_key_on_null`; `test_change_writes_new_key`; `test_empty_key_refused`;
  `test_unreadable_body_on_secret_route_repeats_nothing`; `test_probe_route_keeps_probe`;
  `test_check_model_ok_warn_refused` (200 each, nothing saved, `field` on the refusal);
  `test_check_model_keeps_probe_a_minute` (monkeypatched clock; `POST /api/models` probes
  again); `test_add_model_default_name`; `test_rename_model_route`;
  `test_remove_server_with_models_route`; `test_remove_model_route`;
  `test_provider_models_fresh_skips_kept_list`.
- [ ] Implement (kept probes in a dict under a `threading.Lock`, keyed `(id, address)`,
  failures not kept); `uv run pytest -n auto tests/test_server_model_settings.py
  tests/test_server_providers.py tests/test_server_*.py`; `make web-types`; commit with both
  generated files `The API of Settings → Models (LAD-187)`.

### Task 6: The key canary through a real server

**Files:** create `tests/integration/test_model_settings_canary.py`.

- [ ] A real `lado server` (as `tests/integration/test_project_secrets_canary.py` starts
  one) and the fake model server in its own process with `key=` a canary (profile `all`):
  add with the key; Change with a second canary; a 422 POST with a third; an add refused by
  the probe (`forbidden`, a fourth); listing, probe, check, rename, DELETE with models.
  Assert no canary in any answer, `server.log`, the error journal, `lado.db`, any file of
  `LADO_HOME` but `model-servers/<id>/key` (holding the second until the DELETE), the change
  feed of the test's span.
- [ ] `uv run pytest -m integration -n auto tests/integration/test_model_settings_canary.py`;
  commit `The canary of a model server's key through the UI's API (LAD-187)`.

### Task 7: The page (D6, D13)

**Files:** create `web/src/ModelSettings.tsx`, `web/src/ModelSources.tsx`,
`web/src/ModelSettings.test.tsx`, `web/src/ModelSources.test.tsx`; modify
`web/src/Settings.tsx`, `web/src/paths.ts` (`MODELS_ANCHOR = "models"`), `web/src/api.ts`
(`getModelSettings`, `addModelServer`, `probeModelServer`, `removeModelServer(name,
withModels)`, `addModel`, `checkModel`, `renameModel`, `removeModel`;
`getProviderModels(…, fresh)`), `web/src/styles.css`.

**Interfaces (produces):** `export function ModelSettings()`; `export function
ModelSources({ settings, providers, logins, onChanged })`; `export function refusalOf(error:
unknown): EntryRefused | null`; `export function tickState(models, cli, model, server):
{ on: boolean; several: string[] }`.

- [ ] Vitest first, `ModelSettings.test.tsx`: section between Providers and Usage
  statistics; `#models` scrolls; the empty line; the table sorted, Source column, the `not
  installed` warning; ✎ rename → field → Save PATCHes, refusal under the field, Cancel
  restores; Remove DELETEs and the list is re-read; + Add server: `checking the server…`
  and Add disabled; refusals by `field` under Name / Address / Key, `""` under the
  buttons, warnings under Key; the key field empty after Cancel, refusal and success, the
  body holding it once; success opens the new source with `Saved model server …` and the
  notes.
- [ ] Vitest first, `ModelSources.test.tsx`: no read before a source opens; opening a CLI
  reads `getProviderModels(name, "", null, fresh=true)`, opening a server
  `probeModelServer`; `reading the models…`; Refresh reads again; the latest answer wins
  and none fills a closed source; not installed greyed and closed, not logged in marked;
  a CLI's ticks (aliases tagged `alias`); a server's columns = its `clis` ∩ installed;
  ticking POSTs `name: null`, unticking DELETEs that model; several models → tick on,
  disabled, title naming them; search above more than ten models; embeddings greyed and
  disabled; a saved model missing from the list first, ticked, marked; a server that does
  not answer shows the line, its hint and its models; Other model… note after
  `MODEL_DEBOUNCE` from `checkModel`, Add POSTs; Change with empty New key sends `key:
  null, replace: true`; Remove with models asks `Remove LiteLLM and its 3 models: …?` and
  DELETEs with `with_models`.
- [ ] Implement; `make web`; commit `Settings → Models: your models and their sources
  (LAD-187)`.

### Task 8: UI e2e

**Files:** create `tests/ui/test_models_section.py`.

- [ ] With the `server` fixture, `tests/fake_model_server.py` (`lmstudio`, and a closed
  port) and a fake `claude` on the server's PATH printing a version:
  `test_first_open` (empty line, CLIs, Kilo greyed, no request to the fake);
  `test_tick_claude_sonnet` (open Claude Code, tick `sonnet`, `Claude Sonnet` in Your
  models; untick removes it); `test_add_server_and_tick` (add `LM Studio дома`, open, the
  embeddings model greyed, tick `qwen3-8b` under OpenCode, rename it `Локальная Qwen`);
  `test_refresh_and_missing` (the fake's list changed: Refresh shows the new model unticked,
  the saved one gone shows first, marked); `test_server_does_not_answer` (closed port:
  the line, the model stays); `test_refusals_under_fields` (a closed port under Address,
  boxes not overlapping the inputs); `test_change_and_remove_with_models`;
  `test_phone_width` (390 px: no sideways scroll of the page); screenshots of each state
  into `<temp dir>/lado-ui-shots/` (the `shot` fixture) for the pull request.
- [ ] `uv run pytest -m ui tests/ui/test_models_section.py`; commit `UI tests of Settings →
  Models (LAD-187)`.

### Task 9: Docs and regression

**Files:** modify `docs/design/ui.md` (Settings' sections name Models before Usage
statistics; a section `### Models` beside `### Providers and environment`: the blocks,
sources and ticks, default names, rename, servers, the routes, the key's way, the anchor),
`docs/design/modules.md` (`server/model_entries.py`; `model_settings.py`'s new functions;
`doctor.py`'s line), `AGENTS.md` (the `server/` line names `model_entries.py`),
`CHANGELOG.md` (`### New`: **Set models in Settings.** Settings → Models shows what each
agent CLI and model server offers; tick a model to save it, rename it in place; add, change
and remove servers, a server's models with it (`lado model-server remove --with-models`)).

- [ ] Write the docs true to the code; `uv run pytest tests/test_agents_md.py -n0`.
- [ ] Regression: `make lint`, `make test`, `make web`, `uv run pytest -m integration -n
  auto tests/integration/test_model_settings_canary.py
  tests/integration/test_model_settings_process.py`, `uv run pytest -m ui
  tests/ui/test_models_section.py tests/ui/test_providers_section.py`, `openspec validate
  model-settings-page --strict`, `openspec validate --specs --strict`; a trial archive on a
  copy of `openspec/` validated there, the result in the pull request's description.
- [ ] The pull request's manual check: branch, folder, `env | grep LADO_` and `unset`,
  separate `LADO_HOME` and `LADO_TMUX_SOCKET` (schema 38), `make web`, `uv run lado ui`,
  `/settings#models`, LM Studio on localhost and an outside server, the screenshots.
- [ ] Commit `Docs of Settings → Models (LAD-187)`.

### Task 10: The page after the human's UI remarks (D16)

The page of Tasks 7 and 8 is built; this task reworks it to the clickable mock-up
(`mockup-models-clickable.html`, layout 1: tabs). The core, the commands and the routes but
the form's check stay.

**Files:** modify `src/lado/server/model_entries.py` (`check_server`), `src/lado/server/models.py`
(`ModelServerCheck{name, address, key: str | None, key_typed}`, `ServerCheck`, `kind` in
`ProbeInfo`), `src/lado/server/app.py`; `web/openapi.json`, `web/src/api.gen.ts`
(`make web-types`); `web/src/ModelSettings.tsx`, `web/src/ModelSources.tsx`, `web/src/api.ts`,
`web/src/styles.css` and their vitest files; `tests/test_server_model_settings.py`,
`tests/integration/test_model_settings_canary.py`, `tests/ui/test_models_section.py`;
`docs/design/ui.md`.

**Interfaces (produces):** `checkModelServer(body: ModelServerCheck): Promise<ServerCheck>`;
`model_entries.check_server(given) -> models.ServerCheck`.

- [ ] Unit first, `tests/test_server_model_settings.py`: the check with a free name and the
  fake `lmstudio` gives `probe.kind`, its models and CLIs, no refusal; a taken name gives a
  refusal of field `name`; a closed port a refusal of field `address`; `anthropic-versioned`
  without a key a refusal of field `key` (asks for a key); `key_typed` over plain http the
  warning, no key in the request the fake records; with `key` the fake records it once;
  a second server at the address the same-address note. Implement; `make web-types`.
- [ ] The canary (`test_model_settings_canary.py`) also sends its key through the check.
- [ ] Vitest first, `ModelSettings.test.tsx`: two tabs, `Your models 4`; a card per CLI in
  the order of the sources, its models sorted by name ignoring case, a renamed one moving
  within its card only, an empty card's line and its link opening that source; the empty line's
  link opens Add models; `#models` scrolls once at mount, not after a change of the entries;
  a click on a name gives a field, Enter PATCHes, Esc restores without a request, blur
  PATCHes, a refusal stays under the field, blur then restores; × DELETEs and leaves the
  row `Removed <name>. Undo` for `UNDO_MS`, Undo POSTs it back.
- [ ] Vitest first, `ModelSources.test.tsx`: a click on the row's name toggles (and Enter);
  `<n> added`; the address in the title; ✎ and 🗑 with `aria-label`s; list, Change and
  Remove one at a time, Change's Save opening the list; ↻ above the list; a server's model
  row click (and Enter) opens its CLIs = `probe.clis` ∩ installed, each tick POSTs that CLI
  and the row says `in …`, Esc and Done close it; none → the line and no ticks; the order set at
  reading and kept across ticks; `<n> models` and `<shown> of <n> models`; no embeddings
  row, the count line; Model id for Claude Code, for a CLI with `models: null`, for a server
  with `models: null`, none for Codex with a list; the form: the check after
  `MODEL_DEBOUNCE` without the key, an older answer dropped, Add off until an ok or an
  asked key with a key typed, Check key sends the key once; Remove's question says the key
  goes and it cannot be undone; the removed server's row says `Removed … and its <n>
  models.`
- [ ] Implement to the mock-up; `make web`.
- [ ] UI e2e (`test_models_section.py`, reworked): `test_no_shift` (tick, ×, add and remove
  a server: `window.scrollY` and the acted element's top unchanged); `test_long_list` (the
  fake's profile with 323 models: the list's height bounded, the page's height grows by
  less than 400 px, search narrows); `test_rename_enter_esc`; `test_add_form_checks`
  (a closed port refused before Add, Add off; `lmstudio` ok, Add on);
  `test_phone_width` (390 px, a long address: no sideways scroll, the buttons under the
  name); screenshots for the pull request.
- [ ] `docs/design/ui.md` as built; the manual check in the pull request names the new
  steps (tabs, rename by Enter/Esc, the form's check); regression as Task 9; commit
  `Settings → Models after the human's UI remarks (LAD-187)`.

### Task 11: One word, agent CLI (D17)

**Files:** modify `src/lado/logins.py` (`SETTINGS`), `web/src/Launch.tsx` (label),
`web/src/Providers.tsx` (heading), `web/src/SystemPanel.tsx` (heading, `aria-label`),
`docker/Dockerfile`, `docker/compose.yaml` (headers), the docstrings of `doctor.py`,
`server/provider_check.py`, `server/launch.py`, `server/app.py`, `server/models.py`; the
tests that quote the old words (`tests/test_logins.py`, `tests/test_runtime.py`,
`tests/test_doctor.py`, `tests/test_cli.py`, `tests/test_server_launch.py`,
`tests/test_docker.py`, `tests/ui/test_launch.py`, `tests/ui/test_providers_section.py`, the
vitest files); docs `docs/cli.md`, `docs/install.md`, `docs/design/ui.md`,
`docs/design/agents.md`, `docs/design/modules.md`.

- [ ] Change the tests' expected texts first (`Settings → Agent CLIs and environment`, the
  heading `Agent CLIs and environment`, the label `Agent CLI`, the panel's `Agent CLIs`); a
  UI test that `/settings#providers-and-environment` still scrolls to the section; run them
  and see them fail.
- [ ] Change the labels and `SETTINGS`; `grep -rn "Providers and environment" src web/src
  docker docs/*.md docs/design` finds nothing; run the tests above, `make web`.
- [ ] Commit `The UI says agent CLI (LAD-187)`.

