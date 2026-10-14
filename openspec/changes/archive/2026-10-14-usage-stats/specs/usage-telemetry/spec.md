## MODIFIED Requirements

### Requirement: Statistics are counted when sent, never collected

LADO SHALL NOT keep usage data for sending: the daily report SHALL be counted from
`lado.db` when it is built and not stored after it is sent. Its counts SHALL come from the
local table `usage` (capability usage-stats), which LADO keeps for `lado stats` whatever
the human's choice about sending, and which no send reads but the report's counts; so a
session forgotten before the report is still counted. What waits to be sent SHALL be at
most 200 queued errors and the drop count; an error queued more than 30 days ago SHALL be
removed and counted as dropped; a report's window SHALL start no earlier than 30 days
before it is built.

#### Scenario: A month without network
- **WHEN** LADO is used daily for 45 days with the endpoint unreachable and records 500
  errors
- **THEN** `LADO_HOME/telemetry` holds at most 200 queued errors, none older than 30 days,
  and no report file; the first send after that posts one report counting the last 30
  days and the queued errors, and `errors_dropped` counts the rest

#### Scenario: A session forgotten before the report
- **WHEN** a session with two spawned agents is started and forgotten after the last
  report and before the next one
- **THEN** the next report counts its session and its two agents, as it would without
  the forget
