## ADDED Requirements

### Requirement: Every agent has a model and an effort, each with its source

LADO SHALL keep for every agent in `lado.db` its model and its effort, each a name or
none, each with a source and an optional detail. A source SHALL be one of a set of tokens
that later ways of choosing a model extend without changing the shape: `cli` (the CLI's
own choice: its default or its own settings) and `cli-config` (the user's config of the
CLI, carried by LADO into the agent). An agent whose CLI has said nothing and for which
LADO chose nothing SHALL have no name and the source `cli`.

#### Scenario: A new Claude agent before its first hook
- **WHEN** a Claude agent is spawned and no hook of it has run yet
- **THEN** its model and its effort have no name and the source `cli`

#### Scenario: Agents of an older LADO after the migration
- **WHEN** `lado.db` of schema 35 holds agents and LADO migrates it to schema 36
- **THEN** each of those agents has no model name, no effort name and the source `cli` for both

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

When an event names a model that differs from one chosen by a source other than `cli`,
LADO SHALL set the model's source to `cli` and clear its detail: the CLI runs another
model than the one chosen.

#### Scenario: Codex runs the carried model
- **WHEN** a Codex agent's model is `gpt-5.6-sol` from `cli-config` and its Stop input has
  `model` `gpt-5.6-sol`
- **THEN** its model stays `gpt-5.6-sol` with the source `cli-config`

#### Scenario: The model was changed in the CLI
- **WHEN** a Codex agent's model is `gpt-5.6-sol` from `cli-config` and its next
  UserPromptSubmit input has `model` `gpt-5.5`
- **THEN** its model is `gpt-5.5` with the source `cli` and no detail

### Requirement: list_agents and the API give each agent's model and effort

`list_agents` SHALL give each agent `model`, `model_source`, `model_detail`, `effort`,
`effort_source` and `effort_detail`. The API's agent (`AgentInfo`, also in the agents
feed) SHALL give `model` and `effort`, each with its name, source, detail and the words
the UI shows for its source.

#### Scenario: list_agents of a Codex worker
- **WHEN** an agent calls `list_agents` in a session with a Codex worker whose model is
  `gpt-5.6-sol` from `cli-config` with the detail `profile work`
- **THEN** the worker's entry has `model` `gpt-5.6-sol`, `model_source` `cli-config` and
  `model_detail` `profile work`

#### Scenario: The API's words for a source
- **WHEN** the UI reads the agents of that session
- **THEN** the worker's `model` has the source words `your Codex config, profile work`, and
  an agent with no name has `CLI default`

### Requirement: The agent's page, the Team tooltip and lado ls show the model

The agent's page SHALL show the model's name in its head line after the role and the
provider ("CLI default model" when it has none) and the facts Model and Effort, each its
name and its source's words. The Team chip's tooltip SHALL add the model's name when it
has one. `lado ls` SHALL show the model's name, or `-`, after the agent's time.

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
