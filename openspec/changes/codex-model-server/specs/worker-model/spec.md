## MODIFIED Requirements

### Requirement: list_models shows the supervisor what can run

The supervisor, read-only or not, SHALL have an MCP tool `list_models` with an optional `provider`,
giving for each installed agent CLI, the session's first, or for that `provider` alone: `starts_on`
(what a worker of it starts on with no `model`), its built-in models, its external models with
their servers' saved names and `blocked` (why one cannot start), and `note` (why it has no full
list). It SHALL ask no server and hold no key or address. A worker SHALL NOT have the tool.

#### Scenario: A Claude session with a model for OpenCode
- **WHEN** `Локальная Qwen` on `LM Studio дома` is ticked for OpenCode and the supervisor of a
  Claude Code session calls `list_models`
- **THEN** the first entry is Claude Code's with its aliases and a `note` that it gives no full list,
  and OpenCode's entry has `Локальная Qwen` with the server `LM Studio дома` and `blocked` null

#### Scenario: A silent server
- **WHEN** `LM Studio дома` does not answer and the supervisor calls `list_models`
- **THEN** it answers at once with `Локальная Qwen`, and no request reaches a server

#### Scenario: An external model of a CLI that runs on no server
- **WHEN** an external model on LM Studio is ticked for Codex
- **THEN** its `blocked` says the server does not suit Codex CLI, and why

#### Scenario: One CLI
- **WHEN** the supervisor calls `list_models(provider="kilo")`
- **THEN** the result holds Kilo CLI alone

#### Scenario: A CLI not installed
- **WHEN** Codex is not installed
- **THEN** `list_models` leaves it out, and `list_models(provider="codex")` fails with `Codex CLI is
  not installed`

#### Scenario: What starts with no model
- **WHEN** a session's table names OpenCode's `Локальная Qwen` and Kilo CLI has no default
- **THEN** OpenCode's `starts_on` is `Локальная Qwen` and Kilo CLI's is null

#### Scenario: A worker asks
- **WHEN** a worker calls `list_models`
- **THEN** it is refused as an unknown tool

### Requirement: A spawn checks the worker's model as a start does

Before anything of the worker exists, `spawn_worker` SHALL check the model its worker starts on,
given, the session's or the default, as a start does: an external model's server by the probe of
saving a model, within its timeout, a built-in model against its CLI's list. The probe SHALL come
after any list a name needs to find its CLI. A refusal of a model not given SHALL name `list_models`
and `model=""`. A worker with no model SHALL ask nothing.

#### Scenario: The server does not answer
- **WHEN** the supervisor calls `spawn_worker(model="Локальная Qwen")` and `LM Studio дома` does not
  answer
- **THEN** it fails with `http://localhost:1234 does not answer (<why>); LADO cannot check qwen3-8b`,
  the probe within its timeout, after the lists of the other CLIs when the session's CLI lacks the
  name, and no worker, branch, worktree or window exists

#### Scenario: The session's server went silent
- **WHEN** a session runs on `Локальная Qwen`, its server stops, and the supervisor spawns a worker with
  no `model`
- **THEN** it fails with the same reason, adding `list_models shows the others, model="" is the CLI's
  own settings`

#### Scenario: The session's table cannot be read
- **WHEN** the session's table cannot be read and the supervisor spawns a worker with no `model`
- **THEN** it fails with `the session's model cannot be read`, adding `list_models shows the others,
  model="" is the CLI's own settings`, and `spawn_worker(model="")` starts the worker

#### Scenario: A worker of a run refused
- **WHEN** that happens for a run's waiting step
- **THEN** the step still waits for a worker, and a later `spawn_worker(run=...)` takes it

#### Scenario: The model is gone from the server
- **WHEN** the server answers and its list lacks `qwen3-8b`
- **THEN** it fails with `qwen3-8b is not in LM Studio дома's list of models; lado model-server probe
  http://localhost:1234 prints the list`

#### Scenario: Nothing chosen
- **WHEN** a session has no table, the CLI no default and no `model` is given
- **THEN** no server is asked and no list is read

#### Scenario: Claude Code on an external model
- **WHEN** the supervisor calls `spawn_worker(model="Шлюз Opus")`, which is Claude Code's, on `Шлюз`
- **THEN** `Шлюз` is asked, and the worker starts on it

#### Scenario: Codex on an external model
- **WHEN** the supervisor calls `spawn_worker(model="Шлюз GPT")`, which is Codex's, on `Шлюз`
- **THEN** `Шлюз` is asked, and the worker starts on it
