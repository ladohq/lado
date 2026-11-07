## MODIFIED Requirements

### Requirement: Details' state line says the state once

The state line SHALL be the mark's words without `running`, then the run time. A stopped
session's line SHALL say `stopped` once, in its time.

#### Scenario: A running session
- **WHEN** the human opens Details of an idle session of 2 agents
- **THEN** the state line starts with `idle`, then the run time

#### Scenario: A stopped session
- **WHEN** the human opens Details of a session stopped 2 days ago after 4 hours
- **THEN** the state line starts with `stopped 2 d ago · ran 4 h`
