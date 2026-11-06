## Purpose

What LADO learns of a model's context from its server, how an agent's CLI is told it, and what
happens when the context is too small for an agent to take a turn.

## ADDED Requirements

### Requirement: LADO reads a model's context from its server

At a start, LADO SHALL ask each model server of the agent's config for the context of its models, in
one short read per server, with the server's key and following no redirect. It SHALL take LM Studio's
`loaded_context_length`, the `context_length` of Ollama's running model, and a list item's
`max_input_tokens` with `max_output_tokens`. Any other model SHALL have no known context, with no
warning about it.

#### Scenario: LM Studio with a loaded model

- **WHEN** LM Studio's list gives `qwen` `state: loaded` and `loaded_context_length: 65536`
- **THEN** the context of `qwen` is 65536

#### Scenario: A model LM Studio has not loaded

- **WHEN** LM Studio's list gives a model `not-loaded` and `max_context_length: 262144`
- **THEN** that model has no known context

#### Scenario: A gateway's list

- **WHEN** an item of `/v1/models` holds `max_input_tokens: 16000` and `max_output_tokens: 2048`
- **THEN** the context is 16000 and the output 2048

#### Scenario: A silent server

- **WHEN** a server of the config gives no answer within the ceiling
- **THEN** the start goes on and its models have no known context

### Requirement: A known context goes to the agent's config

For a model with a known context, the config of an OpenCode or Kilo agent SHALL hold `limit` with both
`context` and `output`, as OpenCode refuses a `limit` without `output`. `output` SHALL be the reported
output when there is one, at most a quarter of the context, and at most 8192 otherwise. A model with
no known context SHALL have no `limit`.

#### Scenario: A context with no reported output

- **WHEN** the context of a model is 65536 and no output is reported
- **THEN** its config holds `limit: {context: 65536, output: 8192}`

#### Scenario: A small context

- **WHEN** the context is 24000 and no output is reported
- **THEN** its config holds `limit: {context: 24000, output: 6000}`

#### Scenario: No known context

- **WHEN** the server reports nothing of a model
- **THEN** its entry in the config is as it was before this change

### Requirement: A start on too small a context is warned about

When the known context of the model an agent starts on is below what its CLI needs (OpenCode 32768,
Kilo 49152), `lado start`, the start's warnings and the launch window SHALL warn, naming the model,
its context and the need, and the agent SHALL start. An unknown context, or a model the agent does not
start on, SHALL give no such warning.

#### Scenario: Too small a model

- **WHEN** a session starts on Kilo on a model whose context is 16000
- **THEN** the warning names the model, 16000 and 49152, and the session starts

#### Scenario: The launch window

- **WHEN** the window checks a model whose context is below the need
- **THEN** the Model field shows the warning, and Start stays on

#### Scenario: Enough context

- **WHEN** the context is at the need or above it
- **THEN** no warning about the context is given

### Requirement: The warning says where to act

The warning about a context SHALL say where to change it: the setting of a server of a known type, and
the section of `docs/install.md`. The folded Advanced SHALL name each warning of the chosen model in a
few words of its own.

#### Scenario: A server of a known type

- **WHEN** the model too small is on LM Studio
- **THEN** the warning names `lms load --context-length`

#### Scenario: The folded Advanced

- **WHEN** the chosen model is too small and its key goes over plain http
- **THEN** the folded Advanced reads `⚠ key over http, context too small`; with the context alone,
  `⚠ context too small`

### Requirement: Overflows in a row stop the turn

The plugin SHALL stop a turn at the third context overflow with no successful model step of the turn
between them, and the turn SHALL end on that error, whatever the abort itself reports. The error's text
SHALL say the context is too small for the agent's request. A successful step of the turn or a new prompt
SHALL reset the count; the step of a compaction SHALL not, as its own small request succeeds in the loop
this stops.

#### Scenario: A long message of the server

- **WHEN** a turn is stopped and the server's message passes the limit of an error's line
- **THEN** the chat's line still says the context is too small and ends `; it is idle`, and the
  message's body holds the whole text

#### Scenario: A fixed request larger than the context

- **WHEN** every request of a turn is refused as a context overflow, and only the compaction's own
  requests succeed
- **THEN** the third overflow stops the turn, the agent becomes idle, and the chat shows the turn's error

#### Scenario: A compaction that helps

- **WHEN** an overflow is followed by a compaction and a successful step
- **THEN** the turn goes on and the count starts again
