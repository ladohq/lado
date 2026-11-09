## MODIFIED Requirements

### Requirement: The human sees and changes the choice

Settings SHALL have a page Statistics (`/settings/statistics`) with one row, "Send anonymous
statistics and errors to LADO's maintainers": a switch, on only while the choice is on, disabled
while the environment or a missing endpoint switches sending off, and a line for its state with
What LADO collects ↗. `lado telemetry` SHALL have `status` (the default), `on`, `off` and
`show`; `on` and `off` SHALL be refused inside an agent; `off` SHALL drop what is queued.

#### Scenario: Turned off in Settings
- **WHEN** the human turns the switch off while two errors are queued
- **THEN** the choice is `off`, the queue is empty, and nothing is sent

#### Scenario: Not chosen yet
- **WHEN** the human opens Settings → Statistics before any choice
- **THEN** the switch is off, the row says "Nothing is sent until you choose. What LADO
  collects ↗", and the banner still asks

#### Scenario: Turned on from not chosen
- **WHEN** the human turns the switch on before any choice
- **THEN** the choice is `on` and the banner no longer shows

#### Scenario: Sending
- **WHEN** the choice is `on` and the last send was today at 09:12
- **THEN** the switch is on, the row says "Last sent today at 09:12. What LADO collects ↗", and
  What the next report sends opens under it

#### Scenario: No endpoint in Settings
- **WHEN** this LADO has no statistics endpoint
- **THEN** the switch is off and disabled and the row says "No statistics endpoint: nothing is
  sent."

#### Scenario: An agent tries to switch it on
- **WHEN** an agent runs `lado telemetry on`
- **THEN** it is refused and the choice is unchanged
