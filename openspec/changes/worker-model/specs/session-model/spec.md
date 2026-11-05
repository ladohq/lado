## MODIFIED Requirements

### Requirement: An agent starts on the session's model, else its CLI's default

A worker spawned with a `model` SHALL start on it. Any other agent SHALL start on the session's
model when the table has a row of its CLI; else on its CLI's default model from Settings → Models;
else as before any model existed. This SHALL be read at each launch: a default changed later SHALL
reach the next resume and the next worker, not a running agent. The agent's model SHALL have the
source `supervisor`, `session`, `default` or `cli`.

#### Scenario: The CLI's default with no choice
- **WHEN** OpenCode's default is `Локальная Qwen` and the human runs `lado start ~/shop --provider
  opencode`
- **THEN** the session has no table, its supervisor starts on `Локальная Qwen` and its model has
  the source `default`

#### Scenario: The session's model over the default
- **WHEN** that default is set and the human starts with `--model opencode/big-pickle`
- **THEN** the supervisor starts on `opencode/big-pickle` with the source `session`

#### Scenario: A default changed before a resume
- **WHEN** a stopped session has no table, ran on `Локальная Qwen` as the default, and the human
  sets OpenCode's default to `Рабочая Qwen` and resumes it
- **THEN** the supervisor starts on `Рабочая Qwen` with the source `default`, and `lado start` and
  the session's start warnings say `changed model: Локальная Qwen -> Рабочая Qwen`

#### Scenario: A worker of another CLI with its default
- **WHEN** a session's table names `opencode` and Kilo CLI's default is `Qwen в Kilo`, and the
  supervisor spawns a worker with the provider `kilo`
- **THEN** the worker starts on `Qwen в Kilo` with the source `default`

#### Scenario: A worker's model over the session's
- **WHEN** a session's table names `opencode/big-pickle` and the supervisor spawns a worker with
  `model="Локальная Qwen"`
- **THEN** the worker starts on `Локальная Qwen` with the source `supervisor`

### Requirement: An agent of another CLI runs its own default, loudly

An agent whose provider is not the CLI of the session's `normal` row (a worker spawned
with another provider and no `model`) SHALL start on its CLI's default model from Settings → Models, else as
its CLI chooses; with no such default `spawn_worker` SHALL warn that the session's model is for the
other CLI, and the agent's model SHALL have the source `cli` with the detail `the session's model
<model> is for <CLI title>`, kept when its CLI first names a model.

#### Scenario: A Claude worker in a Codex session
- **WHEN** a session's table names `codex` and `gpt-5.6-sol` and the supervisor spawns a
  worker `w1` with the provider `claude`
- **THEN** `spawn_worker`'s warnings include `w1 runs on Claude Code's default model: the
  session's model gpt-5.6-sol is for Codex CLI`, w1's command line has no `--model`, and
  its page reads Model `CLI default, the session's model gpt-5.6-sol is for Codex CLI`

#### Scenario: The worker's CLI names its model
- **WHEN** w1's SessionStart names `claude-opus-5-5`
- **THEN** its model is `claude-opus-5-5` with the source `cli` and the same detail

### Requirement: Each agent of the session's CLI starts on the session's model

Every agent of the `normal` row's CLI, but a worker with its own `model`, SHALL start on its model
through its CLI's own way, never through the user's global config: Claude Code by `--model`, Codex by `model` in its
own `CODEX_HOME`'s config.toml (top level and carried profile), OpenCode and Kilo by `model` in
their config content and by `--model`. The agent's record SHALL have that model with the source
`session` from its launch on; a CLI's default SHALL go the same way with the source `default`.

#### Scenario: A Claude Code agent
- **WHEN** a session's table names `claude` and `opus` and its supervisor is launched
- **THEN** its command line has `--model opus`, and its model is `opus` with the source
  `session`

#### Scenario: A Codex agent with a carried profile
- **WHEN** the user's Codex config has `profile = "work"` with `[profiles.work] model =
  "gpt-5.5"`, and a session's table names `codex` and `gpt-5.6-sol`
- **THEN** the agent's config.toml has `model = "gpt-5.6-sol"` at the top level and in
  `[profiles.work]`, the user's file is unchanged, and the agent's model is `gpt-5.6-sol`
  with the source `session` while its carried effort keeps the source `cli-config`

#### Scenario: An OpenCode or Kilo agent
- **WHEN** a session's table names `kilo` and `anthropic/claude-sonnet-5-5`
- **THEN** the agent's `KILO_CONFIG_CONTENT` has `"model": "anthropic/claude-sonnet-5-5"`, its
  command line has `--model anthropic/claude-sonnet-5-5`, and its model is that name with the source
  `session`, also while Kilo has reported no model

#### Scenario: No model chosen
- **WHEN** a session has no table and its CLI no default
- **THEN** no launch passes a model, and every agent's model has the source it had
  before this change (`cli`, or `cli-config` for a model carried from the user's Codex
  config)

#### Scenario: Kilo remembers another pick
- **WHEN** the human's last `/model` pick in Kilo is another model and a session on Kilo has a model
- **THEN** the agent starts on the session's model

### Requirement: A CLI that runs on no server is refused

A start model on a server for a CLI that does not run on one yet SHALL be refused before any
request, naming the CLIs that do and that the server suits; a spawned worker SHALL be refused the
same way.

#### Scenario: Claude Code on a gateway
- **WHEN** Claude Code's default is `Шлюз Opus` on `Шлюз`, which also suits OpenCode, and the human
  starts a Claude session
- **THEN** it refuses with `Шлюз Opus is on the model server Шлюз; Claude Code does not run on a
  model server yet, Kilo CLI and OpenCode do`, adding the default's way out, and `Шлюз` is not asked

#### Scenario: A worker of that CLI
- **WHEN** the supervisor of an OpenCode session spawns a worker with the provider `claude`
- **THEN** `spawn_worker` fails with the same line, adding `list_models shows the others, model=""
  is the CLI's own settings` in place of the default's way out, and no worker exists
