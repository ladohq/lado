## Purpose

What a model server in the human's network is, from its address and, when it asks for one,
its key: its type, its models and the agent CLIs that can use it, proven by requests that
generate nothing, with one clear line for each way it can fail and the key kept nowhere.

## ADDED Requirements

### Requirement: lado model-server probe names a server's type, models and CLIs

`lado model-server probe <address>` SHALL print the server's address, its type (Ollama,
LM Studio, OpenAI-compatible or Anthropic-compatible), its models, the agent CLIs that can
use it with the API each uses, and each CLI that cannot with the API it lacks, and exit 0.
`lado model-server` alone SHALL print its help. Nothing else in LADO SHALL change.

#### Scenario: An Ollama server that speaks two APIs
- **WHEN** the human runs `lado model-server probe http://192.168.1.10:11434` and the
  server is Ollama with the models `llama3.1:8b` and `qwen2.5-coder:7b`, answering chat
  completions and the Responses API but not the Anthropic Messages API
- **THEN** it prints `http://192.168.1.10:11434`, `type: Ollama`,
  `models: llama3.1:8b, qwen2.5-coder:7b`,
  `CLIs: Kilo CLI, OpenCode (chat completions); Codex CLI (Responses API)` and
  `not: Claude Code (no Anthropic Messages API)`, and exits 0

#### Scenario: A server every CLI can use
- **WHEN** the server answers all three APIs
- **THEN** the output has no `not:` line

### Requirement: The CLIs follow from the APIs a server proves

A CLI SHALL be named as able to use a server exactly when the server proved the API its
provider declares: chat completions for OpenCode and Kilo, the Responses API for Codex,
the Anthropic Messages API for Claude Code. The server's type SHALL NOT decide it.

#### Scenario: An OpenAI-compatible server with chat completions only
- **WHEN** the server lists its models in OpenAI's shape and answers only chat completions
- **THEN** `type: OpenAI-compatible`, the CLIs are Kilo CLI and OpenCode, and Codex CLI
  and Claude Code are under `not:`

#### Scenario: A server with the Responses API only
- **WHEN** the server answers only the Responses API
- **THEN** the CLIs are Codex CLI alone

#### Scenario: An Anthropic-compatible server
- **WHEN** the server lists its models in Anthropic's shape and answers only the Messages
  API
- **THEN** `type: Anthropic-compatible`, the CLIs are Claude Code alone

#### Scenario: A server that proves no API
- **WHEN** the server lists its models but answers none of the three APIs
- **THEN** it prints `CLIs: none` and every CLI under `not:`, and exits 0

### Requirement: An API is proven without generating

LADO SHALL prove each API with one POST whose body is `{}`: an answer 400 or 422 with a
JSON body proves it, any other answer does not. It SHALL send at most one request per
check to an address (the model list, Ollama's and LM Studio's own endpoints, one per API,
one control), each limited to 5 seconds, and none to another path, port or host.

#### Scenario: The requests of one probe
- **WHEN** the human probes an address that answers
- **THEN** the server receives at most `GET /v1/models`, `GET /api/version`,
  `GET /api/v0/models` and one `POST` with the body `{}` to each of
  `/v1/chat/completions`, `/v1/responses`, `/v1/messages` and `/v1/lado-no-such-api`

#### Scenario: An API missing
- **WHEN** the server answers `POST /v1/responses` with 404
- **THEN** the server is named as without the Responses API

### Requirement: A server that answers every POST alike proves no API

When the control `POST /v1/lado-no-such-api` answers 400 or 422 with a JSON body, no API
SHALL count as proven. A server whose type is otherwise unknown SHALL then be an unknown
server; one whose type is known SHALL print `APIs: cannot be told: <address> answers
<status> to any POST` and `CLIs: none`.

#### Scenario: A gateway that answers 400 to every path
- **WHEN** the server answers every request, `GET /v1/models` and the control included,
  with 400 and a JSON error
- **THEN** it prints `unknown server: <address> answered, but not as an OpenAI-compatible,
  Anthropic-compatible, Ollama or LM Studio server (GET /v1/models: 400; it answers 400 to
  any POST, so its APIs cannot be told)` and exits 1

#### Scenario: A server with a list that answers every POST alike
- **WHEN** the server lists its models in OpenAI's shape and answers every POST, the
  control included, with 400 and a JSON error
- **THEN** it prints `type: OpenAI-compatible`, its models, `APIs: cannot be told:
  <address> answers 400 to any POST` and `CLIs: none`, and exits 0

### Requirement: The server's type

LADO SHALL name a server Ollama when `GET /api/version` gives a version, LM Studio when
`GET /api/v0/models` gives a list, Anthropic-compatible when its model list has
Anthropic's shape, OpenAI-compatible when it has OpenAI's, and otherwise by the APIs it
proved: the Messages API as Anthropic-compatible, chat completions or the Responses API
as OpenAI-compatible.

#### Scenario: LM Studio
- **WHEN** the server answers `GET /api/v0/models` with a list
- **THEN** it prints `type: LM Studio`

### Requirement: A server's models or no list

LADO SHALL take a server's models from `GET /v1/models`. A list it cannot read SHALL be
no list with why, not a failure: `models: no list (<why>)`. An empty list SHALL print
`models: none`.

#### Scenario: A list that fails
- **WHEN** Ollama answers `GET /v1/models` with 500
- **THEN** it prints `models: no list (GET /v1/models: 500)` and the type and CLIs, and
  exits 0

### Requirement: The address as given, its scheme added visibly

An address without a scheme SHALL get `http://`, and the first line SHALL say
`(added http://)`. A trailing `/v1` and trailing `/` SHALL be dropped and any other path
kept. An address that is not `http` or `https`, or holds a user, a password, a query or a
fragment, SHALL be refused with exit 2.

#### Scenario: No scheme
- **WHEN** the human probes `localhost:11434/v1/`
- **THEN** the first line is `http://localhost:11434 (added http://)`

#### Scenario: A password in the address
- **WHEN** the human probes `http://me:pw@host:4000`
- **THEN** it exits 2 with a line that does not contain `pw`

### Requirement: An address that does not answer

An address that gives no HTTP answer to the model list within 5 seconds SHALL stop the
probe, with nothing more sent, and exit 1 with `<address> does not answer (<why>)`. A TLS
failure SHALL exit 1 with `<address>: TLS failed (<why>); a company's CA goes in the file
SSL_CERT_FILE names`.

#### Scenario: Nothing listens
- **WHEN** the human probes `http://127.0.0.1:<a closed port>`
- **THEN** it prints `http://127.0.0.1:<port> does not answer (connection refused)` and
  exits 1

#### Scenario: A server that hangs
- **WHEN** the server accepts the connection and never answers
- **THEN** within about 5 seconds it prints `does not answer (no answer in 5 s)` and exits 1

### Requirement: localhost in LADO's container

When LADO runs in its container and a `localhost`, `127.0.0.0/8` or `::1` address does
not answer, LADO SHALL add the line `LADO runs in a container, where localhost is the
container itself; a server on your machine: lado model-server probe
<scheme>://host.docker.internal:<port><path> (not tried)`. It SHALL NOT send a request to
any address but the one given.

#### Scenario: Ollama on the host, LADO in Docker
- **WHEN** `LADO_CONTAINER=1` and the human probes `localhost:11434`, which does not answer
- **THEN** it prints the hint with `http://host.docker.internal:11434`, sends nothing to
  that address, and exits 1

#### Scenario: Outside the container
- **WHEN** `LADO_CONTAINER` is unset and `localhost:11434` does not answer
- **THEN** no hint is printed

### Requirement: The server's key is asked and kept nowhere

`--key` SHALL read the key without echo on a terminal, else from stdin, and send it as
`Authorization: Bearer` and `x-api-key`. A key given on the command line or an empty one
SHALL be refused. The key's value SHALL appear in no output, log, error journal, file of
`LADO_HOME` or `lado.db`.

#### Scenario: A key piped in
- **WHEN** the human runs `printf '%s' "$KEY" | lado model-server probe http://gw:4000 --key`
- **THEN** each request to the server carries the key, and neither the output nor any
  file of `LADO_HOME` holds its value

#### Scenario: A key on the command line
- **WHEN** the human runs `lado model-server probe http://gw:4000 --key s3cr3t`
- **THEN** it exits 1 without sending a request, and the line does not contain `s3cr3t`

### Requirement: A server that asks for a key or refuses it

Any 401 or 403 among the answers SHALL exit 1: without a key with `<address> asks for a
key (<status>): run lado model-server probe <address> --key`, with one with `<address>
refused the key (<status>)`.

#### Scenario: No key given
- **WHEN** the server answers `GET /v1/models` with 401 and no key was given
- **THEN** it prints `http://gw:4000 asks for a key (401): run lado model-server probe
  http://gw:4000 --key` and exits 1

### Requirement: An unknown server

An address that answers but proves no type and no API SHALL exit 1 with `unknown server:
<address> answered, but not as an OpenAI-compatible, Anthropic-compatible, Ollama or LM
Studio server (GET /v1/models: <answer>)`. LADO SHALL follow no redirect: a redirect is
an answer that proves nothing.

#### Scenario: A web page
- **WHEN** the address is a web server that answers 404 to every request
- **THEN** it prints the unknown server's line with `GET /v1/models: 404` and exits 1

#### Scenario: A redirect
- **WHEN** the server answers every request with 301 to another host
- **THEN** no request reaches that host, and the line names `301 to <location>`
