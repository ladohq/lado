## MODIFIED Requirements

### Requirement: The CLIs follow from the APIs a server proves

A CLI SHALL be named as able to use a server exactly when the server proved the API its
provider declares: chat completions for OpenCode and Kilo, the Responses API for Codex,
the Anthropic Messages API for Claude Code, and its provider does not refuse the server's type. The
type SHALL decide nothing else: LM Studio does not suit Codex CLI, whose MCP tools its Responses API
loses, and `not:` SHALL name the CLI with why.

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

#### Scenario: LM Studio and Codex
- **WHEN** the server is LM Studio and answers chat completions and the Responses API
- **THEN** the CLIs are Kilo CLI and OpenCode, and the output has
  `not: Claude Code (no Anthropic Messages API), Codex CLI (its Responses API loses Codex CLI's MCP
  tools, so the agent could not talk to LADO)`

#### Scenario: A gateway with the Responses API
- **WHEN** the server is OpenAI-compatible and answers the Responses API
- **THEN** Codex CLI is among the CLIs, and a start of a Codex model on it runs there
