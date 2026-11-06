## MODIFIED Requirements

### Requirement: The session's model is where an agent starts, not a limit

For an agent of a CLI whose models on a server sit beside its own, LADO SHALL put every external
model ticked for that CLI into the agent's config, whatever the session chose: a built-in model,
an external model, or nothing. The agent's own CLI's built-in models SHALL stay. An agent of a CLI
holding one model per process SHALL get none of this: it has the server of its start model alone,
and only when it starts on one.

#### Scenario: A built-in model chosen
- **WHEN** a session on OpenCode has `opencode/big-pickle` chosen, and `Локальная Qwen` and `Рабочая
  Qwen` on two servers are ticked for OpenCode
- **THEN** the agent's config has a provider for each server with its models, and its model is
  `opencode/big-pickle`

#### Scenario: An external model chosen
- **WHEN** the session has `Локальная Qwen` chosen
- **THEN** the agent's config has the same two providers, and it starts on `Локальная Qwen`

#### Scenario: Nothing chosen
- **WHEN** the session has no table and OpenCode has no default
- **THEN** the agent's config has the same two providers, no `model`, no `--model`, and the CLI
  chooses

#### Scenario: A Claude Code agent
- **WHEN** an external model is ticked for Claude Code and a Claude session starts on its settings
- **THEN** the agent's launch has nothing of the server

#### Scenario: A Claude Code agent on a server's model
- **WHEN** a Claude session starts on `Шлюз Opus` on `Шлюз`, and `Локальная Qwen` on another server is
  ticked for Claude Code
- **THEN** the agent's launch has `Шлюз` and `Шлюз Opus` alone

### Requirement: A CLI that runs on no server is refused

A start model on a server for a CLI that does not run on one yet SHALL be refused before any
request, naming the CLIs that do and that the server suits; a spawned worker SHALL be refused the
same way.

#### Scenario: Claude Code on a gateway
- **WHEN** Claude Code's default is `Шлюз Opus` on `Шлюз`, which proves the Anthropic Messages API,
  and the human starts a Claude session
- **THEN** no refusal names Claude Code, `Шлюз` is asked, and the session starts on it

#### Scenario: Codex on a gateway
- **WHEN** Codex's default is `Шлюз GPT` on `Шлюз`, which also suits Claude Code and OpenCode, and the
  human starts a Codex session
- **THEN** it refuses with `Шлюз GPT is on the model server Шлюз; Codex does not run on a model
  server yet, Claude Code, Kilo CLI and OpenCode do`, adding the default's way out, and `Шлюз` is not
  asked

#### Scenario: A worker of that CLI
- **WHEN** the supervisor of an OpenCode session spawns a worker with the provider `codex`
- **THEN** `spawn_worker` fails with the same line, adding `list_models shows the others, model=""
  is the CLI's own settings` in place of the default's way out, and no worker exists
