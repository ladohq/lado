## Context

A session (`state.Session`, table `sessions`, schema 36 on the epic branch) has a
provider, a permission mode, kits and switched-off items; nothing of a model. A launch is
`base.Launch` from `Provider.launch_command(agent, session, spec)`, called by
`runtime._launch_command`, which records `Launch.model`/`effort` with `state.set_model`.
The agent-model capability gives every agent a model and an effort with a source (`cli`,
`cli-config`), `state.source_words`, `state.report_model` for what a CLI names in its
events, and the API's `ModelInfo`.

What each CLI takes and lists: proposal, Why. The human's answers (question #2471): the
mockup as drawn, the words `chosen for the session`, a provider change drops the model,
a resume keeps it unless given, OpenCode's and Kilo's own list commands, the model shown
on the agents only.

## Goals / Non-Goals

Goals: one model per session, reaching every agent of its CLI by the CLI's own way,
checked before the start, visible with its source; stored in the format later tables
reuse. Non-goals: the proposal's Out of scope.

## Decisions

### D1. The power table is one JSON column of `sessions`

`sessions.power TEXT` (NULL: no table); `SCHEMA_VERSION = 37`, `MIGRATIONS[36] =
["ALTER TABLE sessions ADD COLUMN power TEXT"]`; `tests/agent_helpers.previous_schema`
undoes it. The document: `{"light": {"cli": "codex", "model": "gpt-5.6-sol"}, "normal":
{...}, "heavy": {...}}`. In `state.py`: `LEVELS = ("light", "normal", "heavy")`,
`DEFAULT_LEVEL = "normal"`, `@dataclass(frozen=True) PowerRow(cli: str, model: str)`,
`PowerTable(rows: dict[str, PowerRow])` with `single(cli, model)` (all three rows),
`row(level=DEFAULT_LEVEL)`, `to_json()` and `from_json(text)`; `Session.power: PowerTable
| None = None`, read and written by `add_session`, `resume_session` and the session
reader. A row has no effort key yet: effort adds one, as levels add tables, in the same
format. Why JSON rather than rows (proposal, options): the coming user and project tables
live outside `sessions` (a settings store, the project's files), where a document travels
as it is.

### D2. The source `session`

`state.SESSION = "session"`, `MODEL_SOURCES[SESSION] = "chosen for the session"`. The
other CLI's note is no new token: the source `cli` with the detail `the session's model
<model> is for <CLI title>` (D5). `Choice.name` becomes `str | None`, so a launch can
record a source and a detail with no name.

### D3. The rule above the providers: which agent gets the model

`runtime.session_model(sess, agent_cli) -> tuple[str | None, str | None]`: the `normal`
row's model when its CLI is `agent_cli.name`, else None and, when there is a table, the
note of D5. `_spec` puts the model into `AgentSpec.model: str | None = None` (new field);
providers apply it and know nothing of tables. Used for the supervisor (start, resume)
and every worker (`spawn_worker`, run workers through it).

### D4. Each provider's way

A provider that applies `spec.model` returns `Launch.model = Choice(spec.model, SESSION)`.

- Claude Code: `--model <model>` on the command line. `--model` wins over the user's
  settings and `ANTHROPIC_MODEL`, and is what the smoke test reads; LADO's `--settings`
  file stays as it is. The model name is no secret, so the command line may show it.
- Codex: in the agent's config.toml, `model = <model>` at the top level and, when the
  carried `profile` names a table of the carried `profiles`, in that table too: Codex
  takes the profile's value over the top level's (`_setting`'s rule). The carried effort
  stays with `cli-config`. The user's `~/.codex/config.toml` is read only, as today.
- OpenCode and Kilo (`opencode_family`): `config["model"] = spec.model` in the dict that
  becomes `OPENCODE_CONFIG_CONTENT` / `KILO_CONFIG_CONTENT`. Kilo's card shows the model
  from the launch even when its plugin names none.
- The fake provider: `FAKE_AGENT_MODEL=<model>` in its launch environment, so the fake
  agent reports it back (agent-model's fake-agent hook) and integration tests see the
  whole path.

### D5. An agent of another CLI

When `session_model` gives a note (the row's CLI is not the agent's), runtime records
`Choice(None, CLI_DEFAULT, note)` for an agent whose launch set no model (a Codex worker
with a carried model keeps `cli-config`; the note is then only the warning), and adds
`<agent> runs on <CLI title>'s default model: the session's model <model> is for <row
CLI title>` to the launch's warnings: `spawn_worker` returns it in its warnings and
writes it to loop.log, as other launch warnings. The supervisor never meets this: a
provider change drops the table (D8).

### D6. Reported models (state.report_model)

`report_model` takes one more argument, `same: Callable[[str, str], bool]`, the agent's
provider's `same_model(chosen, reported)` (default: equality; `hooks.handle` passes the
provider's). For the model pair: a reported name equal to the stored one changes nothing;
a stored name None takes the reported name and keeps source and detail; `same(stored,
reported)` replaces the name and keeps source and detail; anything else replaces the name
with the source `cli` and no detail (as today). Claude Code's `same_model`: the chosen
name is one of its aliases and the reported name, without a `[1m]` suffix, starts with
`claude-<alias>-` (`opus` → `claude-opus-5-5`); the aliases that name no family
(`default`, `best`, `opusplan`) match any `claude-` name. The effort pair is unchanged.

### D7. The check: `model_check.py` and `Provider.model_list`

`base.ModelList(aliases: tuple[str, ...], models: tuple[str, ...] | None, command: str,
why: str = "")`: `models` None means no list, with `why`. `Provider.model_list(env) ->
ModelList` (default: no aliases, no list, why "LADO knows no list of this CLI's models").
`base.MODEL_LIST_TIMEOUT = 15` seconds for a list command, run with the agents'
environment (`agents_env`), as a login status is.

- Claude Code: the aliases its help names, checked by hand against the installed version
  (`fable`, `opus`, `sonnet`, `haiku`, `default`, `best`, `opusplan`, each also with
  `[1m]`), no list, why "Claude Code gives no list of models beyond its aliases".
- Codex: no aliases; with the carried model provider OpenAI's (`_model_provider`), the
  slugs of `codex debug models --bundled` (JSON, `models[].slug`) and of the user's
  `$CODEX_HOME/models_cache.json` when it reads; else no list, why "Codex CLI gives no
  list of models for the model provider `<name>`". Command named: `codex debug models`.
- OpenCode / Kilo: no aliases; the lines of `opencode models` / `kilo models` (stdout,
  one `provider/model` a line). Command named: that one.
- The fake provider: the list from `FAKE_AGENT_MODELS` (comma-separated) of the agents'
  environment, none when unset.

`model_check.check(provider, model, env) -> Verdict(kind, text)` with kinds `default`
(empty model), `ok` (an alias or in the list: `an alias of <title>` / `in <title>'s list
of models`), `warn` (no list: `<why>: LADO cannot check <model>; a wrong name stops its
agents at their first turn`) and `refused` (`<model> is not in <title>'s list of models;
<command> prints the list`). The one rule; the CLI, the API and the UI show its text.

### D8. Start and resume

`runtime.start_session(..., model: str | None = None)`: None keeps (a resume) or none (a
new session); "" drops; a name makes `PowerTable.single(provider, name)`. A resume whose
provider changes and gives no model drops a table of another CLI. The check (D7) runs
for a given non-empty model, after the provider is resolved and before the session is
stored: `refused` raises `LadoError` with its text (nothing stored); `warn` goes to
`started.warnings` and loop.log. `_changes` adds `model: <cli> <model> -> CLI default`
(and the reverse, or one model to another) with `CLI default` for none.

### D9. CLI

`lado start --model MODEL`: help "the model for the session's agents of its provider's
CLI, an alias or a name of the CLI's list (checked before the start); '' on a resume goes
back to the CLI's default; without it, a resume keeps the session's". `cmd_start` passes
it through, prints the warnings as today.

### D10. API

- `Launch.model: str | None`, `Resume.model: str | None` (None keeps, "" drops).
- `SessionInfo.model: str | None`: the `normal` row's model (its CLI is the session's
  provider, D8), for the Resume window.
- `GET /api/providers/{name}/models?model=<text>` → `ProviderModels(aliases: list[str],
  models: list[str] | None, why: str, check: ModelCheck(kind, text))`, the agents'
  environment as `POST /api/sessions` uses it. The server keeps each provider's
  `ModelList` for 60 seconds in memory, so typing re-checks without re-running the CLI.
- `make web-types` regenerates `web/openapi.json` and `web/src/api.gen.ts`.

### D11. UI (`Launch.tsx`)

As the approved mockup (`mockup-session-model.html`): in Advanced, before Switch off, a
`.field` Model, an `<input list>` with a `<datalist>` of the aliases then the models, a
placeholder `<CLI title>'s default`, and one `.field-note` from `check`: `default` muted
(`empty: <title>'s default model; type or pick one of its models`), `ok` `.ok` with ✓,
`warn` `.warn` with ⚠, `refused` `.bad`; Start off while `refused` or while the check of
the typed text is under way. The summary: `Advanced: model, switch off agents, skills,
MCP servers or flows`; folded with a model, `Advanced: model <model>` with the model in
`launch-first-peek`. The check is asked when the provider or the text changes, the latter
after 300 ms of no typing. Changing the provider empties the field; Resume fills it from
`SessionInfo.model` and sends `model` only when it changed ("" when emptied). No new CSS.

### D12. Migration number

37 while main has 35 and the epic branch 36. At each merge of the base, the developer
compares `SCHEMA_VERSION` with `origin/main`'s and moves this step's migration after any
main gained (`SCHEMA_VERSION`, `MIGRATIONS`, `previous_schema`, the migration test).

## Risks / Trade-offs

- A list command costs a process per check (Kilo about 1.7 s here): the server's 60 s
  cache and the 300 ms pause bound it; `lado start` runs it once.
- Codex's bundled catalogue can lag behind the account's; the account's cache covers a
  model the account has used Codex with. A model in neither is refused although the
  server might take it: the refusal names `codex debug models`, which refreshes it.
- Kilo's `kilo models` refreshes its gateway's list over the network itself (accepted by
  the human, #2471); offline it answers from its cache.
- Claude Code's full names always warn: it gives no list; the aliases do not.
- A `/model` typed in a terminal shows only at the CLI's next event naming the model
  (agent-model, as before).

## Migration Plan

Schema 36 → 37 adds a nullable column: old sessions have no table and start as before.
`lado update`'s rollback restores `lado.db` from its backup; an older LADO on schema 37
refuses with `state.SchemaError` as today (the migration test checks it, nothing changes
there).
