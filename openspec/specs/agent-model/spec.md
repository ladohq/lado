# agent-model Specification

## Purpose
The model and the effort each agent runs on, and where each came from: kept in `lado.db`
with a source token and a detail, learnt from the CLI's own events and, for Codex, from
the user's config LADO carries into the agent, and shown by `list_agents`, the API, the
agent's page, the Team tooltip and `lado ls`.

## Requirements

### Requirement: Every agent has a model and an effort, each with its source

LADO SHALL keep for every agent in `lado.db` its model and its effort, each a name or none, each
with a source and an optional detail. A source SHALL be one of a set of tokens that later ways
extend: `cli`, `cli-config`, `session`, `default` (in words `default in Settings`), `supervisor` (in
words `chosen by the supervisor`) and `cli-changed` (in words `changed in the agent CLI`). An agent whose CLI has said nothing and for which LADO chose
nothing SHALL have no name and the source `cli`.

#### Scenario: A new Claude agent before its first hook
- **WHEN** a Claude agent is spawned in a session with no model and no hook of it has run
  yet
- **THEN** its model and its effort have no name and the source `cli`

#### Scenario: Agents of an older LADO after the migration
- **WHEN** `lado.db` of schema 35 holds agents and LADO migrates it to schema 36
- **THEN** each of those agents has no model name, no effort name and the source `cli` for both

#### Scenario: An agent on the session's model
- **WHEN** a Codex agent starts in a session whose model is `gpt-5.6-sol`
- **THEN** its model is `gpt-5.6-sol` with the source `session`, and its page reads Model
  `gpt-5.6-sol · chosen for the session`

#### Scenario: An agent on the CLI's default
- **WHEN** a Codex agent starts in a session with no table and Codex's default is `gpt-5.6-sol`
- **THEN** its page reads Model `gpt-5.6-sol · default in Settings`

#### Scenario: A worker on a model the supervisor chose
- **WHEN** the supervisor spawns a Claude worker with `model="sonnet"`
- **THEN** its model is `sonnet` with the source `supervisor`, and its page reads Model `sonnet · chosen
  by the supervisor`

### Requirement: A Codex agent shows the model and effort carried from the user's config

When LADO carries `model` or `model_reasoning_effort` from the user's Codex config into a
Codex agent's config, the agent's model or effort SHALL be that value with the source
`cli-config`, read by Codex's rule: the value of the profile named by `profile` when that
profile has it, else the top level's. The detail SHALL name the profile when the value
came from one.

#### Scenario: A profile's model
- **WHEN** the user's `~/.codex/config.toml` has `profile = "work"`, `model = "gpt-5.5"`
  and `[profiles.work] model = "gpt-5.6-sol"`, `model_reasoning_effort = "high"`, and a
  Codex agent is spawned
- **THEN** its model is `gpt-5.6-sol` and its effort `high`, both with the source
  `cli-config` and the detail `profile work`

#### Scenario: No model in the user's config
- **WHEN** the user's Codex config names no model and no effort
- **THEN** the Codex agent's model and effort have no name and the source `cli` until its
  CLI names the model

### Requirement: The model a CLI names in its events becomes the agent's model

When a hook or plugin event of an agent names the model it runs (Codex's hooks, Claude
Code's SessionStart, the OpenCode family's `chat.message`), LADO SHALL take that name as
the agent's model, and the OpenCode family's variant as its effort, learning it from
events only, never from the agent's terminal. A name equal to the one the agent has SHALL
change nothing.

#### Scenario: Claude Code names its default
- **WHEN** a Claude agent's SessionStart input has `model` `claude-opus-5-5`
- **THEN** its model is `claude-opus-5-5` with the source `cli`

#### Scenario: OpenCode names its model and variant
- **WHEN** an OpenCode or Kilo agent's `chat.message` has the model `anthropic` /
  `claude-sonnet-5-5` with the variant `high`
- **THEN** its model is `anthropic/claude-sonnet-5-5` and its effort `high`, both with the
  source `cli`

#### Scenario: An event without a model
- **WHEN** an agent's event names no model
- **THEN** its model, effort and their sources stay as they were

### Requirement: A model named with no variant runs the CLI's default effort

When the OpenCode family's `chat.message` names a model with no variant, the agent's
effort SHALL have no name and the source `cli`: OpenCode drops the variant when the human
picks the model's default one, so the variant chosen before no longer holds.

#### Scenario: OpenCode goes back to the model's default variant
- **WHEN** an OpenCode or Kilo agent's effort is `high` and its next `chat.message` has the
  model `anthropic` / `claude-sonnet-5-5` with no variant
- **THEN** its effort has no name and the source `cli`, and the page reads `CLI default`

### Requirement: A reported model that differs from the chosen one is the CLI's

When an event names a model that differs from the one the agent has, LADO SHALL set the model's
source to `cli-changed` and clear its detail: the CLI runs another model. A name the agent's CLI
gives to the chosen one (Claude Code's full name of the alias it was started with) SHALL replace
the name and keep the source and the detail. A name reported for an agent that has none SHALL keep
the source and the detail it has.

#### Scenario: Codex runs the carried model
- **WHEN** a Codex agent's model is `gpt-5.6-sol` from `cli-config` and its Stop input has
  `model` `gpt-5.6-sol`
- **THEN** its model stays `gpt-5.6-sol` with the source `cli-config`

#### Scenario: The model was changed in the CLI
- **WHEN** a Codex agent's model is `gpt-5.6-sol` from `cli-config` and its next
  UserPromptSubmit input has `model` `gpt-5.5`
- **THEN** its model is `gpt-5.5` with the source `cli-changed` and no detail

#### Scenario: Claude Code names the alias's model
- **WHEN** a Claude agent's model is `opus` from `session` and its SessionStart input has
  `model` `claude-opus-5-5`
- **THEN** its model is `claude-opus-5-5` with the source `session`

#### Scenario: Claude Code runs another model than the alias
- **WHEN** that agent's model is `claude-opus-5-5` from `session` and its next
  SessionStart input has `model` `claude-sonnet-5-5`
- **THEN** its model is `claude-sonnet-5-5` with the source `cli-changed` and no detail

### Requirement: list_agents and the API give each agent's model and effort

`list_agents` SHALL give each agent `model`, `model_source`, `model_detail`, `effort`,
`effort_source` and `effort_detail`, `model` being the saved name of an external model. The API's
agent (`AgentInfo`, also in the agents feed) SHALL give `model` and `effort`, each with its name,
source, detail and the words the UI shows for its source, and for an external model its saved name,
its server's name and address.

#### Scenario: list_agents of a Codex worker
- **WHEN** an agent calls `list_agents` in a session with a Codex worker whose model is
  `gpt-5.6-sol` from `cli-config` with the detail `profile work`
- **THEN** the worker's entry has `model` `gpt-5.6-sol`, `model_source` `cli-config` and
  `model_detail` `profile work`

#### Scenario: The API's words for a source
- **WHEN** the UI reads the agents of that session
- **THEN** the worker's `model` has the source words `your Codex config, profile work`, and
  an agent with no name has `CLI default`

#### Scenario: An external model
- **WHEN** an agent runs on `Локальная Qwen`
- **THEN** `list_agents` gives `model` `Локальная Qwen`, and the API's `model` adds the server's name
  and address, never its key

### Requirement: The agent's page, the Team tooltip and lado ls show the model

The agent's page SHALL show the model's name in its head line after the role and the
provider ("CLI default model" when none) and the facts Model and Effort, each its name and its
source's words; an external model's fact SHALL read `<name> · <model> · server <server>,
<address> · <source's words>`, without `<model> · ` when it is the name ignoring case. The Team
chip's tooltip SHALL add the model's name when it has one. `lado ls` SHALL show the model's
name, or `-`, after the agent's time.

#### Scenario: A Codex agent on its page
- **WHEN** the human opens the page of a Codex agent whose model is `gpt-5.6-sol` and
  effort `high`, both from `cli-config` with the detail `profile work`
- **THEN** its head line reads `developer · codex · gpt-5.6-sol`, Model reads
  `gpt-5.6-sol · your Codex config, profile work` and Effort reads
  `high · your Codex config, profile work`

#### Scenario: A CLI that has named nothing yet
- **WHEN** the human opens the page of a Kilo agent whose CLI has reported nothing
- **THEN** its head line ends with `CLI default model`, and Model and Effort read
  `CLI default`

#### Scenario: lado ls
- **WHEN** a session has a Claude supervisor whose model is `claude-opus-5-5` and a worker
  whose CLI has named no model, and the human runs `lado ls`
- **THEN** the supervisor's line has `claude-opus-5-5` and the worker's line has `-` after
  their times

#### Scenario: An external model on the page
- **WHEN** the human opens the page of an OpenCode agent on `Локальная Qwen`, chosen for the session
- **THEN** its head line ends with `Локальная Qwen`, and Model reads `Локальная Qwen · qwen3-8b ·
  server LM Studio дома, http://localhost:1234 · chosen for the session`

#### Scenario: An external model named by its id
- **WHEN** the human opens the page of a Kilo agent on `qwen3.8-27b`, the model `qwen3.8-27b` on
  `LM Studio` at `http://localhost:1234`, Kilo CLI's default model
- **THEN** Model reads `qwen3.8-27b · server LM Studio, http://localhost:1234 · Kilo CLI's default
  model`

### Requirement: LADO's model is known by its provider id

A model an OpenCode or Kilo agent reports as `lado-<server id>/<model>`, from the launch or from a
switch through `/model`, SHALL count as that server's model: `list_agents`, `lado ls`, the API and
the agent's page SHALL name its saved name, or its id when no entry of that CLI has it. A server
removed since SHALL leave the name as the CLI gives it. Two entries may hold one model of a server:
an agent SHALL keep the name it started on until its CLI changes the model, in its config too.

#### Scenario: A switch through /model
- **WHEN** an OpenCode agent on `Локальная Qwen` reports `lado-<id>/qwen3-coder-30b`, saved as
  `Рабочая Qwen` on `LM Studio дома`
- **THEN** its page reads Model `Рабочая Qwen · qwen3-coder-30b · server LM Studio дома,
  http://localhost:1234 · changed in the agent CLI`

#### Scenario: Two entries of one model
- **WHEN** an agent runs on `Локальная Qwen` and the human saves `Новая Qwen`, the same model on the
  same server
- **THEN** its page still names `Локальная Qwen`

#### Scenario: A renamed model
- **WHEN** the human renames that model while the agent runs
- **THEN** the page shows the new name at its next read

#### Scenario: Kilo has reported nothing
- **WHEN** a Kilo agent started on `Qwen в Kilo` and has reported no model
- **THEN** its page reads as for OpenCode, from LADO's record

### Requirement: An agent's popup names its model without effort or source

An agent's popup in the session's head and on the terminals' strip SHALL have the fact Model: a
configured model's saved name, else the name the CLI reported, else `CLI default`. It SHALL name
neither the effort nor a source; those stay on the agent's page.

#### Scenario: The model in the head's popup
- **WHEN** the human holds the pointer over the avatar of a Codex agent on `gpt-5.6-sol`, effort
  `high`, both from its Codex config, of an OpenCode agent on `Локальная Qwen`, and of a Kilo
  agent whose CLI has named nothing
- **THEN** their popups' Model reads `gpt-5.6-sol`, `Локальная Qwen` and `CLI default`, and none
  names the effort or a source
