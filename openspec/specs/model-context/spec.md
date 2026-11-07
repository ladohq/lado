# model-context Specification

## Purpose
What LADO learns of a model's context from its server, how an agent's CLI is told it, and what
happens when the context is too small for an agent to take a turn.

## Requirements

### Requirement: LADO reads a model's context from its server

At a start, LADO SHALL ask each model server of the agent's config for the context of its models, in
one short read per server, with the server's key and following no redirect. It SHALL take LM Studio's
`loaded_context_length`, the `context_length` of Ollama's running model, and a list item's
`max_input_tokens`, else `context_length`, else `max_model_len`, with `max_output_tokens`, else
`top_provider.max_completion_tokens`. Any other model SHALL have no known context.

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

#### Scenario: cloud.ru's list

- **WHEN** an item of `/v1/models` holds `context_length: 131072` and `max_model_len: 131072`
- **THEN** the context is 131072 and no output is reported

#### Scenario: OpenRouter's list

- **WHEN** an item holds `context_length: 131072` and `top_provider: {max_completion_tokens: 117964}`
- **THEN** the context is 131072 and the output 117964

#### Scenario: A list of both

- **WHEN** an item holds `max_input_tokens: 16000` and `context_length: 32768`
- **THEN** the context is 16000

#### Scenario: An item with a null context

- **WHEN** an item holds `context_length: null`, as cloud.ru's speech models do
- **THEN** that model has no known context

### Requirement: A known context goes to the agent's config

For a model with a known context, the config of an OpenCode or Kilo agent SHALL hold `limit` with both
`context` and `output`, as OpenCode refuses a `limit` without `output`. `output` SHALL be the reported
output when there is one, else 8192, or 32000 for a context of 131072 or more, and at most a quarter
of the context. A model with
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

#### Scenario: A large context with no reported output

- **WHEN** the context of a model is 262144 and no output is reported
- **THEN** its config holds `limit: {context: 262144, output: 32000}`

#### Scenario: A large reported output

- **WHEN** the context is 131072 and the reported output 117964
- **THEN** its config holds `limit: {context: 131072, output: 32768}`

### Requirement: A start on too small a context is warned about

When the known context of the model an agent starts on is below what its CLI needs (OpenCode 32768, Kilo 49152,
Claude Code 65536), `lado start`, the start's warnings and the launch window SHALL warn, naming the model,
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
the section of `docs/install.md`. In the launch window the name `docs/install.md` SHALL be a link to that
section on GitHub, opening in a new tab; `lado start` SHALL print the same text with no link. The folded
Advanced SHALL name each warning of the chosen model in a few words of its own.

#### Scenario: A server of a known type

- **WHEN** the model too small is on LM Studio
- **THEN** the warning names `lms load --context-length`

#### Scenario: The link of the launch window

- **WHEN** the launch window shows the warning
- **THEN** `docs/install.md ↗` in it links to `docs/install.md#what-to-expect-of-a-small-model` on
  GitHub, and a warning about a key over http has no link

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
  message's body holds the server's whole text

#### Scenario: The body does not repeat the line

- **WHEN** a turn is stopped with a message of the server
- **THEN** the message's body holds that text alone, without LADO's words

#### Scenario: A fixed request larger than the context

- **WHEN** every request of a turn is refused as a context overflow, and only the compaction's own
  requests succeed
- **THEN** the third overflow stops the turn, the agent becomes idle, and the chat shows the turn's error

#### Scenario: A compaction that helps

- **WHEN** an overflow is followed by a compaction and a successful step
- **THEN** the turn goes on and the count starts again

### Requirement: A server's refusal for context reads in LADO's words

A turn of OpenCode or Kilo that ends on a server's refusal with `exceed_context_size_error` (LM Studio,
llama.cpp), which both CLIs report as `UnknownError`, SHALL end on the error `ContextOverflowError: the
model's context is too small for the agent's request`, followed by the server's own `request (<n> tokens)
exceeds the available context size (<m> tokens)` when its text holds that. The message's body SHALL hold
the error's whole text as the CLI gave it.

#### Scenario: LM Studio on a small context

- **WHEN** a turn ends on `UnknownError` whose message holds `exceed_context_size_error` and `request
  (21556 tokens) exceeds the available context size (16384 tokens)`
- **THEN** the chat's line reads `turn of supervisor ended on an error: ContextOverflowError: the
  model's context is too small for the agent's request; request (21556 tokens) exceeds the available
  context size (16384 toke…; it is idle`, cut to the limit of a message's summary, and the body holds
  the raw JSON

#### Scenario: Another unknown error

- **WHEN** a turn ends on an `UnknownError` that does not hold `exceed_context_size_error`
- **THEN** its line and body stay as the CLI gave them

### Requirement: A known context goes to a Claude agent

A Claude agent on a server's model with a known context SHALL have that context as
`CLAUDE_CODE_MAX_CONTEXT_TOKENS` in the `env` of its own settings, and as
`CLAUDE_CODE_MAX_OUTPUT_TOKENS` the output of the rule for OpenCode and Kilo: the server's, else 8192, or 32000 for a context of
131072 or more, at most a quarter of the context and at most 16384. With no known context the variables SHALL be absent.

#### Scenario: A known context
- **WHEN** a Claude agent starts on a model whose context is 65536
- **THEN** its settings' `env` has `CLAUDE_CODE_MAX_CONTEXT_TOKENS` `65536` and
  `CLAUDE_CODE_MAX_OUTPUT_TOKENS` `8192`, and its requests ask for no more

#### Scenario: A large prompt on a context of 64K
- **WHEN** the prompt is 45K tokens and the server ends a request over its context of 65536
- **THEN** the turn ends as on any model

#### Scenario: No known context
- **WHEN** the server reports nothing of the model
- **THEN** its settings' `env` has neither variable

#### Scenario: A large context
- **WHEN** a Claude agent starts on a model whose context is 262144 and no output is reported
- **THEN** its settings' `env` has `CLAUDE_CODE_MAX_OUTPUT_TOKENS` `16384`

### Requirement: A start on a public server with no known context is warned about

When the model an agent starts on is on a server outside the human's machine and network, by the hosts of the rule on a key over plain http and by a name with no dot or ending in `.local`, `.lan`, `.internal` or `.home.arpa`, and its context is not known, `lado start`, the start's warnings and the launch window SHALL warn, naming the model and the server and saying that compaction comes late and the output has no limit; the agent SHALL start. The folded Advanced SHALL name it `context unknown`.

#### Scenario: A provider that lists no context

- **WHEN** a session starts on a model of `https://llm.example.com` whose list gives no context
- **THEN** the warning names the model and the server, and the session starts

#### Scenario: A local server

- **WHEN** a session starts on a model of `http://192.168.1.10:1234` or `localhost` with no known context
- **THEN** no such warning is given

#### Scenario: A name of the human's network

- **WHEN** a session starts on a model of `http://mac-studio.local:1234`, `http://gpu-box:8000` or `http://ollama.lan:11434` with no known context
- **THEN** no such warning is given, and a key over plain http to that name is warned about as before

#### Scenario: The folded Advanced

- **WHEN** the chosen model is on such a server
- **THEN** the folded Advanced reads `⚠ context unknown`

#### Scenario: A known context

- **WHEN** the same server lists the model's context
- **THEN** no such warning is given

### Requirement: A known context goes to a Codex agent

For a model with a known context, a Codex agent's config SHALL hold `model_context_window` with that context and `model_auto_compact_token_limit` with the context less the output room, and its list entry the context. A model with no known context SHALL have neither key and a null context in its entry. Codex has no setting for its output, so nothing SHALL cap it.

#### Scenario: A context of 65536
- **WHEN** a Codex agent starts on a model whose context is 65536 and no output is reported
- **THEN** its config holds `model_context_window = 65536` and `model_auto_compact_token_limit = 57344`

#### Scenario: No known context
- **WHEN** a Codex agent starts on a model of a public server that reports no context
- **THEN** its config has neither key, and the start warns as on the other CLIs

#### Scenario: The real CLI compacts
- **WHEN** real Codex on a fake server has its token use pass that limit
- **THEN** its next turn is preceded by a compaction request to the same server
