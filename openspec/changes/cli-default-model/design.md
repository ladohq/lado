## Context

The epic branch has `state.py` schema 38 (`models` keyed by `folded`, `server` nullable, no id),
`model_settings.py` (`check_model`, `add_model`, `default_name`, `remove_models`, `remove_server`),
`model_check.py`, `server/model_entries.py`, `server/launch.py` (`model_list`, a CLI's list kept
a minute), `Provider.model_list` (`base.run_list` with its timeout), and the page in
`web/src/ModelSettings.tsx` and `web/src/ModelSources.tsx`. No session reads the entries.

The human's answers: the concept's decisions; #3358 (the command's form, the question before
removing a default, a background read only for a built-in default, a card of a CLI not
installed); #3395 (one block). The mock-up, its spec and critique: the flow run
`ui-design/model-picker`. Plan: `docs/superpowers/plans/2026-11-05-cli-default-model.md`.

## Goals / Non-Goals

Goals: the store keeps external models only; a default per CLI as a model reference; one
computed list; one picker. Non-goals: the proposal's Out of scope.

## Decisions

### D1. The schema

`SCHEMA_VERSION = 39`. `models` is rebuilt, `MIGRATIONS[38]` as a list of statements: rename to
`models_38`, create the new table, copy the rows with a server, drop the old one, create
`cli_defaults`.

```sql
CREATE TABLE IF NOT EXISTS models (
    id TEXT PRIMARY KEY,               -- never changes: references hold it
    folded TEXT NOT NULL UNIQUE,       -- name.casefold()
    name TEXT NOT NULL,
    cli TEXT NOT NULL,
    model TEXT NOT NULL,
    server TEXT NOT NULL REFERENCES model_servers(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS cli_defaults (
    cli TEXT PRIMARY KEY,
    model_id TEXT REFERENCES models(id),  -- external
    builtin TEXT,                         -- built-in: the CLI's name for it
    CHECK ((model_id IS NULL) != (builtin IS NULL))
);
```

An id is `lower(hex(randomblob(6)))` in the migration and `uuid.uuid4().hex[:12]` in the core,
as a server's. `MIGRATIONS[37]` keeps schema 38's table under a name of its own
(`MODELS_TABLE_38`), since `tests/agent_helpers.schema_before` asserts that step. The way back:
`lado update`'s rollback restores `lado.db` from its backup, an older LADO refuses a newer
database. The rows dropped are the human's stand only (the epic branch), so no note in the
release. No ON DELETE CASCADE: the core clears a default in the transaction that removes the
model, and the foreign key refuses a stray delete loudly.

### D2. A model reference

`state.ModelRef(cli, model_id: str | None, builtin: str | None)`, the one form the next changes
take. `state.cli_defaults()`, `state.set_cli_default(ref)`, `state.clear_cli_default(cli)`. An
external reference's CLI is the entry's: the core refuses another.

### D3. The full list in the core

`model_settings.choices(provider, listing, saved=None) -> Choices(aliases, models, why, external:
list[ConfiguredModel], other_name: bool, read_again: bool)`: `other_name` is `models is None`,
`read_again` is `not ModelList.fixed`: a provider marks a list that cannot change (Claude Code's
aliases, Codex on another model provider), which a timeout's shape cannot be told from. `listing`
is a callable, so the server passes `launch.model_list` (kept a minute, `fresh`). In the core, not
in the API, because a later MCP tool needs the same list: one source. No new wait:
`base.run_list`'s timeout stands.

### D4. Setting a default

`model_settings.set_default(cli, name, env) -> tuple[ModelRef, Verdict | None]`
resolves as the delta says: the CLI known, installed (`shutil.which(provider.command,
path=env["PATH"])`), an entry of this CLI, the list read for the clash, a built-in, another
CLI's entry, then `model_check.verdict`. `set_default_ref(ref, env, listing)` is the page's
form, by id or built-in name. `clear_default(cli) -> bool`. The list is read for an external
name too, only to find the clash; when it cannot be read there is no clash to find.

### D5. Removing

`state.remove_model` and `remove_model_server_with_models` delete the default in the same
transaction and report the cleared CLIs; `model_settings.remove_models(names, removed, cleared)`,
`remove_server(…, cleared=…)`; `cli.py` prints the lines. The default of a model added to the
server after the question is cleared too: the server's `confirmed` check guards the models, and
they carry their defaults. The page asks from the `defaults` of its last listing.

### D6. The API

| Route | Body | Answer |
|---|---|---|
| `GET /api/model-settings` | | `ModelSettings{models, servers, defaults: [CliDefault]}` |
| `GET /api/providers/{name}/model-choices?model=&fresh=` | | `ModelChoices{aliases, models, why, external: [ConfiguredModelInfo], other_name, whole_process, read_again, check}` |
| `PUT /api/model-defaults/{cli}` | `ModelDefaultSet{external: str \| None, builtin: str \| None}` | `ModelDefaultSaved{settings, check}` |
| `DELETE /api/model-defaults/{cli}` | | `ModelSettings` |

`CliDefault{cli, external: str | None, builtin: str | None, name, model, server: str | None,
whole_process}`: the card says it with no list read, as opening the page reads none for an
external default. `ModelChoices.check` is the core's verdict on the built-in `model`: the card's
warning and a lost default come from it, no line is rebuilt on the page.
`ConfiguredModelInfo` gains `id`; `ModelAdd.server` is required. Refusals are `EntryRefused`.
The typed check of `Other name…` is the existing `GET /api/providers/{name}/models?model=`.
`DELETE /api/models/{name}` and the server's stay; the page compares `defaults` for its lines.

### D7. Which CLI's external model takes the whole process

`Provider.external_whole_process: bool = True`, `False` in `opencode_family.py`. A fact of the
provider, read by the API (`whole_process`): the page names no CLI (neutral core).

### D8. What is read when

Opening the section reads the lists of CLIs with a built-in default, one `model-choices` each in
the background, stale answers dropped by `latest`; no server is asked (#3358). Opening a picker
reads the CLI's list `fresh` and probes each server of that CLI's models once, in the
background (`POST /api/model-servers/{name}/probe`, the route the sources use). A warning from a background read grows the card;
`useScrollAnchor` holds what the human acts on.

### D9. The picker

`web/src/ModelPicker.tsx`, props `cli`, `value`, `where: "settings"`; the launch window's and the
power row's forms are added with their change (only what is used). The list is `position: fixed`
by the field's box, measured on `visualViewport`, so no card or dialog cuts it. Plain rows, no
virtual list: 321 rows draw at once and the search filters in place; a list past 1000 is
another question. Rows, order and sizes: the mock-up's spec §2, §7-§9, in the order YOUR MODELS before BUILT-IN: with Kilo CLI's 321 models the
external ones would sit behind them. This differs from the concept's order, and the human saw it
(#3395).

### D10. Order and folding of a card's models

The default first, the others by name ignoring case, folded to five above five (the mock-up's
spec §1a): the critic's open finding F23 saw section 15's sample rows out of that order; the
spec's text stands and the sample is only a sample. The fold is a page state, kept in
`ModelSettings` by CLI, so a reload of the entries keeps it.

### D11. Undo

Undo of a default's × is `POST /api/models` then `PUT /api/model-defaults/{cli}` with the new id.
A second call refused leaves the model back and shows the refusal in the row. Two calls reuse two
routes; an `as_default` on `ModelAdd` would be a field for one caller.

### D12. What leaves the code

`CliModels`, `CliSource`, `YourModels`, `EMPTY`, `EMPTY_HOW`, `CLIS_LEAD`, the CLI branch of
`SourceBody` and `goneOf`; the alias branch of `default_name`; the no-server branch of
`check_model` and `add_model`, its thresholds now reached through `model_check.verdict` in
`set_default`.

## Risks / Trade-offs

- The page shows external models on Claude Code and Codex CLI before a session can run them; the
  whole-process line says what they do, and the later change refuses at start. One release.
- `Removing` a default whose page is stale clears it without the question; the line after it
  says so. Accepted: a race of two windows.
- A background read per built-in default costs up to one `kilo models` per opening, kept a
  minute.
