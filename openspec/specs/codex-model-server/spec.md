# codex-model-server Specification

## Purpose
A Codex agent whose model is on a model server runs there with its tools, MCP servers and hooks, and nothing of the human's Codex login reaches that server.

## Requirements

### Requirement: A Codex agent runs on its model's server

A Codex agent whose start model is on a model server SHALL start with an entry for that server in `model_providers` of its own `CODEX_HOME`, over the carried values, with `wire_api` `responses`, and with that entry and the model chosen at the top level and in a carried profile. Its turns, tools, MCP servers and hooks SHALL work as on a built-in model. A Codex agent on a built-in model or on the user's own provider SHALL start as before, with nothing of a server.

#### Scenario: A session on a server's model
- **WHEN** `lado start <repo> --provider codex --model "Шлюз GPT"` starts, and `Шлюз GPT` is on `Шлюз` at `http://gw:4000`
- **THEN** the supervisor's config.toml has `model_provider` `lado-<id>`, an entry with `base_url` `http://gw:4000/v1` and the model's id as `model`, and its first turn reaches that server

#### Scenario: A carried profile
- **WHEN** the user's Codex config has `profile = "work"` with its own `model` and `model_provider`
- **THEN** the agent's requests still go to its model's server, and the user's `model_providers` entries are in its config

#### Scenario: A worker
- **WHEN** the supervisor calls `spawn_worker(model="Шлюз GPT")`, which is Codex's, on `Шлюз`
- **THEN** `Шлюз` is asked, and the worker starts on it

#### Scenario: A resume on a built-in model
- **WHEN** a session that ran on `Шлюз GPT` resumes with a built-in model
- **THEN** the agent's config holds no `lado-` provider and no `model_catalog_json`, and its environment has no key

#### Scenario: The real CLI
- **WHEN** real Codex runs on a fake Responses server that asks for a shell tool and an MCP tool
- **THEN** both run, LADO's hooks report the turn, and its message reaches the agent

### Requirement: A Codex agent's key stays in its environment

A server's key SHALL reach a Codex agent only as the variable its provider entry names in `env_key`, in the agent's environment. It SHALL NOT be in config.toml, `models.json`, `lado.db`, the output or a log of LADO.

#### Scenario: A keyed server
- **WHEN** a Codex agent starts on a server with a key
- **THEN** its config.toml has the variable's name and not the value, and each request carries the key as `Authorization: Bearer`

#### Scenario: A server with no key
- **WHEN** a Codex agent starts on a server with no key, with `OPENAI_API_KEY` set
- **THEN** its entry has no `env_key`, and its requests carry no `Authorization`

### Requirement: A Codex agent on a server needs no Codex login

A Codex agent on a server SHALL start without a Codex login, and LADO SHALL neither link the user's login file into its home nor write a key file there.

#### Scenario: No login
- **WHEN** Codex is not logged in and a session starts on a server's model
- **THEN** the session starts, with no question of a login

#### Scenario: A logged-in user
- **WHEN** Codex is logged in and an agent starts on a server's model
- **THEN** the agent's home has no `auth.json`

### Requirement: A Codex agent on a server offers its own model

The `/model` of a Codex agent on a server SHALL offer that agent's one model under its saved name, from a list of the agent's own made from the installed Codex's catalogue. A catalogue that cannot be read SHALL leave Codex's list in place, with a launch warning that says so.

#### Scenario: The agent's list
- **WHEN** a Codex agent starts on `Шлюз GPT`
- **THEN** its config.toml has `model_catalog_json`, and that file holds the one model named `Шлюз GPT`

#### Scenario: No catalogue
- **WHEN** `codex debug models --bundled` fails
- **THEN** the agent starts, and the launch warns that `/model` shows OpenAI's models, which its server does not have

#### Scenario: The real CLI takes the list
- **WHEN** real Codex starts with that file
- **THEN** it runs a turn, and its `/model` shows that one model alone

### Requirement: A Codex agent on a server asks for nothing a server may refuse

A Codex agent on a server SHALL have web search off and no reasoning effort carried from the user's config, and its list entry SHALL add no tool or parameter of OpenAI's.

#### Scenario: A carried effort
- **WHEN** the user's Codex config has `model_reasoning_effort = "xhigh"`, and an agent starts on a server's model
- **THEN** the agent's config has no such key, and its page shows no effort

#### Scenario: The tools of a request
- **WHEN** real Codex on a fake server sends its first request
- **THEN** no tool has the type `web_search` or `custom`, and LADO's MCP tools are in a `namespace`
