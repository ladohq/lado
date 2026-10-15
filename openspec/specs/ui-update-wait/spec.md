# ui-update-wait Specification

## Purpose
When the web UI's wait for an update it started ends: only once the update's result is
written, the UI server is back, and `update.lock` is released, so the System panel never
keeps an answer that says an update still runs.

## Requirements

### Requirement: The update wait ends once the update's lock is released

The web UI's wait for an update it started (U2) SHALL end only when `GET /api/update`
answers `running` false, besides its other conditions: `UpdateInfo.last` has the id the
`POST /api/update` answered and an outcome other than `running`, and the server's
`started_at` is newer than the one before, or the result is a `failed` one with no log
(the update ended before it started). The `UpdateInfo` the page keeps when the wait ends
SHALL be one with `running` false, so the System panel's Update… button and `why_not`
reflect no running update.

#### Scenario: The result is written but the lock is still held
- **WHEN** a poll during the wait finds the result of the waited id `rolled_back`, a
  server started after the one before, and `running` true
- **THEN** the wait goes on, and the page keeps polling

#### Scenario: The lock is released
- **WHEN** a later poll finds the same result and server, and `running` false
- **THEN** the wait ends, the result shows, and the System panel offers Update… while a
  newer LADO is available and nothing else refuses the update

#### Scenario: An update that did not start
- **WHEN** a poll finds a `failed` result of the waited id with no log, on the same
  server, and `running` false
- **THEN** the wait ends
