## ADDED Requirements

### Requirement: A Claude agent runs on its model's server

A Claude agent whose start model is on a model server SHALL start with that model as `--model` and
the server's root address as `ANTHROPIC_BASE_URL` in the `env` of its own settings file, so that a
value in the user's or the repository's settings or in the environment does not win. Its turns, tools,
MCP servers and hooks SHALL work as on a built-in model. A Claude agent on a built-in model, or on
Claude Code's own choice, SHALL start as before, with nothing of a server.

#### Scenario: A session on a server's model
- **WHEN** `lado start <repo> --provider claude --model "Шлюз Opus"` starts, and `Шлюз Opus` is on
  `Шлюз` at `http://gw:4000`
- **THEN** the supervisor's launch has `--model` with the model's id, its settings' `env` has
  `ANTHROPIC_BASE_URL` `http://gw:4000`, with no `/v1`, and its first turn reaches that server

#### Scenario: A base URL in the user's settings
- **WHEN** `~/.claude/settings.json` has another `ANTHROPIC_BASE_URL` in its `env`
- **THEN** the agent's requests and its key still go to its model's server

#### Scenario: A resume on a built-in model
- **WHEN** a session that ran on `Шлюз Opus` resumes with `--model opus`
- **THEN** the agent's settings hold nothing of the server, and its environment has no key

#### Scenario: Auto mode
- **WHEN** a Claude agent on a server runs in auto mode, and the server's model gives its classifier
  no usable answer
- **THEN** LADO's tools work, as its settings allow them; an agent on a built-in model allows nothing
  of its own

#### Scenario: The real CLI
- **WHEN** real Claude Code runs on a fake Anthropic server that asks for a shell tool and an MCP tool
- **THEN** both run, LADO's hooks report the turn, and its message reaches the agent

### Requirement: Nothing of the human's Claude credentials reaches a server

A Claude agent on a server SHALL have an empty value for every variable by which Claude Code would
send another credential or use another provider, and its own `apiKeyHelper`, for a server with no
key too. Neither the human's Claude login, nor a key, token, header or `apiKeyHelper` of the
environment or the user's settings SHALL reach the server.

#### Scenario: A logged-in human and a server with no key
- **WHEN** Claude Code is logged in and an agent starts on a server with no key
- **THEN** the server gets the placeholder `no-key`, not the login's token

#### Scenario: The human's key in the environment
- **WHEN** `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` is LADO's secret, a project secret or in
  the login shell, and an agent starts on a server with a key
- **THEN** the server gets that server's key alone

#### Scenario: The user's settings
- **WHEN** `~/.claude/settings.json` has `apiKeyHelper` and `ANTHROPIC_AUTH_TOKEN` in its `env`
- **THEN** the server gets neither

#### Scenario: Another provider in the environment
- **WHEN** `CLAUDE_CODE_USE_BEDROCK`, `CLAUDE_CODE_USE_MANTLE` or `ANTHROPIC_UNIX_SOCKET` is set
- **THEN** the agent still goes to its model's server

### Requirement: A Claude agent on a server stays on its model

The settings of a Claude agent on a server SHALL allow that model alone and make it the default and
the small model of Claude Code, so that `/model` shows no model of Anthropic and no request asks for
one. Telemetry and experimental betas SHALL be off for it.

#### Scenario: /model
- **WHEN** the human opens `/model` in that agent's terminal
- **THEN** it shows Default and the model, and no Opus, Fable, Sonnet or Haiku

#### Scenario: A subagent asking for another model
- **WHEN** the agent starts a subagent with `model: haiku`
- **THEN** the request names the agent's model

### Requirement: A model of a server may start another Claude agent

Each Claude agent SHALL have its own model and server: `spawn_worker(model=…)` SHALL start a worker on
another model of the server, another server or a built-in model, whatever its supervisor runs on, and
neither the supervisor's server key nor its address, nor anything else its settings give the
processes it starts, SHALL reach a worker.

#### Scenario: A worker on another server
- **WHEN** a supervisor on `Шлюз Opus` spawns a worker on `Локальная Qwen` of another server
- **THEN** the worker runs on that server with its key, and has no variable of `Шлюз`'s key

#### Scenario: A worker on a built-in model
- **WHEN** that supervisor spawns a worker with `model="sonnet"`
- **THEN** the worker's settings and environment hold nothing of a server, also in inherit mode, and
  it needs Claude Code's login

### Requirement: A Claude agent on a server needs no Claude login

A session, a resume and a worker of Claude Code on a server's model SHALL start with Claude Code not
logged in: no refusal, no wait for a login and no keychain warning. LADO SHALL record Claude Code's
first run for such an agent, so no first-run screen holds it.

#### Scenario: No login
- **WHEN** Claude Code is not logged in and a session starts on a server's model
- **THEN** it starts, and the agent reaches its first hook with no answer in its terminal

#### Scenario: A clone for such a session
- **WHEN** Claude Code is not logged in and `lado start <git-url> --provider claude --model "Шлюз Opus"`
  runs, or Claude Code's default is `Шлюз Opus` on a server and no model is given
- **THEN** the repository is cloned and the session starts on the server

#### Scenario: A built-in model in the same state
- **WHEN** Claude Code is not logged in and a session starts on `opus`
- **THEN** it is refused as before

### Requirement: A running Claude agent on a server is shown by its saved name

The card of a running Claude agent on a server's model, `lado ls` and `list_agents` SHALL name the
saved model, its server and its source, whoever chose it, by what its launch wrote and never by
the model's id alone. A stopped agent SHALL show the id.

#### Scenario: A worker the supervisor put on a server
- **WHEN** the supervisor spawns a worker with `model="Шлюз Opus"`
- **THEN** its card has `Шлюз Opus`, `Шлюз` and the supervisor as its source

#### Scenario: A built-in model with the id of a saved one
- **WHEN** a worker starts on the built-in `claude-opus-5-5`, and a saved model of a server has that id
- **THEN** its card names no server

### Requirement: A name Claude Code would read as its own is refused

A model of a server whose id Claude Code reads as its own, ignoring case one of its aliases,
`default` or a name ending in `[1m]`, SHALL be refused for Claude Code when it is saved and at a
start, naming the model and the server, and `list_models` SHALL give that as its `blocked`. The same
model SHALL stay usable for another CLI, and any other name SHALL stay as it is.

#### Scenario: A server's model named sonnet
- **WHEN** `lado model add --cli claude --server Шлюз sonnet` runs
- **THEN** it exits non-zero with a line saying Claude Code reads `sonnet` as its own model

#### Scenario: Another case
- **WHEN** `lado model add --cli claude --server Шлюз Opus` runs
- **THEN** it is refused the same way, and `Qwen/Qwen3-8B` is saved

#### Scenario: A server without Anthropic's API
- **WHEN** a Claude model is saved or started on a server that proves no Anthropic Messages API
- **THEN** it is refused before the agent starts, naming that API and the CLIs the server suits
