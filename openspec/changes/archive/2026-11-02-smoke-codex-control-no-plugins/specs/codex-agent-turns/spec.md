## MODIFIED Requirements

### Requirement: A Codex agent has none of Codex's own subagents

The config.toml LADO writes for each Codex agent SHALL switch Codex's own subagents off for
every model, both of Codex's versions of them: `features.multi_agent = false`,
`features.multi_agent_v2 = false` and `[agents] enabled = false`. The request Codex sends to
the model SHALL then carry none of its subagent tools (`spawn_agent`, `wait_agent`,
`send_input`, `resume_agent`, `close_agent`, the `collaboration` namespace), whatever the
model's metadata turns on.

#### Scenario: The agent's config
- **WHEN** LADO launches a Codex agent
- **THEN** its config.toml has `multi_agent = false` and `multi_agent_v2 = false` under
  `[features]` and `enabled = false` under `[agents]`

#### Scenario: A model whose metadata turns the subagents on
- **WHEN** a Codex supervisor whose model is one that Codex's metadata gives the
  `collaboration` tools (gpt-6-sol with Codex 0.162.0) sends its first request
- **THEN** the request's tools hold no `collaboration` namespace and no `spawn_agent` or
  `wait_agent`, while a plain `codex exec` with the same model and none of LADO's config,
  only its plugins switched off (`-c features.plugins=false`, so it starts no background
  sync of Codex's plugins catalogue that outlives it), does get them

#### Scenario: The human's first message after the start
- **WHEN** a new Codex session's supervisor on a ChatGPT login has ended its start turn
  and the human writes "hi"
- **THEN** the message is delivered, the supervisor answers the human, and it called no
  subagent tool in either turn
