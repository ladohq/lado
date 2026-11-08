# configured-models Specification

## Purpose
The models the human configures once under names: an agent CLI, the model as that CLI
names it and, when it lives elsewhere, a saved model server; checked against the CLI's or
the server's list when saved, so that the rest of LADO can refer to a model by its name.

## Requirements

### Requirement: lado model add saves a model under a name

`lado model add <name> --cli <cli> --model <model> --server <server>` SHALL save a
configured model: a name, an agent CLI (a provider's name), the model as that CLI names it
(spaces around it dropped), and a saved model server by its name. On success it SHALL print
`Saved model "<name>": <CLI title>, <model> on <server> (<the check's text>)` and exit 0.
`lado model` alone SHALL print its help.

#### Scenario: A model on LM Studio
- **WHEN** `LM Studio дома` is saved, answers and lists `qwen3-8b`, and the human runs
  `lado model add "Локальная Qwen" --cli opencode --model qwen3-8b --server "LM Studio
  дома"`
- **THEN** it prints `Saved model "Локальная Qwen": OpenCode, qwen3-8b on LM Studio дома (in
  LM Studio дома's list of models)` and exits 0

#### Scenario: A CLI LADO does not know
- **WHEN** the human gives `--cli gemini`
- **THEN** it exits 1 naming the CLIs LADO knows, and nothing is saved

#### Scenario: An alias of Claude Code
- **WHEN** the human runs `lado model add Быстрая --cli claude --model haiku`
- **THEN** it exits 1 with the line and the hint naming `lado model default`, and nothing is
  saved

### Requirement: A model's name

A model's name SHALL be one line of visible text of 1 to 64 characters; spaces and any
script SHALL be allowed. A name another configured model has, compared ignoring case,
SHALL be refused with `a model "<its name>" is saved already; remove it first: lado model
remove "<its name>"` and exit 1, before any check. Every command that takes a model's name
SHALL find it ignoring case. Models and servers SHALL have names of their own: a model may
have a server's name.

#### Scenario: A name taken in another case
- **WHEN** `Быстрая` is saved and the human runs `lado model add быстрая --cli opencode
  --model qwen3-8b --server lms`
- **THEN** it exits 1 with the line naming `Быстрая`, and the saved model is unchanged

### Requirement: A model's server must be saved and answer

A model SHALL name a saved server; one no server has SHALL be refused,
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
server's name. It SHALL run no CLI and send no request. With no model it
SHALL print `No models. Add one: lado model add <name> --cli <cli> --model <model>
--server <server>`.

#### Scenario: Two models
- **WHEN** `Быстрая` (Kilo CLI, qwen3-8b on `lms`) and `Локальная Qwen` (OpenCode, qwen3-8b
  on `LM Studio дома`) are saved
- **THEN** the list shows `Быстрая  Kilo CLI  qwen3-8b  lms` and `Локальная Qwen  OpenCode
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

### Requirement: The configured models are kept in lado.db and used by sessions

The configured models SHALL be kept in `lado.db` (from schema 38), each with an id that
never changes (from schema 39), its name, CLI, model and its server's id; a model SHALL NOT
exist without a saved server. With none saved and no default set, `lado start`, the launch window
and every agent SHALL behave as before. A saved model SHALL reach an agent of its CLI as
`session-model` says, and a default as the start model of a session that chose none.

#### Scenario: A session with models saved
- **WHEN** models and servers are saved, no default is set and the human runs `lado start <repo>`
  without `--model`
- **THEN** the session's agents start on their CLI's choice, as without them, and no server is asked

#### Scenario: A session with a default set
- **WHEN** OpenCode's default model is set and the human starts a session on OpenCode
- **THEN** the session's agents start on that model

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

### Requirement: lado model add takes a server's models only

A configured model SHALL always live on a server: without `--server` `lado model add` SHALL be
refused with exit 1 and `a CLI's own models need no saving; only a model on a server is added:
--server <server>`, and the hint `to make one its default: lado model default <cli> <model>`.

#### Scenario: A model of a CLI's own list
- **WHEN** the human runs `lado model add Сонет --cli opencode --model a/b`
- **THEN** it exits 1 with that line and hint, reads no list, and nothing is saved

### Requirement: Removing a model clears the default on it

A model that is its CLI's default SHALL be removed with the default cleared in one
transaction, the next line after its own saying `<CLI title>'s default model is cleared.`

#### Scenario: A model that is a default
- **WHEN** `Локальная Qwen` is Kilo CLI's default model and the human removes it
- **THEN** it prints `Removed model "Локальная Qwen".` and `Kilo CLI's default model is
  cleared.`, and `lado model default` shows Kilo CLI with no default

### Requirement: The migration to model ids

A `lado.db` of schema 38 SHALL be upgraded by the migration: each model on a server SHALL keep
its name, CLI, model and server and get an id; a model without a server SHALL be dropped.

#### Scenario: Upgrading from schema 38
- **WHEN** a `lado.db` of schema 38 holds `Быстрая` (Claude Code, haiku, no server) and
  `Локальная Qwen` on `LM Studio дома`
- **THEN** at schema 39 `lado model list` shows `Локальная Qwen` alone, with its server, and
  `lado model default` shows every agent CLI with no default

### Requirement: A model reference is external or built-in

A reference to a model SHALL be external, a configured model's id, or built-in, an agent
CLI and the model as that CLI names it. A reference SHALL survive a rename of its configured
model. A CLI's built-in models SHALL be read from the CLI and never stored as a list.

#### Scenario: A renamed default
- **WHEN** `Локальная Qwen` is OpenCode's default model and the human renames it `Alpha`
- **THEN** `lado model default` shows `Alpha` as OpenCode's default

### Requirement: A CLI's full list is computed

The core SHALL compute in one place what an agent CLI can run: its aliases and its own list
as its list command gives them, within that command's timeout, and the configured models of
that CLI, by name ignoring case. It SHALL keep none of it. A list that cannot be read SHALL
give why, and the configured models SHALL still be there. `Other name` SHALL be offered
exactly when the CLI gives no full list, whether it has aliases or not.

#### Scenario: OpenCode with a server
- **WHEN** OpenCode lists 10 models and two configured models are OpenCode's
- **THEN** the list has the 10 built-in models and the 2 external ones, and offers no other
  name

#### Scenario: Claude Code
- **WHEN** the list of Claude Code is asked for
- **THEN** it has Claude Code's aliases, says it gives no list beyond them, and offers an
  other name

#### Scenario: A list command that times out
- **WHEN** `kilo models` does not end in its timeout and one configured model is Kilo CLI's
- **THEN** the list has that external model, why the list is missing, and offers an other
  name

### Requirement: lado model default shows the agent CLIs' default models

`lado model default` SHALL print one line per agent CLI LADO knows, in LADO's order, under
the header `CLI DEFAULT MODEL SERVER`: its title, its default (the configured model's name
or the built-in model, `—` for none) and the server of an external default (`—` otherwise).
It SHALL run no CLI and send no request. `lado model default <cli>` SHALL print that CLI's line
alone under the header.

#### Scenario: Two defaults
- **WHEN** Claude Code's default is `opus` and Kilo CLI's is `Локальная Qwen` on `LM Studio
  дома`
- **THEN** it prints `Claude Code  opus  —`, `Codex CLI  —  —`, `Kilo CLI  Локальная Qwen
  LM Studio дома` and `OpenCode  —  —`

#### Scenario: One CLI
- **WHEN** Claude Code's default is `opus` and the human runs `lado model default claude`
- **THEN** it prints the header and `Claude Code  opus  —`

### Requirement: lado model default sets a CLI's default model

`lado model default <cli> <model>` SHALL set the agent CLI's default model, replacing the
one it had. `<model>` SHALL be taken as a configured model of that CLI by its name ignoring
case, else as a built-in model of that CLI. On success it SHALL print `<CLI title>'s default
model: <name> (<model> on <server>)` for an external model, `<CLI title>'s default model:
<model> (<the check's text>)` for a built-in one, and exit 0.

#### Scenario: An external model
- **WHEN** `Локальная Qwen` is Kilo CLI's and the human runs `lado model default kilo
  "локальная qwen"`
- **THEN** it prints `Kilo CLI's default model: Локальная Qwen (qwen3-8b on LM Studio дома)`
  and exits 0

### Requirement: lado model default refuses what cannot be a CLI's default

`lado model default <cli> <model>` SHALL exit 1 and change nothing for a name that is both a
configured model and a built-in model of the CLI, a name that is only another CLI's
configured model, a CLI LADO does not know (naming those it knows), and a CLI that is not
installed.

#### Scenario: One name, two models
- **WHEN** OpenCode lists `qwen3-8b` and a configured model of OpenCode is named `qwen3-8b`
- **THEN** `lado model default opencode qwen3-8b` exits 1 with `"qwen3-8b" is both a saved
  model of OpenCode and one of its own; rename the saved one: Settings → Model servers`, and the
  default is unchanged

#### Scenario: Another CLI's model
- **WHEN** `Локальная Qwen` is OpenCode's and the human runs `lado model default claude
  "Локальная Qwen"`
- **THEN** it exits 1 with `"Локальная Qwen" is a model of OpenCode, not of Claude Code`,
  even though Claude Code gives no full list

#### Scenario: Not installed
- **WHEN** Kilo CLI is not installed and the human runs `lado model default kilo
  "Локальная Qwen"`
- **THEN** it exits 1 with `Kilo CLI is not installed`, and the default is unchanged

### Requirement: A CLI's default model is checked when set

A built-in default SHALL be checked against its CLI, read with the agents' environment, by
the session model's thresholds: an alias or a name of the CLI's list SHALL be set; a name
its list lacks SHALL be refused with exit 1; with no list it SHALL be set after the warning
on stderr. An external default SHALL be set with no request to its server.

#### Scenario: An alias of Claude Code
- **WHEN** the human runs `lado model default claude opus`
- **THEN** it prints `Claude Code's default model: opus (an alias of Claude Code)` and exits
  0

#### Scenario: A name OpenCode does not list
- **WHEN** OpenCode lists `anthropic/claude-sonnet-4` and the human runs `lado model default
  opencode anthropic/claude-sonet-4`
- **THEN** it exits 1 with `anthropic/claude-sonet-4 is not in OpenCode's list of models;
  <the command that prints it> prints the list`, and the default is unchanged

#### Scenario: A full id of Claude Code
- **WHEN** the human runs `lado model default claude claude-opus-4-1-20250805`
- **THEN** stderr has `lado: warning: Claude Code gives no list of models beyond its
  aliases: LADO cannot check claude-opus-4-1-20250805; a wrong name stops its agents at their
  first turn`, the default is set, and it exits 0

#### Scenario: A server that is off
- **WHEN** `LM Studio дома` does not answer and the human sets `Локальная Qwen` on it as
  Kilo CLI's default
- **THEN** the default is set and no request is sent

### Requirement: lado model default --clear clears a CLI's default model

`lado model default <cli> --clear` SHALL clear the agent CLI's default model, whether the
CLI is installed or not, print `<CLI title>'s default model is cleared.` and exit 0; with no
default it SHALL print `<CLI title> has no default model.` and exit 0. A model together with
`--clear` SHALL be refused with exit 2.

#### Scenario: A CLI not installed
- **WHEN** Kilo CLI is not installed, its default is set, and the human runs `lado model
  default kilo --clear`
- **THEN** it prints `Kilo CLI's default model is cleared.` and exits 0
