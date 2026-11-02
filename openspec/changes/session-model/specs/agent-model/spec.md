## MODIFIED Requirements

### Requirement: Every agent has a model and an effort, each with its source

LADO SHALL keep for every agent in `lado.db` its model and its effort, each a name or
none, each with a source and an optional detail. A source SHALL be one of a set of tokens
that later ways of choosing a model extend without changing the shape: `cli` (the CLI's
own choice: its default or its own settings), `cli-config` (the user's config of the
CLI, carried by LADO into the agent) and `session` (the session's model, chosen with
`lado start --model` or the launch window; words `chosen for the session`). An agent
whose CLI has said nothing and for which LADO chose nothing SHALL have no name and the
source `cli`.

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

### Requirement: A reported model that differs from the chosen one is the CLI's

When an event names a model that differs from one chosen by a source other than `cli`,
LADO SHALL set the model's source to `cli` and clear its detail: the CLI runs another
model than the one chosen. A name the agent's CLI gives to the chosen one (Claude Code's
full name of the alias it was started with) SHALL replace the name and keep the source
and the detail. A name reported for an agent that has none SHALL keep the source and the
detail it has.

#### Scenario: Codex runs the carried model
- **WHEN** a Codex agent's model is `gpt-5.6-sol` from `cli-config` and its Stop input has
  `model` `gpt-5.6-sol`
- **THEN** its model stays `gpt-5.6-sol` with the source `cli-config`

#### Scenario: The model was changed in the CLI
- **WHEN** a Codex agent's model is `gpt-5.6-sol` from `cli-config` and its next
  UserPromptSubmit input has `model` `gpt-5.5`
- **THEN** its model is `gpt-5.5` with the source `cli` and no detail

#### Scenario: Claude Code names the alias's model
- **WHEN** a Claude agent's model is `opus` from `session` and its SessionStart input has
  `model` `claude-opus-5-5`
- **THEN** its model is `claude-opus-5-5` with the source `session`

#### Scenario: Claude Code runs another model than the alias
- **WHEN** that agent's model is `claude-opus-5-5` from `session` and its next
  SessionStart input has `model` `claude-sonnet-5-5`
- **THEN** its model is `claude-sonnet-5-5` with the source `cli` and no detail
