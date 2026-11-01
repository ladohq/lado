Task: LAD-169

## Why

LADO does not know which model its agents run on: every CLI starts on its own default, and
nothing in `lado.db`, `list_agents`, the API or the UI says which one. A human cannot tell
whether an agent runs on a strong or a cheap model, and the coming work on choosing models
per session, per model server and per power table has nowhere to show its result.

What each CLI tells about its model, read in this run in the CLIs installed in LADO's
image (Claude Code 2.1.295, Codex CLI 0.162.0, OpenCode 1.18.35, Kilo 7.8.8):

- **Codex** puts `model` into the input of every hook LADO uses (SessionStart,
  UserPromptSubmit, Stop, Interrupt, PermissionRequest, PostToolUse; the hook input
  schemas in its binary). No hook says the reasoning effort. LADO carries the user's
  `model` and `model_reasoning_effort` from `~/.codex/config.toml` into each agent's
  config (`providers/codex.CARRIED`), where a chosen `profile` wins over the top level
  (`_model_provider`'s rule).
- **Claude Code** puts `model` into SessionStart's input in its interactive mode, the one
  LADO runs (checked by hand on a clean config: `claude-opus-5-5` with no setting,
  `claude-sonnet-5-5` with `--model sonnet`; at a compaction and a resume too). In
  `claude -p` it is missing. No hook said the effort in the same check, though the binary
  has an `effort` field in its common hook input for some turns.
- **OpenCode** gives its plugins' `chat.message` hook the user message, whose `model`
  holds `providerID`, `modelID` and `variant` (its reasoning variant), resolved from the
  agent's or the session's choice (read in its bundle). LADO's plugin already reports
  `chat.message`. **Kilo** runs the same plugin interface; its bundle is packed, so the
  build checks it with a test of the plugin's payload.

Root cause: the agent's record has no place for a model, the providers translate no field
of the events they already get, and the UI has nothing to show.

Options weighed:

- A (taken): an agent's model and effort, each with its source, are columns of `agents`;
  providers read them from the events LADO already gets and, for Codex, from the carried
  config at launch; everything shows them. Long-term cost: six columns and one migration;
  each later way of choosing a model adds a source value, not a column.
- B: keep the model in a JSON column of `agents`. Saves a migration later but hides the
  shape from SQL and the journal; later steps add values, not fields, so A's columns hold.
- C: ask each CLI for its model by a command or the model API. Costs a process or a
  network call per agent and reads a CLI's guess, not what the agent runs; refused by the
  task's limits (no new requests to model APIs).

## What Changes

- `agents` gets `model`, `model_source`, `model_detail`, `effort`, `effort_source`,
  `effort_detail` (schema 36); every agent so far reads as "CLI default" with no name.
- A source is a token: `cli` (the CLI's own choice, its default or its own settings) and
  `cli-config` (the user's config of the CLI that LADO carries into the agent). The detail
  says which part of it (`profile work`). Later ways to choose a model add tokens.
- At launch a Codex agent gets the model and effort of the carried config, by the profile
  rule, with the source `cli-config`.
- The events LADO gets name the model (Claude Code's SessionStart, Codex's hooks, the
  OpenCode family's `chat.message` with its variant as the effort); the agent's record
  takes the name. A reported name that differs from the one chosen at launch means the CLI
  runs another model: the source becomes `cli`.
- `list_agents` (MCP), `AgentInfo` (API, the agents feed), the agent's page in the UI
  (the head line and two facts, Model and Effort, with their source), the Team chip's
  tooltip and `lado ls` show them.
- BACKLOG.md's "Choose the model per agent" becomes a pointer to LAD-154.

## Scope

- The six columns and their migration; the source tokens `cli` and `cli-config`.
- Codex: the carried model and effort at launch; the model from every hook.
- Claude Code: the model from SessionStart (startup, compaction, resume, `/clear`).
- OpenCode and Kilo: the model and variant from the plugin's `chat.message` payload.
- The fake agent of the integration tests reports a model when told to.
- `list_agents`, `AgentInfo`, the agent's page, the Team tooltip, `lado ls`; their docs.

## Out of scope

- Choosing or passing a model or an effort to any CLI: LADO only learns and shows here;
  choosing comes with the session's model (LAD-154's later work).
- Model servers, effort as a setting, power tables: later work of LAD-154.
- Claude Code's effort: no hook reported it in this run's check; it shows "CLI default"
  until a CLI event is confirmed to carry it.
- A model change made in a CLI's own terminal (Claude Code's `/model`) shows only at the
  next event that names the model (Claude Code: the next SessionStart). LADO never reads
  the terminal (Events, not screens).
- The `spawned` event and `lado log`: they do not show the model; nothing there changes.
- The user's own Claude Code or OpenCode settings files are not read for a model: their
  CLIs report the model they run in their events, which is the truth to show.

## Impact

- Code: `state.py` (columns, migration, `report_model`, `set_model`), `providers/base.py`
  (`Event.model`/`effort`, `Launch.model`/`effort`), `providers/codex.py`,
  `providers/claude.py`, `providers/opencode_family.py`, `providers/opencode_plugin.js`,
  `hooks.py`, `runtime.py`, `mcp_server.py`, `server/models.py`, `cli.py`,
  `web/src/Agents.tsx`, `web/src/Team.tsx`, `web/openapi.json`, `web/src/api.gen.ts`.
- Tests: unit, integration with the fake agent, the plugin's node tests, the migration,
  UI e2e.
- Docs: `docs/design/agents.md`, `docs/design/ui.md`, `docs/cli.md`,
  `docs/design/modules.md`, CHANGELOG.md, BACKLOG.md.
- Version: the minor (schema migration, an MCP tool's result). The epic ships in 0.45.0;
  0.44.0 is released from main without it. The CHANGELOG line goes under
  `## 0.45.0 (unreleased)`, added on top when the target branch lacks it, above the
  0.44.0 section as that section stands there. When main, with 0.44.0 released, is merged
  into the epic branch, the 0.44.0 section and schema numbers come from main and the
  epic's sit on top of them.
- Way back: `lado update`'s rollback restores `lado.db` from its backup; an older LADO on
  schema 36 refuses it with `state.py`'s existing schema error (checked, not changed).
