## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: An API is proven without generating

LADO SHALL prove each API with one POST whose body is `{}`: an answer 400 or 422 with a
JSON body proves it, any other answer does not. It SHALL send at most one request per
check to an address (the model list, the model list in Anthropic's way, Ollama's and LM
Studio's own endpoints, one per API, one control), each limited to 5 seconds, and none to
another path, port or host. A POST with no answer in that time SHALL be sent once more, limited to 15
seconds.

#### Scenario: The requests of one probe
- **WHEN** the human probes an address that answers
- **THEN** the server receives at most `GET /v1/models` twice (once without
  `anthropic-version` and once with it), `GET /api/version`, `GET /api/v0/models` and one
  `POST` with the body `{}` to each of `/v1/chat/completions`, `/v1/responses`,
  `/v1/messages` and `/v1/lado-no-such-api`

#### Scenario: An API missing
- **WHEN** the server answers `POST /v1/responses` with 404
- **THEN** the server is named as without the Responses API
