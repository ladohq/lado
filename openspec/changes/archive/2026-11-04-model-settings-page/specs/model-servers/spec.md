## ADDED Requirements

### Requirement: Why a server has no list is given only with no list

A probe SHALL give why a server has no list of models only when it has none: when the list
asked without `anthropic-version` fails and the one asked with it gives the models, the
probe SHALL have those models and no why. Every place that shows the why (`lado
model-server probe` and `add`, Settings → Models) SHALL show it only with no list.

#### Scenario: An Anthropic API that lists its models only with its version header
- **WHEN** the server refuses `GET /v1/models` without `anthropic-version` with 400 and
  lists `claude-x` in Anthropic's shape with it
- **THEN** the probe has the models `claude-x` and no why, and Settings → Models shows
  `claude-x` with no `no list` reason

#### Scenario: A list that fails both ways
- **WHEN** the server answers `GET /v1/models` with 500 with and without the header
- **THEN** the probe has no list and its why is `GET /v1/models: 500`

### Requirement: lado doctor names models their server no longer lists

For each saved server that answered with a list of models, the `Model servers` line of
`lado doctor` SHALL warn of each configured model on that server whose model the list
lacks: `model "<name>" (<model>) is not in <server>'s list of models`. A server with no
list or that does not answer SHALL name no model so.

#### Scenario: A model gone from LM Studio
- **WHEN** `Локальная Qwen` (`qwen3-8b`) refers to `LM Studio дома`, which answers and no
  longer lists `qwen3-8b`
- **THEN** `lado doctor` prints `[WARN] Model servers:` with `model "Локальная Qwen"
  (qwen3-8b) is not in LM Studio дома's list of models`, and its exit status is as without
  the line

### Requirement: lado model-server remove --with-models removes its models too

`lado model-server remove <name> --with-models` SHALL remove every configured model that
refers to the server, printing `Removed model "<model>".` for each, then the server and
its key file, in one transaction for the models and the server, and exit 0.

#### Scenario: A server with its models
- **WHEN** the models `coder-oc` and `sp` refer to `lms` and the human runs `lado
  model-server remove lms --with-models`
- **THEN** it prints `Removed model "coder-oc".`, `Removed model "sp".` and `Removed model
  server "lms".`, exits 0, and neither the models, the server nor its key folder is left

## MODIFIED Requirements

### Requirement: lado model-server remove refuses a server a model uses

`lado model-server remove <name>` SHALL remove the saved server and its key file, print
`Removed model server "<name>".` and exit 0. While a configured model refers to the
server it SHALL be refused, changing nothing, with a line naming every model that refers
to it and one `lado model remove` for all of them, the hint `or remove them with it: lado
model-server remove "<name>" --with-models`, and exit 1. A name no server has SHALL be
refused with exit 1.

#### Scenario: A server a model uses
- **WHEN** the model `Локальная Qwen` refers to `LM Studio дома` and the human runs `lado
  model-server remove "LM Studio дома"`
- **THEN** it exits 1 with the line naming `Локальная Qwen` and the hint naming
  `--with-models`, and the server and its key file stay

#### Scenario: A server several models use
- **WHEN** the models `coder-codex`, `coder-oc` and `sp` refer to `lms` and the human runs
  `lado model-server remove lms`
- **THEN** it exits 1 with `model server "lms" is used by the models coder-codex, coder-oc,
  sp; remove them first: lado model remove "coder-codex" "coder-oc" "sp"`
- **AND** running that command and then `lado model-server remove lms` removes the server

#### Scenario: A server no model uses
- **WHEN** no model refers to `work` and the human runs `lado model-server remove work`
- **THEN** the server is gone from the list, its folder under `<LADO_HOME>/model-servers/`
  is gone, and it exits 0

### Requirement: lado model-server probe names a server's type, models and CLIs

`lado model-server probe <address>` SHALL print the server's address, its type (Ollama,
LM Studio, OpenAI-compatible or Anthropic-compatible), its models, the agent CLIs that can
use it with the API each uses, and each CLI that cannot with the API it lacks, and exit 0.
The CLIs SHALL come in LADO's one order of the agent CLIs (Claude Code, Codex CLI, Kilo CLI,
OpenCode), the order of Settings → Models. `lado model-server` alone SHALL print its help.
Nothing else in LADO SHALL change.

#### Scenario: An Ollama server that speaks two APIs
- **WHEN** the human runs `lado model-server probe http://192.168.1.10:11434` and the
  server is Ollama with the models `llama3.1:8b` and `qwen2.5-coder:7b`, answering chat
  completions and the Responses API but not the Anthropic Messages API
- **THEN** it prints `http://192.168.1.10:11434`, `type: Ollama`,
  `models: llama3.1:8b, qwen2.5-coder:7b`,
  `CLIs: Codex CLI (Responses API); Kilo CLI, OpenCode (chat completions)` and
  `not: Claude Code (no Anthropic Messages API)`, and exits 0

#### Scenario: A server every CLI can use
- **WHEN** the server answers all three APIs
- **THEN** the output has no `not:` line

### Requirement: lado model-server list shows the saved servers without asking them

`lado model-server list` SHALL print one line per saved server, sorted by name ignoring
case, under the header `NAME ADDRESS TYPE KEY CLIs`: its name, address, type, `yes` when its
key file is there and `no` otherwise, and the titles of the CLIs whose API it proved when
it was saved (`none` for none), in LADO's one order of the agent CLIs. It SHALL send no
request. With no server saved it SHALL print `No model servers. Add one: lado model-server
add <name> <address> [--key]`.

#### Scenario: Two servers
- **WHEN** `LM Studio дома` (LM Studio, chat completions, no key) and `work`
  (OpenAI-compatible, chat completions and the Responses API, a key) are saved
- **THEN** the list shows `LM Studio дома  http://localhost:1234  LM Studio  no  Kilo CLI,
  OpenCode` and `work  https://gw.corp/llm  OpenAI-compatible  yes  Codex CLI, Kilo CLI,
  OpenCode`, and no request reaches either server

#### Scenario: None saved
- **WHEN** no server is saved
- **THEN** it prints `No model servers. Add one: lado model-server add <name> <address>
  [--key]` and exits 0
