## MODIFIED Requirements

### Requirement: An API is proven without generating

LADO SHALL prove each API with one POST whose body is `{}`: an answer 400 or 422 with a
JSON body proves it, any other answer does not. It SHALL send at most one request per
check to an address (the model list, the model list in Anthropic's way, Ollama's and LM
Studio's own endpoints, one per API, one control), each limited to 5 seconds, and none to
another path, port or host. The header `anthropic-version` SHALL go only with the POSTs and
with the model list asked in Anthropic's way; the model list, `GET /api/version` and
`GET /api/v0/models` SHALL be asked without it.

#### Scenario: The requests of one probe
- **WHEN** the human probes an address that answers
- **THEN** the server receives at most `GET /v1/models` twice (once without
  `anthropic-version` and once with it), `GET /api/version`, `GET /api/v0/models` and one
  `POST` with the body `{}` to each of `/v1/chat/completions`, `/v1/responses`,
  `/v1/messages` and `/v1/lado-no-such-api`

#### Scenario: An API missing
- **WHEN** the server answers `POST /v1/responses` with 404
- **THEN** the server is named as without the Responses API

#### Scenario: The header of Anthropic's API
- **WHEN** the human probes an address that answers
- **THEN** every `POST` and one `GET /v1/models` carry `anthropic-version: 2023-06-01`, and
  the first `GET /v1/models`, `GET /api/version` and `GET /api/v0/models` carry no
  `anthropic-version`

### Requirement: The server's type

LADO SHALL name a server Ollama when `GET /api/version` gives a version, LM Studio when
`GET /api/v0/models` gives a list, then by its model list asked without
`anthropic-version`: Anthropic-compatible when it has Anthropic's shape, OpenAI-compatible
when it has OpenAI's; when that gives no list, Anthropic-compatible when the model list
asked with `anthropic-version` has Anthropic's shape; and otherwise by the APIs it proved:
the Messages API as Anthropic-compatible, chat completions or the Responses API as
OpenAI-compatible.

#### Scenario: LM Studio
- **WHEN** the server answers `GET /api/v0/models` with a list
- **THEN** it prints `type: LM Studio`

#### Scenario: A gateway that speaks both APIs
- **WHEN** the server (LiteLLM) lists its models in OpenAI's shape when asked without
  `anthropic-version` and in Anthropic's shape when asked with it, and proves all three APIs
- **THEN** it prints `type: OpenAI-compatible`, its models once each, and no `not:` line;
  `lado model-server add` saves it so and `lado model-server list` shows
  `OpenAI-compatible`

#### Scenario: An Anthropic API that lists its models only with its version header
- **WHEN** the server refuses `GET /v1/models` without `anthropic-version` with 400, lists
  `claude-x` in Anthropic's shape with it, and proves the Messages API
- **THEN** it prints `type: Anthropic-compatible` and `models: claude-x`

### Requirement: A server's models or no list

LADO SHALL take a server's models from `GET /v1/models` asked without `anthropic-version`;
when that gives no list, from the one asked with it when that is a list in Anthropic's
shape. A list it cannot read SHALL be no list with why, not a failure: `models: no list
(<why>)`, the why of the list asked without the header. An empty list SHALL print `models:
none`.

#### Scenario: A list that fails
- **WHEN** Ollama answers `GET /v1/models` with 500
- **THEN** it prints `models: no list (GET /v1/models: 500)` and the type and CLIs, and
  exits 0

#### Scenario: A list in another shape with the header
- **WHEN** the server lists `gpt-oss-20b` in OpenAI's shape without `anthropic-version` and
  `other` in Anthropic's shape with it
- **THEN** it prints `models: gpt-oss-20b`

### Requirement: lado model-server remove refuses a server a model uses

`lado model-server remove <name>` SHALL remove the saved server and its key file, print
`Removed model server "<name>".` and exit 0. While a configured model refers to the
server it SHALL be refused, changing nothing, with `model server "<name>" is used by the
models <model>, <model>; remove them first: lado model remove "<model>" "<model>"`, one
command naming every model that refers to it, and exit 1. A name no server has SHALL be
refused with exit 1.

#### Scenario: A server a model uses
- **WHEN** the model `Локальная Qwen` refers to `LM Studio дома` and the human runs `lado
  model-server remove "LM Studio дома"`
- **THEN** it exits 1 with the line naming `Локальная Qwen`, and the server and its key
  file stay

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

## ADDED Requirements

### Requirement: Embeddings models are marked in a server's models

A model that `GET /api/v0/models` types `embeddings` SHALL be shown in the `models:` line
of `lado model-server probe` and `lado model-server add` as `<model> (embeddings)`. A
server that gives no type for a model SHALL show it as before.

#### Scenario: LM Studio with an embeddings model
- **WHEN** LM Studio lists `qwen3-8b` and `text-embedding-nomic-embed-text-v1.5` and types
  them `llm` and `embeddings` in `GET /api/v0/models`
- **THEN** it prints `models: qwen3-8b, text-embedding-nomic-embed-text-v1.5 (embeddings)`

#### Scenario: Ollama
- **WHEN** the server is Ollama
- **THEN** its models are shown without a mark

### Requirement: A server at the address of another is saved and named

`lado model-server add` SHALL save a server whose address is that of another saved server,
and print `same address as model server "<its name>"` for each such server, after the
probe's lines and before `Saved model server "<name>".` (or `Replaced …`), exit 0; with
`--replace` the server replaced SHALL NOT count, and a failed probe SHALL print no such
line.

#### Scenario: The same LM Studio under a second name
- **WHEN** `macpro` is saved at `http://10.73.10.235:1234` and the human runs `lado
  model-server add lms 10.73.10.235:1234/v1/`, where LM Studio answers
- **THEN** it prints the probe's lines, `same address as model server "macpro"` and `Saved
  model server "lms".`, exits 0, and `lado model-server list` shows both

#### Scenario: Replacing a server at its own address
- **WHEN** `lms` is saved at `http://h:1234` and the human runs `lado model-server add lms
  http://h:1234/ --key --replace` with a new key
- **THEN** it prints no `same address` line and `Replaced model server "lms".`

### Requirement: Two addresses of one server

Two addresses of servers SHALL be the same when, after the probe's normalisation (`http://`
added, `/v1` and `/` dropped at the end), their scheme, host ignoring case, port (80 for
`http`, 443 for `https` when none is given) and path are the same.

#### Scenario: Three spellings of one address
- **WHEN** a server is saved at `http://h:1234` and the human adds another at `h:1234/v1/`,
  at `http://H:1234/` or at `http://h:1234`
- **THEN** each prints `same address as model server "<the first's name>"`

#### Scenario: Another port or path
- **WHEN** a server is saved at `http://h:1234` and the human adds another at
  `http://h:1235` or at `http://h:1234/llm`
- **THEN** no `same address` line is printed
