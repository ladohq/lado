## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: A known context goes to a Claude agent

A Claude agent on a server's model with a known context SHALL have that context as
`CLAUDE_CODE_MAX_CONTEXT_TOKENS` in the `env` of its own settings, and as
`CLAUDE_CODE_MAX_OUTPUT_TOKENS` the output the server reports or 8192, at most a quarter of the
context. With no known context the variables SHALL be absent.

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
