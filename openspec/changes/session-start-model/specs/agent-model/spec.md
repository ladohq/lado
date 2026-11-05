## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Every agent has a model and an effort, each with its source

LADO SHALL keep for every agent in `lado.db` its model and its effort, each a name or none, each
with a source and an optional detail. A source SHALL be one of a set of tokens that later ways
extend: `cli`, `cli-config`, `session`, `default` (in words `default in Settings`) and `cli-changed`
(in words `changed in the agent CLI`). An agent whose CLI has said nothing and for which LADO chose
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
provider ("CLI default model" when it has none) and the facts Model and Effort, each its
name and its source's words; an external model's fact SHALL read `<saved name> · <model> · server
<server>, <address> · <source's words>`, and its saved name stand in the head line. The Team chip's
tooltip SHALL add the model's name when it has one. `lado ls` SHALL show the model's name, or `-`,
after the agent's time.

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
