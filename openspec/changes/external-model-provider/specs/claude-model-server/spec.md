## ADDED Requirements

### Requirement: A Claude agent on a server repeats a request within a limit

The settings of a Claude agent on a server SHALL hold `CLAUDE_CODE_MAX_RETRIES` `7`, so that its repeats are limited: a 429 with no `Retry-After` ends the turn after about 70 seconds, as on OpenCode and Kilo, a 401 after about 150. A Claude agent on a built-in model SHALL have no such variable.

#### Scenario: The settings
- **WHEN** a Claude agent starts on a server's model
- **THEN** its settings' `env` has `CLAUDE_CODE_MAX_RETRIES` `7`

#### Scenario: A server that answers 429
- **WHEN** real Claude Code runs on a fake server that answers 429 to every request
- **THEN** the server gets at most 8 requests of the turn, and the turn ends

#### Scenario: A built-in model
- **WHEN** a Claude agent starts on `opus`
- **THEN** neither its settings nor its environment has the variable

### Requirement: A Claude agent on a server names no effort

The settings of a Claude agent on a server SHALL hold `CLAUDE_CODE_EFFORT_LEVEL` `auto`, so that its requests name no effort, also with an `effortLevel` in the user's own settings. A Claude agent on a built-in model SHALL have no such variable.

#### Scenario: The human's effort
- **WHEN** real Claude Code runs on a fake server, with `effortLevel` `xhigh` in the user's settings
- **THEN** no request holds `output_config`

### Requirement: A Claude agent on a large context compacts within it

A Claude agent on a server SHALL ask for at most 16384 tokens of output, so that the request at Claude Code's compaction fits the context on a server that counts input and `max_tokens` together.

#### Scenario: Reads up to a compaction
- **WHEN** real Claude Code reads files of 50 KB up to its compactions on a fake server of a context of 131072 that refuses a request over it
- **THEN** every request's input and `max_tokens` fit the context, and no turn ends on an error
