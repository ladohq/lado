# Settings → Models: Implementation Plan

**Goal:** the human adds, checks, changes and removes model servers and configured models in
Settings → Models with the commands' rules and lines, each refusal under its field, the
ready-made Claude Code models one click away; a server's key goes into the API and never out.

**Architecture:** the core (`model_settings.py`, `model_servers.py`) marks each refusal with
its field and gets `check_model` (the checks of `add_model` without the save); providers
declare `ready_models`; a new `server/model_entries.py` holds the listing, the kept probes
and the conversions, called by thin routes in `server/app.py`; a new
`web/src/ModelSettings.tsx` is the section, reusing `SecretField`, `SuggestField`, the
launch window's fields and notes.

**Tech Stack:** Python 3.10+ standard library, FastAPI and pydantic (as the server has them),
React + TypeScript (Vite, vitest), Playwright (UI e2e), pytest (unit `-n auto`, integration
`-m integration`, UI `-m ui`), `tests/fake_model_server.py`.

**Spec:** `openspec/changes/model-settings-page/` (proposal, deltas `model-settings-page` and
`model-servers`, design.md D1-D11) and
`docs/superpowers/specs/2026-11-03-model-settings-page-design.md`; the mock-up is the run's
artifact `mockup-models-page.html`.

## Global Constraints

- No new Python or npm dependency; no schema change; no CLI change in output or exit codes;
  nothing above `providers/` names a provider.
- Every refusal text is the core's (`model_settings.Refused`, `model_servers.ProbeError`),
  verbatim; the page adds no text of its own to a refusal.
- UI texts exact as in the delta: `Models set once under names; sessions will refer to them
  by name. No session uses them yet.`, `Your models`, `Model servers`, `No models yet.`,
  `No servers yet.`, `+ Add model`, `+ Add server`, `checking the server…`,
  `checking the model…`, `Saved model server "<name>".`, `Remove <name>?`, `Check`,
  `Change`, `New key`, `(not installed)`, `Ready-made for <CLI title>:`,
  `+ <name> · <model>`, `Add both`, `Add all three`, `(embeddings)`, `key: yes|no`.
- The key: only in `ModelServerAdd.key` (POST body); in no answer, log, error journal,
  change feed, `lado.db` or file of `LADO_HOME` but `model-servers/<id>/key`; in the page
  only in its `SecretField`, emptied after a send, on Cancel and when the form closes.
- A probe from the page takes no longer than the command's (5 s per request, two waves).
- `make web-types` after any API model change; commit `web/openapi.json` and
  `web/src/api.gen.ts`.
- CHANGELOG.md: one line under `## 0.45.0 (unreleased)`, `### New`.
- No step numbers of the epic, no link to `docs/epics/` in code, docs or specs.
- Unit suites with `-n auto`; integration files with `-m integration`; UI files with
  `-m ui`; single node ids with `-n0`.

## Review Focus

- A refusal whose `field` is missing or wrong lands under the wrong field or nowhere: every
  `raise Refused`/`ProbeError` in the two modules has a test asserting its field (Task 1).
- The key in a 422 body, an `EntryRefused`, the server log or the journal: the canary
  (Task 4) and the 422 unit test (Task 3).
- Change with an empty New key must send `null`, never `""` (that would be refused) and
  never drop the kept key (Task 3 unit, Task 6 vitest).
- The live check and Add disagreeing on a rule: `check_model` is the only check (Task 1);
  only the probe's age differs (Task 2's kept-probe test).
- A slow or hanging server: the add form stays disabled with `checking the server…` and the
  page stays usable (Task 7 e2e with the fake's hanging profile, if the fake has one;
  otherwise a closed port).

---

### Task 1: The core: fields of refusals, `check_model`, the empty key, the list's why (D2, D3, D5, D8)

**Files:**
- Modify: `src/lado/model_settings.py`, `src/lado/model_servers.py`, `src/lado/cli.py`
  (`_server_key` uses `check_key`'s empty-key line).
- Test: `tests/test_model_settings.py`, `tests/test_model_servers.py`,
  `tests/test_cli_model_settings.py` (unchanged output).

**Interfaces:**
- Produces: `Refused(text, hint="", field="")`, `ProbeError(text, hint="", field="")`;
  fields `"name" | "address" | "key" | "cli" | "server" | "model" | ""`.
- Produces: `check_model(name, cli, model, server_name, env, *, probe=None) ->
  tuple[providers.Provider, str, state.ModelServer | None, model_check.Verdict]` (raises
  `Refused`); `probe: Callable[[state.ModelServer], model_servers.Probe] | None`.
- Produces: `add_model` = `check_model` + save, same signature and result as now.
- Produces: `check_key("")` raises `Refused("the key is empty", field="key")`.

Steps:
- [ ] Tests first: one per raise site asserting `exc.field` (name empty, too long, hidden
  char, taken for server and model; key not carriable, too large, empty; probe: does not
  answer, TLS, unknown, asks for a key, refused the key; model: unknown CLI, empty model,
  server not saved, no API, server does not answer, lacks the API, embeddings, not in the
  list; remove: unknown names, used server → `""`).
- [ ] `test_check_model_runs_add_models_checks`: for each refusal case `check_model` and
  `add_model` raise the same text and field; on success `check_model` saves nothing
  (`state.models()` empty) and returns the verdict `add_model` returns.
- [ ] `test_check_model_uses_the_probe_given`: with `probe=` a stub, no request reaches the
  fake server (its `requests` empty).
- [ ] `tests/test_model_servers.py::test_versioned_list_has_no_why`: profile
  `anthropic-versioned` → `models == ("claude-x",)` and `models_why == ""`; a 500 both ways
  keeps `GET /v1/models: 500`.
- [ ] Implement; run `uv run pytest -n auto tests/test_model_settings.py
  tests/test_model_servers.py tests/test_cli_model_settings.py tests/test_cli_model_server.py`
  → pass; the CLI tests unchanged prove no output change.
- [ ] Commit: `Refusals of model settings name their field, and a model's check runs without
  saving (LAD-187)`.

### Task 2: Ready-made models of a provider (D7)

**Files:**
- Modify: `src/lado/providers/base.py` (`ready_models: tuple[tuple[str, str], ...] = ()`),
  `src/lado/providers/claude.py`.
- Test: the providers' unit tests (`tests/test_providers*.py`, the file that tests
  `claude.ALIASES`).

**Interfaces:**
- Produces: `Provider.ready_models`; Claude's `(("Claude Haiku", "haiku"), ("Claude
  Sonnet", "sonnet"), ("Claude Opus", "opus"))`.

Steps:
- [ ] `test_ready_models_are_aliases`: every model of every provider's `ready_models` is in
  its `model_list({}).aliases` (Claude: `ALIASES`); names pass `model_settings.check_name`.
- [ ] `test_only_claude_declares_ready_models`: the other providers' are `()`.
- [ ] Implement; run the two tests with `-n0`; commit `Claude Code declares its ready-made
  models (LAD-187)`.

### Task 3: The API (D1, D4, D5, D6, D7)

**Files:**
- Create: `src/lado/server/model_entries.py`.
- Modify: `src/lado/server/app.py` (routes, `SECRET_ROUTE` adds `model-servers`),
  `src/lado/server/models.py` (`ModelSettings`, `ModelServerInfo`, `ConfiguredModelInfo`,
  `ReadyModel`, `ProbeInfo`, `CliApi{title, api}`, `ModelServerAdd`, `ModelServerAdded`,
  `ModelAdd`, `ModelAdded`, `EntryRefused`, `ModelCheck` gets `field: str = ""`).
- Regenerate: `web/openapi.json`, `web/src/api.gen.ts` (`make web-types`).
- Test: `tests/test_server_model_settings.py` (new).

**Interfaces:**
- Consumes: Task 1's `check_model`, fields; Task 2's `ready_models`.
- Produces (`model_entries`): `listing() -> ModelSettings`; `add_server(given:
  ModelServerAdd) -> ModelServerAdded`; `probe_server(name) -> ProbeInfo`;
  `remove_server(name) -> ModelSettings`; `check_model(given: ModelAdd) -> ModelCheck`;
  `add_model(given: ModelAdd) -> ModelAdded`; `remove_model(name) -> ModelSettings`;
  `KEPT = 60`; each raises `Refusal(EntryRefused)` that `app.py` turns into a 400 with that
  detail.
- Produces (routes): `GET /api/model-settings`, `POST /api/model-servers`, `POST
  /api/model-servers/{name}/probe`, `DELETE /api/model-servers/{name}`, `POST
  /api/models/check`, `POST /api/models`, `DELETE /api/models/{name}`.

Steps:
- [ ] Tests first, each with the in-process fake model server and a temp `LADO_HOME`:
  - `test_listing_empty_makes_no_db`: no `lado.db` → empty lists, still no `lado.db`.
  - `test_listing_asks_no_server`: two servers saved; GET; the fakes' `requests` empty.
  - `test_add_server_lmstudio`: `lmstudio` profile → `ProbeInfo.kind == "LM Studio"`,
    embeddings listed, `clis` Kilo CLI and OpenCode; `lado model-server list` equivalent
    (`state.model_servers()`) has it.
  - `test_add_server_same_address_note` and `test_add_server_plain_http_warning` (a key to
    `http://llm.example.com` is not sent: use an unreachable `.invalid` host; the warning is
    in the refusal's `warnings`).
  - `test_add_server_refusals_carry_fields`: closed port → `address`; `forbidden` without a
    key → `key`; name taken → `name` and the fake got no request.
  - `test_change_keeps_key_on_null` and `test_change_writes_new_key`.
  - `test_empty_key_refused`: `key: ""` → 400, `field == "key"`, `the key is empty`.
  - `test_unreadable_body_on_secret_route_repeats_nothing`: POST `/api/model-servers` with
    `{"key": "canary-…", "name": 5}` → 422 whose body lacks the canary.
  - `test_remove_server_used_names_models`; `test_remove_server_unknown`.
  - `test_check_model_ok_warn_refused`: OK on the server's list, WARN for a CLI with no
    list (the fake provider), refused with `field == "server"` for a CLI the server does not
    suit; status 200 each; nothing saved.
  - `test_check_model_keeps_probe_a_minute`: two checks → the fake got one probe's
    requests; after `KEPT` (monkeypatched clock) a new probe; `POST /api/models` probes again.
  - `test_add_model_and_remove`; `test_add_model_embeddings_refused_under_model`.
  - `test_ready_models_installed_only`: a fake `claude` on PATH printing a version → three
    ready models; one saved (`opus`, other name) → two; no `claude` → none.
- [ ] Implement `model_entries.py` (the kept probes in a dict under a `threading.Lock`,
  keyed `(server.id, server.address)`, failures not kept) and the routes; models with
  docstrings as `models.py`'s; `SECRET_ROUTE = re.compile(r"/api/((projects/[^/]+/secrets|providers/[^/]+/variables)/|
  model-servers(/|$))")`, so the old two routes still match as before.
- [ ] `uv run pytest -n auto tests/test_server_model_settings.py tests/test_server_*.py`
  → pass; `make web-types`; commit with both generated files: `The API of Settings →
  Models over the model settings (LAD-187)`.

### Task 4: The key canary through a real server (spec: "A server's key enters the API and never leaves it")

**Files:**
- Create: `tests/integration/test_model_settings_canary.py`.

Steps:
- [ ] A real `lado server` (as `tests/integration/test_project_secrets_canary.py` starts
  one, its `Api` helper pattern) and `tests/fake_model_server.py` in its own process with
  `key=` a unique canary (profile `all`): POST add with the key; POST Change with a second
  canary; a 422 POST with a third canary; an add whose probe is refused (`forbidden` with a
  wrong key, a fourth canary); GET listing, probe, check, DELETE. Assert no canary in any
  answer body, `server.log`, the error journal, `lado.db`, any file of `LADO_HOME` but
  `model-servers/<id>/key` (which holds the second canary), and the change feed read for
  the test's span.
- [ ] `uv run pytest -m integration -n auto tests/integration/test_model_settings_canary.py`
  → pass; commit `The canary of a model server's key through the UI's API (LAD-187)`.

### Task 5: The section's frame and the servers block (D9)

**Files:**
- Create: `web/src/ModelSettings.tsx`, `web/src/ModelSettings.test.tsx`.
- Modify: `web/src/Settings.tsx` (between `Providers` and `StatisticsSetting`),
  `web/src/paths.ts` (`MODELS_ANCHOR = "models"`), `web/src/api.ts` (`getModelSettings`,
  `addModelServer`, `probeModelServer`, `removeModelServer`, `checkModel`, `addModel`,
  `removeModel`, names encoded whole), `web/src/ProjectVariables.tsx` (no change: it
  already exports `SecretField`), `web/src/styles.css` (only what the classes lack: `.mm-*`
  rows' buttons, the chips' line, the phone layout).

**Interfaces:**
- Consumes: Task 3's routes and generated types; `SecretField`, `SuggestField`,
  `useDebounced`, `MODEL_DEBOUNCE`, `messageOf`, `ApiError.detail`.
- Produces: `export function ModelSettings()`; `export function refusalOf(error):
  { message: string; hint: string; field: string; warnings: string[] }`.

Steps:
- [ ] Vitest first (fake `api` as the other tests mock it): empty listing renders both empty
  lines and buttons; Settings renders Models after Providers and before Usage statistics;
  `#models` scrolls (as `Providers.test.tsx` checks its anchor); a server row shows type,
  address, CLIs, `key: no`; Add server disables Add with `checking the server…`; a refusal
  with `field: "address"` shows under Address with class `field-note bad`, `key` under Key,
  `""` under the buttons, warnings as `field-note warn` under Key; the key field is empty
  after Cancel, after a refusal and after success, and the request body had the key only
  once; Check renders models with `(embeddings)`; Change with empty New key sends `key:
  null, replace: true`; Remove asks `Remove <name>?` and the refusal names the models.
- [ ] Implement; `make web` → pass; commit `Settings → Models: the section and its model
  servers (LAD-187)`.

### Task 6: The models block and the ready-made chips (D9, D10)

**Files:**
- Modify: `web/src/ModelSettings.tsx`, `web/src/ModelSettings.test.tsx`,
  `web/src/styles.css`.

Steps:
- [ ] Vitest first: the table sorted by name ignoring case, `—` for no server; the CLI
  select lists every provider, `(not installed)` marked; the Server select `—` then the
  servers; with no server the suggestions are aliases (tag `alias`) and the CLI's list (from
  `getProviderModels`), with a server the probe's models without its embeddings; the live
  note after `MODEL_DEBOUNCE`: `✓` / `⚠` / refusal under its field, `checking the model…`
  meanwhile; Add's refusal under Name / CLI / Server / Model by `field`; a saved model's
  warning in its row; chips per ready model, a click POSTs it with `server: null`; `Add all
  three` POSTs three in order and keeps going after a refusal, which shows under the chips;
  `Add both` with two; a chip of a saved CLI+model is not shown (the server's list already
  omits it); Remove asks in the row.
- [ ] Implement; `make web` → pass; commit `Settings → Models: your models and the ready-made
  ones (LAD-187)`.

### Task 7: UI e2e of the section

**Files:**
- Create: `tests/ui/test_models_section.py`.

Steps:
- [ ] With the `server` fixture, `tests/fake_model_server.py` (`lmstudio` profile) and a
  fake `claude` on the server's PATH printing a version:
  - `test_add_server_and_model`: add `LM Studio дома` → row with `LM Studio`, the
    embeddings mark, `Saved model server …`; add model OpenCode on it, type `qwen`, see `qwen3-8b`
    and not the embeddings model among the suggestions, pick it, see `✓ in LM Studio
    дома's list of models`, Add, row in the table.
  - `test_refusals_under_fields`: a closed port under Address; Claude Code on the server (the
    `lmstudio` profile has no Messages API) under Server; the notes do not cover a field (bounding boxes do not overlap the inputs).
  - `test_ready_made_chips`: three chips; `Add all three` → three rows, no chip.
  - `test_remove_server_refused_then_done`.
  - `test_phone_width`: 390 px, fields stacked (x of Name and CLI equal), no horizontal
    scroll (`scrollWidth <= clientWidth`).
  - Screenshots of each state into `<temp dir>/lado-ui-shots/` (the `shot` fixture) for the
    pull request.
- [ ] `uv run pytest -m ui tests/ui/test_models_section.py` → pass; commit `UI tests of
  Settings → Models (LAD-187)`.

### Task 8: Docs and regression

**Files:**
- Modify: `docs/design/ui.md` (Settings' list of sections names Models before Usage
  statistics; a section `### Models` under Tasks' neighbours as `### Providers and
  environment` is written: what each block shows, the routes, the key's way, the anchor),
  `docs/design/modules.md` (`server/model_entries.py`; `model_settings.py`'s `check_model`
  and fields), `AGENTS.md` (the `server/` line names `model_entries.py`), `CHANGELOG.md`
  (`### New`: **Set model servers and models in Settings.** Settings → Models adds, checks,
  changes and removes servers and models as the `lado model-server` and `lado model`
  commands do, with the ready-made Claude Code models one click away).
- `docs/cli.md`: unchanged (no command changes); say so in the pull request.

Steps:
- [ ] Write the docs true to the code; `uv run pytest tests/test_agents_md.py -n0`.
- [ ] Regression: `make lint`, `make test`, `make web`, `uv run pytest -m integration -n auto
  tests/integration/test_model_settings_canary.py
  tests/integration/test_model_settings_process.py`, `uv run pytest -m ui
  tests/ui/test_models_section.py tests/ui/test_providers_section.py`, `openspec validate
  model-settings-page --strict`, `openspec validate --specs --strict`; a trial archive on a
  copy of `openspec/` with `openspec validate --specs --strict` there, the result in the
  pull request's description.
- [ ] The pull request's manual check: branch, folder, `env | grep LADO_` and `unset`,
  separate `LADO_HOME` and `LADO_TMUX_SOCKET` (schema 38), `make web`, `uv run lado ui`,
  `/settings#models`, adding LM Studio on localhost and an outside server, the screenshots.
- [ ] Commit `Docs of Settings → Models (LAD-187)`.
