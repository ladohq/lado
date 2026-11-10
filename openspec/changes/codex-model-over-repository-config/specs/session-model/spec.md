## MODIFIED Requirements

### Requirement: Each agent of the session's CLI starts on the session's model

Every agent of the `normal` row's CLI, but a worker with a `model`, SHALL start on its model
through its CLI's own way, never through the user's global config: Claude Code by `--model`, Codex
by `model` in its own `CODEX_HOME`'s config.toml (top level and carried profile) and by `-m`,
OpenCode and Kilo by `model` in their config content and by `--model`. Its record SHALL have that
model with the source `session` from its launch on; a CLI's default goes so with `default`.

#### Scenario: A Claude Code agent
- **WHEN** a session's table names `claude` and `opus` and its supervisor is launched
- **THEN** its command line has `--model opus`, and its model is `opus` with the source
  `session`

#### Scenario: A Codex agent with a carried profile
- **WHEN** the user's Codex config has `profile = "work"` with `[profiles.work] model =
  "gpt-5.5"`, and a session's table names `codex` and `gpt-5.6-sol`
- **THEN** the agent's config.toml has `model = "gpt-5.6-sol"` at the top level and in
  `[profiles.work]`, its command line has `-m gpt-5.6-sol`, the user's file is unchanged, and the
  agent's model is `gpt-5.6-sol` with the source `session` while its carried effort keeps the
  source `cli-config`

#### Scenario: An OpenCode or Kilo agent
- **WHEN** a session's table names `kilo` and `anthropic/claude-sonnet-5-5`
- **THEN** the agent's `KILO_CONFIG_CONTENT` has `"model": "anthropic/claude-sonnet-5-5"`, its
  command line has `--model anthropic/claude-sonnet-5-5`, and its model is that name with the source
  `session`, also while Kilo has reported no model

#### Scenario: No model chosen
- **WHEN** a session has no table and its CLI no default
- **THEN** no launch passes a model of LADO's choice (a Codex agent passes the model carried from
  the user's Codex config as `-m`), and every agent's model has the source it had before this
  change (`cli`, or `cli-config` for a model carried from the user's Codex config)

#### Scenario: Kilo remembers another pick
- **WHEN** the human's last `/model` pick in Kilo is another model and a session on Kilo has a model
- **THEN** the agent starts on the session's model
