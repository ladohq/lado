# codex-agent-turns Specification

## Purpose
How a Codex agent's turns end: Codex's own subagents, which newer models turn on through
their metadata and which would hold a turn open while the model waits for them, are
switched off in every Codex agent's config, and LADO's first input to a Codex agent asks it
to end its turn instead of waiting.

## Requirements

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
  `wait_agent`, while a plain `codex exec` with the same model and no LADO config does get
  them

#### Scenario: The human's first message after the start
- **WHEN** a new Codex session's supervisor on a ChatGPT login has ended its start turn
  and the human writes "hi"
- **THEN** the message is delivered, the supervisor answers the human, and it called no
  subagent tool in either turn

### Requirement: LADO's first input ends the agent's turn

`runtime.FIRST_INPUT`, the line LADO gives as its first input an agent whose CLI starts its
session only on its first input and whose queue is empty
(`Capabilities.session_start_on_first_input`), SHALL ask the agent to end its turn and
SHALL NOT ask it to wait: `session started; nothing to do yet: end this turn, the next
message starts a new one`.

#### Scenario: A new Codex session without a first message
- **WHEN** a session of provider `codex` starts without `prompt`
- **THEN** its supervisor's argv ends with `[from lado] session started; nothing to do yet:
  end this turn, the next message starts a new one`

#### Scenario: Another provider
- **WHEN** a session of provider `claude`, `kilo` or `opencode` starts without `prompt`
- **THEN** LADO queues no `runtime.FIRST_INPUT` for its supervisor
