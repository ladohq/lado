## ADDED Requirements

### Requirement: An agent's popup names its model without effort or source

An agent's popup in the session's head and on the terminals' strip SHALL have the fact Model: a
configured model's saved name, else the name the CLI reported, else `CLI default`. It SHALL name
neither the effort nor a source; those stay on the agent's page.

#### Scenario: The model in the head's popup
- **WHEN** the human holds the pointer over the avatar of a Codex agent on `gpt-5.6-sol`, effort
  `high`, both from its Codex config, of an OpenCode agent on `Локальная Qwen`, and of a Kilo
  agent whose CLI has named nothing
- **THEN** their popups' Model reads `gpt-5.6-sol`, `Локальная Qwen` and `CLI default`, and none
  names the effort or a source
