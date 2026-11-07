## ADDED Requirements

### Requirement: The form names a CLI the server's type does not suit

What answered a server's check SHALL name, under its Agent CLIs, each CLI that has the server's API but cannot use a server of that type, with why, and the server's list SHALL offer no column for that CLI.

#### Scenario: LM Studio
- **WHEN** the human checks a server that is LM Studio and proves chat completions and the Responses API
- **THEN** Agent CLIs reads `Kilo CLI, OpenCode`, a warning under it reads `Codex CLI: its Responses API loses Codex CLI's MCP tools, so the agent could not talk to LADO`, and the list of models has no Codex CLI column

#### Scenario: Another server
- **WHEN** the human checks OpenRouter
- **THEN** Agent CLIs names Codex CLI, and no such warning shows
