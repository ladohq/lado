## ADDED Requirements

### Requirement: A Claude agent on a server repeats a request within a limit

The settings of a Claude agent on a server SHALL hold `CLAUDE_CODE_MAX_RETRIES` `7`, so that a refused or failed request stops after about 70 seconds, as on OpenCode and Kilo. A Claude agent on a built-in model SHALL have no such variable.

#### Scenario: The settings
- **WHEN** a Claude agent starts on a server's model
- **THEN** its settings' `env` has `CLAUDE_CODE_MAX_RETRIES` `7`

#### Scenario: A server that answers 429
- **WHEN** real Claude Code runs on a fake server that answers 429 to every request
- **THEN** the server gets at most 8 requests of the turn, and the turn ends

#### Scenario: A built-in model
- **WHEN** a Claude agent starts on `opus`
- **THEN** neither its settings nor its environment has the variable
