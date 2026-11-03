# configured-models Specification

## Purpose
The models the human configures once under names: an agent CLI, the model as that CLI
names it and, when it lives elsewhere, a saved model server; checked against the CLI's or
the server's list when saved, so that the rest of LADO can refer to a model by its name.

## Requirements

### Requirement: lado model add saves a model under a name

`lado model add <name> --cli <cli> --model <model> [--server <server>]` SHALL save a
configured model: a name, an agent CLI (a provider's name), the model as that CLI names it
(spaces around it dropped), and optionally a saved model server by its name. On success it
SHALL print `Saved model "<name>": <CLI title>, <model>[ on <server>] (<the check's
text>)` and exit 0. `lado model` alone SHALL print its help.

#### Scenario: An alias of Claude Code
- **WHEN** the human runs `lado model add Быстрая --cli claude --model haiku`
- **THEN** it prints `Saved model "Быстрая": Claude Code, haiku (an alias of Claude Code)`
  and exits 0

#### Scenario: A model on LM Studio
- **WHEN** `LM Studio дома` is saved, answers and lists `qwen3-8b`, and the human runs
  `lado model add "Локальная Qwen" --cli opencode --model qwen3-8b --server "LM Studio
  дома"`
- **THEN** it prints `Saved model "Локальная Qwen": OpenCode, qwen3-8b on LM Studio дома (in
  LM Studio дома's list of models)` and exits 0

#### Scenario: A CLI LADO does not know
- **WHEN** the human gives `--cli gemini`
- **THEN** it exits 1 naming the CLIs LADO knows, and nothing is saved

### Requirement: A model's name

A model's name SHALL be one line of visible text of 1 to 64 characters; spaces and any
script SHALL be allowed. A name another configured model has, compared ignoring case,
SHALL be refused with `a model "<its name>" is saved already; remove it first: lado model
remove "<its name>"` and exit 1, before any check. Every command that takes a model's name
SHALL find it ignoring case. Models and servers SHALL have names of their own: a model may
have a server's name.

#### Scenario: A name taken in another case
- **WHEN** `Быстрая` is saved and the human runs `lado model add быстрая --cli claude
  --model sonnet`
- **THEN** it exits 1 with the line naming `Быстрая`, and the saved model is unchanged

### Requirement: A model without a server is checked against its CLI

A model without a server SHALL be checked against its CLI, read with the agents'
environment, by the session model's thresholds: an alias or a name of the CLI's list SHALL
be saved; a name its list lacks SHALL be refused with exit 1; with no list the model SHALL
be saved after a warning on stderr.

#### Scenario: A name OpenCode does not list
- **WHEN** OpenCode lists `anthropic/claude-sonnet-4` and the human adds `--cli opencode
  --model anthropic/claude-sonet-4`
- **THEN** it exits 1 with `anthropic/claude-sonet-4 is not in OpenCode's list of models;
  <the command that prints it> prints the list`, and nothing is saved

#### Scenario: A CLI that gives no list
- **WHEN** the CLI's list cannot be read (the CLI is not installed, or its list command
  fails)
- **THEN** stderr has `lado: warning: <why>: LADO cannot check <model>; a wrong name stops
  its agents at their first turn`, the model is saved, and it exits 0

### Requirement: A model's server must be saved and answer

A model with a server SHALL name a saved server; one no server has SHALL be refused,
naming `lado model-server list`. LADO SHALL probe the server with its kept key: a server
that does not answer, asks for a key, refuses the key or is no longer a server LADO knows
SHALL refuse the model with the probe's line and `LADO cannot check <model>`, exit 1.

#### Scenario: The server does not answer
- **WHEN** `LM Studio дома` is saved but LM Studio is closed, and the human adds a model
  naming it
- **THEN** it exits 1 with `http://localhost:1234 does not answer (connection refused)` and
  `LADO cannot check qwen3-8b`, and nothing is saved

#### Scenario: A server no one saved
- **WHEN** the human adds a model with `--server nowhere` and no server has that name
- **THEN** it exits 1 naming `lado model-server list`, and sends no request

### Requirement: A model's server must suit its CLI

The API the CLI's provider speaks SHALL be among the APIs the server proves at the
model's adding, else the model SHALL be refused with `<server> does not suit <CLI title>:
it has no <API>; it suits <titles>` (`it suits no CLI` for none) and exit 1; a CLI that
speaks no server API SHALL be refused likewise.

#### Scenario: A server that does not suit the CLI
- **WHEN** `LM Studio дома` proves chat completions only, and the human adds a model with
  `--cli codex --server "LM Studio дома"`
- **THEN** it exits 1 with `LM Studio дома does not suit Codex CLI: it has no Responses
  API; it suits Kilo CLI, OpenCode`, and nothing is saved

### Requirement: A model on a server is checked against the server's list

A model on a server SHALL be checked against the server's list of models by the session
model's thresholds: in the list saved, not in it refused with exit 1, no list saved after
the warning on stderr.

#### Scenario: A model the server does not list
- **WHEN** the server lists `qwen3-8b` and the human adds `--model qwen3-14b` on it
- **THEN** it exits 1 with `qwen3-14b is not in LM Studio дома's list of models; lado
  model-server probe http://localhost:1234 prints the list`

#### Scenario: Claude Code on an Anthropic-compatible gateway
- **WHEN** the server proves the Anthropic Messages API and lists `claude-sonnet-4`, and
  the human adds `--cli claude --model claude-sonnet-4 --server gw`
- **THEN** the model is saved (the API rule suits; whether a session can start on it is
  decided when sessions use configured models)

### Requirement: lado model list shows the configured models

`lado model list` SHALL print one line per configured model, sorted by name ignoring case,
under the header `NAME CLI MODEL SERVER`: its name, its CLI's title, its model and its
server's name (`—` for none). It SHALL run no CLI and send no request. With no model it
SHALL print `No models. Add one: lado model add <name> --cli <cli> --model <model>
[--server <server>]`.

#### Scenario: Two models
- **WHEN** `Быстрая` (Claude Code, haiku) and `Локальная Qwen` (OpenCode, qwen3-8b on `LM
  Studio дома`) are saved
- **THEN** the list shows `Быстрая  Claude Code  haiku  —` and `Локальная Qwen  OpenCode
  qwen3-8b  LM Studio дома`

#### Scenario: A server renamed nowhere
- **WHEN** the server of `Локальная Qwen` has its address replaced with `--replace`
- **THEN** the list still shows `LM Studio дома` as its server

### Requirement: lado model remove removes a model

`lado model remove <name> [<name> …]` SHALL find every name given (ignoring case, a name
given twice counted once) before it removes any; when one is no model's, it SHALL be
refused with `no model "<name>" is saved; lado model list names them` (`no models "<name>",
"<name>" are saved; …` for several), remove nothing and exit 1. Otherwise it SHALL remove
each model in the order given, print `Removed model "<name>".` for each and exit 0. Their
servers SHALL stay.

#### Scenario: Removing the last model of a server
- **WHEN** `Локальная Qwen` is the only model on `LM Studio дома` and the human removes it
- **THEN** it is gone from `lado model list`, `LM Studio дома` stays, and `lado
  model-server remove "LM Studio дома"` then succeeds

#### Scenario: Several models at once
- **WHEN** `coder-codex`, `coder-oc` and `sp` are saved and the human runs `lado model
  remove "coder-codex" "coder-oc" "sp"`
- **THEN** it prints `Removed model "coder-codex".`, `Removed model "coder-oc".` and
  `Removed model "sp".`, and exits 0

#### Scenario: One name of several not saved
- **WHEN** `coder-codex` is saved, `nowhere` is not, and the human runs `lado model remove
  coder-codex nowhere`
- **THEN** it exits 1 with `no model "nowhere" is saved; lado model list names them`, and
  `coder-codex` stays

### Requirement: The configured models are kept in lado.db and used by no session yet

The configured models SHALL be kept in `lado.db` (from schema 38), each with its name, CLI,
model and its server's id; a model SHALL NOT refer to a server that is not saved. No
session, agent, launch or resume SHALL read the configured models or the saved servers:
with them or without them, `lado start`, the launch window and every agent SHALL behave as
before.

#### Scenario: A session with models saved
- **WHEN** models and servers are saved and the human runs `lado start <repo>` without
  `--model`
- **THEN** the session's agents start on their CLI's default, as without them

### Requirement: An embeddings model is no agent's model

A model on a server whose `GET /api/v0/models` types it `embeddings` SHALL be refused by
`lado model add` with `<model> is an embeddings model on <server>; an agent needs a chat
model: lado model-server probe <address> lists the models` and exit 1, after the check that
the server suits the CLI and before the check against its list; nothing SHALL be saved. A
model the server gives no type for SHALL be checked as before.

#### Scenario: The embeddings model of LM Studio
- **WHEN** `lms` is LM Studio at `http://10.73.10.235:1234` and types
  `text-embedding-nomic-embed-text-v1.5` `embeddings`, and the human runs `lado model add
  emb --cli opencode --model text-embedding-nomic-embed-text-v1.5 --server lms`
- **THEN** it exits 1 with `text-embedding-nomic-embed-text-v1.5 is an embeddings model on
  lms; an agent needs a chat model: lado model-server probe http://10.73.10.235:1234 lists
  the models`, and nothing is saved

#### Scenario: A chat model of the same server
- **WHEN** the same server types `qwen3-8b` `llm` and the human adds `--model qwen3-8b`
  on it
- **THEN** the model is saved

#### Scenario: A server without types
- **WHEN** the server is Ollama and lists `nomic-embed-text`
- **THEN** `lado model add … --model nomic-embed-text --server <it>` is checked against the
  list as before and saved
