## Context

An agent's record (`state.Agent`, table `agents`, schema 35) has its role, provider,
status, branch and run, nothing of its model. Status comes from hooks: a provider's
`parse_event(native, payload)` turns a native hook input into a neutral `base.Event`, and
`hooks.handle` acts on its `kind`. A launch is `base.Launch` (argv, env, warnings), made by
`Provider.launch` in `runtime._launch_command` before the window opens.

What each CLI gives (proposal, Why): Codex's hook inputs carry `model` (all events LADO
uses; no effort); Claude Code's SessionStart carries `model` in the interactive mode,
nothing about effort was seen; the OpenCode family's `chat.message` gets the user message
whose `model` is `{providerID, modelID, variant}`, and LADO's plugin already runs a hook
command for it. Codex's agents carry `model` and `model_reasoning_effort` from the user's
config (`CARRIED`), with `profile`/`profiles`.

The UI's agents are `AgentInfo` (`server/models.agent_info`), sent by `GET` and by the
change feed, which records any update of an `agents` row except one that changes only
`seen_at` (`state.AGENTS_CHANGED`).

## Goals / Non-Goals

Goals: every agent's model and effort, and where they came from, in `lado.db`, MCP, API,
UI and `lado ls`; a shape later ways of choosing a model extend by values only.

Non-goals: see the proposal's Out of scope.

## Decisions

### D1. Six columns of `agents`, one migration

`model TEXT`, `model_source TEXT NOT NULL DEFAULT 'cli'`, `model_detail TEXT`, `effort
TEXT`, `effort_source TEXT NOT NULL DEFAULT 'cli'`, `effort_detail TEXT`; `SCHEMA_VERSION
= 36`, `MIGRATIONS[35]` six `ALTER TABLE agents ADD COLUMN`; `tests/agent_helpers` undoes
it (`previous_schema`). `state.Agent` gets the same six fields (defaults None / `"cli"`).
Why columns, not one JSON column: the journal, `lado ls` and tests read them plainly, and
later sources are new values in the same columns. Model and effort have separate sources
because they come from different places already (Codex: effort from the config, model
from the CLI) and will more (a session's model over a config's effort).

### D2. Source tokens and their words in one place

`state.MODEL_SOURCES = {"cli": "CLI default", "cli-config": "your {cli} config"}`, tokens
as constants `state.CLI_DEFAULT = "cli"`, `state.CLI_CONFIG = "cli-config"`, and
`state.source_words(source, detail, cli_title) -> str`: the words, then `, <detail>` when
there is one; an unknown token (a newer LADO's row) is shown as the token itself. The API
and `list_agents` give the token and the detail; the API adds the words (D6), so the UI
holds no table of its own. The detail is free text the source writes (`profile work`).

### D3. A launch says what it set up

`base.Launch` gets `model: Choice | None = None` and `effort: Choice | None = None`, with
`state.Choice(name: str, source: str, detail: str | None = None)` (in `state.py`, which
`base` imports and whose `set_model` takes it). `runtime` writes them
into the agent's record right after `_launch_command`, before the window opens
(`state.set_model(session, agent, model, effort)`), for the supervisor and for workers.
None leaves `cli` and no name. Codex's `launch` fills them from the carried config by the
profile rule: a helper `_carried(config, key) -> (value, profile_name | None)` beside
`_model_provider`, whose rule it shares (the profile's value, else the top level's); the
detail is `profile <name>` when the profile gave it. Only a value that is carried (kept by
`_keep`) counts.

### D4. Events carry the model

`base.Event` gets `model: str = ""` and `effort: str | None = None` (None: the event says
nothing of the effort; "": the model runs its default effort, no name). Providers fill
them:

- Codex: `data.get("model")` for every event it parses (strings only).
- Claude Code: `data.get("model")` for SessionStart, both as SESSION_START and as
  CONVERSATION_START (the `/clear` and resume switch).
- OpenCode family: the plugin's `chat.message` payload gets `model` (`providerID/modelID`
  of `output.message.model`) and `variant`; `parse_event` puts them into `model` and
  `effort`; a model with no variant gives the effort "", as OpenCode drops the variant
  when the human picks the model's default one. No new hook or event: the existing
  `chat.message` carries two more fields.
- The fake provider reads `model` and `effort` from its payload; the fake agent puts
  `FAKE_AGENT_MODEL` / `FAKE_AGENT_EFFORT` of its environment into its session-start and
  prompt-submit payloads.

### D5. hooks.handle records a reported model first

Before acting on `event.kind`, after `state.seen`, `hooks.handle` calls
`state.report_model(session, agent, event.model, event.effort)` when either is set. In
one transaction it reads the row and writes only what changes: a reported name equal to
the current one changes nothing; a different one replaces the name, and when the current
source is not `cli`, sets the source to `cli` and the detail to NULL. A model "" or an
effort None leaves its pair alone; an effort "" clears the name, as a different one would. No write when nothing changes, so the journal and the UI get no
empty update. A failure there is logged like any hook error and does not stop the status
handling (wrapped as the rest of `main`).

### D6. The API's shape

`server/models.ModelInfo(name: str | None, source: str, detail: str | None, words: str)`;
`AgentInfo.model: ModelInfo`, `AgentInfo.effort: ModelInfo`. `words` from
`state.source_words` with the provider's title (`providers.get(name).title`, the
provider's own name when it is not installed or unknown). `make web-types` regenerates
`web/openapi.json` and `web/src/api.gen.ts`.

### D7. list_agents gives flat fields

`list_agents` entries add `model`, `model_source`, `model_detail`, `effort`,
`effort_source`, `effort_detail` as stored; its docstring names the model and effort. An
agent reads tokens, not words.

### D8. The UI

`Agents.tsx`: the head line `role · provider · <model name or "CLI default model">`; in
`agent-facts`, first, `Model` and `Effort`: the name in `<code>` then ` · <words>` muted,
or only the words muted when there is no name. `Team.tsx` `AgentTip`: the model's name
after the provider when it has one. No new CSS beyond a muted span (`.muted` exists).

### D9. lado ls

After the time column, before the branch: the model's name or `-`, padded like the other
columns (`{model:<18}`), a longer name is printed whole.

## Risks / Trade-offs

- Claude Code names its model only at SessionStart: a `/model` typed in its terminal
  shows at the next SessionStart (compaction, resume). Accepted: no terminal reading.
- Kilo's bundle could not be read in this run: if its `chat.message` user message lacks
  `model`, Kilo agents show "CLI default" with no name, which is true and loud enough; the
  plugin's node test and the smoke run of Kilo in CI catch a crash, not a missing name.
- A hand-edited Codex config with a non-string `model` is not carried by `_keep` and so
  not shown.

## Migration Plan

Schema 35 → 36 adds nullable or defaulted columns: old rows read as `cli` with no names.
`lado update`'s rollback restores `lado.db` from its backup; an older LADO meeting schema
36 refuses with `state.SchemaError` as today (checked by the migration test, not changed).

The epic ships in 0.45.0 and 0.44.0 is released from main without it; the epic's
migrations are numbered after 0.44.0's. Main has schema 35 now, so 36 fits. Each time the
base is merged into the run's branch, the developer compares `SCHEMA_VERSION` with
main's: when 0.44.0 or a fix of its RC added a migration to main, this step's migration
moves to the next free number (`SCHEMA_VERSION`, `MIGRATIONS`, `previous_schema`, the
migration test).
