## ADDED Requirements

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
- **WHEN** an external model is ticked for Claude Code
- **THEN** its `blocked` says Claude Code does not run on a model server yet

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

### Requirement: spawn_worker starts a worker on a model by name

`spawn_worker` SHALL take `model`, with or without `run`, read for the worker's CLI as `lado model
default` reads a name. The worker SHALL start on it through its CLI's own way, its record SHALL have
it with the source `supervisor`, and it SHALL go before the session's model and the CLI's default.
The session's table SHALL NOT change. With no `model` a worker SHALL start as before.

#### Scenario: A built-in model of the session's CLI
- **WHEN** the supervisor of a Claude Code session on `opus` calls `spawn_worker(model="sonnet")`
- **THEN** the worker's command line has `--model sonnet`, its page reads Model `sonnet · chosen by
  the supervisor`, and the session's model stays `opus`

#### Scenario: A worker of a run
- **WHEN** the supervisor calls `spawn_worker(run="task/x", model="sonnet")` for a step that waits
- **THEN** the worker takes the step and starts on `sonnet`

#### Scenario: The next worker
- **WHEN** a worker was spawned with a model and the next one is spawned with none
- **THEN** the next one starts on the session's model

#### Scenario: The CLI's own settings
- **WHEN** a session's table names OpenCode's `Локальная Qwen` and the supervisor calls
  `spawn_worker(model="")`
- **THEN** the worker passes no model, its source is `cli`, and no server is asked

### Requirement: A name picks the worker's CLI

With no `provider`, the worker's CLI SHALL be the session's when the name is its saved model, alias
or listed model; else the one other installed CLI that has it. A name several other CLIs have SHALL
be refused naming them. A name no CLI has SHALL be refused, and SHALL point to `list_models`. The
other CLIs' lists SHALL be read only when the session's CLI lacks the name.

#### Scenario: An external model of another CLI
- **WHEN** the supervisor of a Claude Code session calls `spawn_worker(model="Локальная Qwen")`, which
  is OpenCode's, and the server has it
- **THEN** the worker runs on OpenCode, with `Локальная Qwen` and the source `supervisor`

#### Scenario: The session's CLI goes first
- **WHEN** a built-in name is in OpenCode's list and Kilo CLI's and the session is on OpenCode
- **THEN** the worker runs on OpenCode, and Kilo CLI's list is not read

#### Scenario: Two other CLIs
- **WHEN** that name is asked for in a Claude Code session
- **THEN** `spawn_worker` fails with `<name> is a model of OpenCode and Kilo CLI; give provider`, and no
  worker exists

#### Scenario: No list has it
- **WHEN** the supervisor of an OpenCode session calls `spawn_worker(model="gpt-9")` and no list has it
- **THEN** it fails with `gpt-9 is in no agent CLI's list of models; list_models shows them`, and no
  worker, branch or worktree exists

### Requirement: A provider and a model of another CLI are refused

With a `provider`, the name SHALL be read for that CLI alone. A name that another CLI has and that
CLI lacks SHALL be refused naming both CLIs.

#### Scenario: An external model of another CLI
- **WHEN** the supervisor calls `spawn_worker(provider="kilo", model="Локальная Qwen")`, which is
  OpenCode's
- **THEN** it fails with `"Локальная Qwen" is a model of OpenCode, not of Kilo CLI`, and no worker
  exists

#### Scenario: A built-in model of another CLI
- **WHEN** the supervisor calls `spawn_worker(provider="opencode", model="sonnet")`
- **THEN** it fails with `sonnet is a model of Claude Code, not of OpenCode`

### Requirement: A free name needs an explicit provider

A name outside the aliases of a CLI with no full list, which no other CLI has, SHALL be refused with
no `provider`, saying how to give it; with an explicit `provider` of that CLI the worker SHALL start
with the warning a start gives.

#### Scenario: A typo in a Claude Code session
- **WHEN** the supervisor of a Claude Code session calls `spawn_worker(model="sonet")`
- **THEN** it fails with `sonet is in no agent CLI's list of models; list_models shows them; Claude
  Code gives no full list: provider="claude" starts it with a warning`

#### Scenario: A full name given on purpose
- **WHEN** the supervisor calls `spawn_worker(provider="claude", model="claude-opus-5-5")`
- **THEN** the worker starts on it, and `warnings` says that LADO cannot check `claude-opus-5-5`

### Requirement: A spawn checks the worker's model as a start does

Before anything of the worker exists, `spawn_worker` SHALL check the model its worker starts on,
given, the session's or the default, as a start does: an external model's server by the probe of
saving a model, within its timeout, a built-in model against its CLI's list. A refusal of a model
not given SHALL name `list_models` and `model=""`. A worker with no model SHALL ask nothing.

#### Scenario: The server does not answer
- **WHEN** the supervisor calls `spawn_worker(model="Локальная Qwen")` and `LM Studio дома` does not
  answer
- **THEN** it fails with `http://localhost:1234 does not answer (<why>); LADO cannot check qwen3-8b`,
  within the probe's timeout, and no worker, branch, worktree or window exists

#### Scenario: The session's server went silent
- **WHEN** a session runs on `Локальная Qwen`, its server stops, and the supervisor spawns a worker with
  no `model`
- **THEN** it fails with the same reason, adding `list_models shows the others, model="" is the CLI's
  own settings`

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
- **THEN** it fails with `Шлюз Opus is on the model server Шлюз; Claude Code does not run on a model
  server yet, OpenCode does`, and `Шлюз` is not asked

### Requirement: A worker's key stays in its own environment

A server's key SHALL reach a worker spawned with a model only through that worker's environment, and
SHALL NOT appear in `list_models`, `spawn_worker`'s result or refusal, or `loop.log`.

#### Scenario: A worker of another CLI on a keyed server
- **WHEN** the supervisor of a Claude Code session spawns a worker on an OpenCode model of a server
  with a key
- **THEN** the worker's environment has the key, the supervisor's does not, and neither the worker's
  config files, the tool's results nor `loop.log` hold it

### Requirement: The supervisor is told how to choose

The supervisor's text and the descriptions of `list_models` and `spawn_worker` SHALL say: leave
`model` out unless the human or the task names one; after a refused model tell the human the reason
and ask, never pick another by yourself; `model` holds for that spawn only. A kit SHALL name no model.

#### Scenario: The supervisor's text
- **WHEN** a session's supervisor starts
- **THEN** its instructions name `list_models` and these three rules, whatever the kits
