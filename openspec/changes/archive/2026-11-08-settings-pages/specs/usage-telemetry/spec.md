## MODIFIED Requirements

### Requirement: When nothing may be sent, LADO says why

When any condition of sending does not hold, nothing SHALL be queued or sent, and
`lado telemetry status`, `GET /api/telemetry` and the System panel SHALL say why: not
chosen, off, off by the named variable, or no statistics endpoint.

#### Scenario: Switched off by the environment
- **WHEN** the choice is `on` and the UI server runs with `DO_NOT_TRACK=1`
- **THEN** nothing is sent, Settings → Statistics shows the choice disabled with "Off:
  DO_NOT_TRACK is set in the server's environment.", and `lado telemetry status` run with that
  variable prints `statistics: off: DO_NOT_TRACK=1 is set (your choice: on)`

#### Scenario: No endpoint
- **WHEN** this LADO's project token is empty and `LADO_TELEMETRY_URL` is unset
- **THEN** no question is asked, nothing is sent, and `status` says this LADO has no
  statistics endpoint

### Requirement: The human sees and changes the choice

Settings SHALL have a page Statistics (`/settings/statistics`) with one row, "Send anonymous
statistics and errors to LADO's maintainers", with Send / Don't send, none picked while not
chosen and disabled while the environment or a missing endpoint switches it off, and one line
for its state with What LADO collects ↗. `lado telemetry` SHALL have `status` (the default),
`on`, `off` and `show`; `on` and `off` SHALL be refused inside an agent; `off` SHALL drop what
is queued.

#### Scenario: Turned off in Settings
- **WHEN** the human picks Don't send while two errors are queued
- **THEN** the choice is `off`, the queue is empty, and nothing is sent

#### Scenario: Not chosen yet
- **WHEN** the human opens Settings → Statistics before any choice
- **THEN** neither Send nor Don't send is picked, and the row says "Nothing is sent until you
  choose. What LADO collects ↗"

#### Scenario: Sending
- **WHEN** the choice is `on` and the last send was today at 09:12
- **THEN** the row says "Last sent today at 09:12. What LADO collects ↗", and What the next
  report sends opens under it

#### Scenario: No endpoint in Settings
- **WHEN** this LADO has no statistics endpoint
- **THEN** the choice is disabled and the row says "No statistics endpoint: nothing is sent."

#### Scenario: An agent tries to switch it on
- **WHEN** an agent runs `lado telemetry on`
- **THEN** it is refused and the choice is unchanged

### Requirement: The System panel and the system report show the statistics' state

The System panel SHALL have a row `Statistics` (`sending · last
<time>`, `off`, `not chosen`, or off by the variable) that leads to Settings → Statistics
(`/settings/statistics`), and the copied system report SHALL have a line `- Statistics: ...`.

#### Scenario: The panel's row
- **WHEN** the choice is `on` and the last send was today at 09:12
- **THEN** the System panel shows `Statistics` `sending · last today 09:12`, and the
  copied report has `- Statistics: on`

#### Scenario: From the panel to the page
- **WHEN** the human clicks the panel's row Statistics
- **THEN** the panel closes and `/settings/statistics` opens
