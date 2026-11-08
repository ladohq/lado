## MODIFIED Requirements

### Requirement: lado model-server probe names a server's type, models and CLIs

`lado model-server probe <address>` SHALL print the server's address, its type (Ollama,
LM Studio, OpenAI-compatible or Anthropic-compatible), its models, the agent CLIs that can
use it with the API each uses, and each CLI that cannot with the API it lacks, and exit 0.
The CLIs SHALL come in LADO's one order of the agent CLIs (Claude Code, Codex CLI, Kilo CLI,
OpenCode), the order of Settings → Agent CLIs. `lado model-server` alone SHALL print its help.
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

### Requirement: Why a server has no list is given only with no list

A probe SHALL give why a server has no list of models only when it has none: when the list
asked without `anthropic-version` fails and the one asked with it gives the models, the
probe SHALL have those models and no why. Every place that shows the why (`lado
model-server probe` and `add`, Settings → Model servers) SHALL show it only with no list.

#### Scenario: An Anthropic API that lists its models only with its version header
- **WHEN** the server refuses `GET /v1/models` without `anthropic-version` with 400 and
  lists `claude-x` in Anthropic's shape with it
- **THEN** the probe has the models `claude-x` and no why, and Settings → Model servers shows
  `claude-x` with no `no list` reason

#### Scenario: A list that fails both ways
- **WHEN** the server answers `GET /v1/models` with 500 with and without the header
- **THEN** the probe has no list and its why is `GET /v1/models: 500`

### Requirement: A late answer is not a missing API

An API whose POST got no answer even the second time SHALL be neither proven nor missing: `lado model-server probe` SHALL name it `did not answer in time`, not `no <API>`, `lado model-server add` SHALL save the server with a warning naming it, and `lado model add` and a start on a CLI of that API SHALL refuse, saying it did not answer in time and to try again.

#### Scenario: A slow POST that answers the second time
- **WHEN** `POST /v1/messages` gets no answer within 5 seconds and a 400 with a JSON body the second time
- **THEN** the server is named as with the Anthropic Messages API

#### Scenario: The probe
- **WHEN** `POST /v1/messages` gets no answer either time
- **THEN** the `not:` line reads `Claude Code (Anthropic Messages API did not answer in time)`, and the probe exits 0

#### Scenario: lado model add
- **WHEN** `lado model add --cli claude --server Шлюз <model>` meets that server
- **THEN** it exits non-zero with a line saying the Anthropic Messages API of `Шлюз` did not answer in time and to try again, and it does not say the server has no such API

#### Scenario: An API that answers no
- **WHEN** `POST /v1/messages` answers 404 at once
- **THEN** it is asked once, and the server is named as without that API

#### Scenario: A control that is late
- **WHEN** the control POST gets no answer the first time
- **THEN** it is sent once more with the late POSTs, and a control refused the same way proves nothing as before

#### Scenario: Settings → Models
- **WHEN** a probe of Settings → Model servers, in its form or of a saved server, meets a late API
- **THEN** the probe's `apis_why` names it, once, and the page reads `⚠ APIs: cannot be told:` with those words

#### Scenario: Trying again
- **WHEN** the check of a model in Settings → Model servers met a late API and the server answers now
- **THEN** the next check asks the server anew: a probe with a late API is not kept
