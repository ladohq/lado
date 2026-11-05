## MODIFIED Requirements

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
