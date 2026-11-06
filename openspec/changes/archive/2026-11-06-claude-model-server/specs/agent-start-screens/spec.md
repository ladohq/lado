## MODIFIED Requirements

### Requirement: An agent with no hook after its launch waits for an answer in its terminal

The session loop SHALL put an agent of any provider that is `starting` with no hook yet, its
provider's limit or more after its CLI's launch, into `waiting` with the reason `Waiting for an
answer in its terminal: no sign from it <limit> s after its start. Open its terminal.`; its first
hook SHALL make it ready. The limit SHALL be 30 s, and 45 s for OpenCode and Kilo, past the 30 s
their server plugin counts from its own start.

#### Scenario: A screen LADO does not know
- **WHEN** a Claude agent's CLI shows a screen before its first hook and nobody answers it
  for 30 s
- **THEN** the agent is `waiting` with the reason, `lado ls` prints it and Needs you shows
  it with its terminal

#### Scenario: The human answers in the terminal
- **WHEN** that agent's human answers the screen and the CLI fires its session start
- **THEN** the agent is ready and takes its queue, with no restart

#### Scenario: A slow start under the limit
- **WHEN** an agent's first hook comes 20 s after its window opened
- **THEN** it was never `waiting`

#### Scenario: After the login's wait
- **WHEN** an agent waited 5 minutes for its login and its window starts the CLI
- **THEN** it is measured from the moment its window started the CLI, not from the
  window's opening

#### Scenario: Any provider
- **WHEN** a Codex agent gives no hook 30 s after its launch, or a Kilo or OpenCode agent none 45 s
  after it
- **THEN** it is `waiting` with the reason, naming its limit

#### Scenario: A silent TUI is not shown as a question
- **WHEN** a Kilo agent's server plugin starts 5 s after the launch and its TUI never reports
- **THEN** the agent is ready 35 s after the launch, and it was never `waiting`
