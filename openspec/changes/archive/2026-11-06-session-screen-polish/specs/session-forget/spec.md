## MODIFIED Requirements

### Requirement: Stop can forget the session in one go

The Stop popover of a running session SHALL have, before `Stop <name>`, when it offers it (see
"Stop and forget is not offered for a session with open runs"), a second dangerous button
`Stop and forget` (its tooltip "Stops it, then deletes its history for good"). It SHALL stop the
session, then forget it without `force`, then go to `/sessions`. When the stop succeeds and the
forget is refused, the session SHALL stay stopped and the popover SHALL show the core's reason.

#### Scenario: A session with no open runs
- **WHEN** the human opens Stop on running lad-92 and presses `Stop and forget`
- **THEN** lad-92 is stopped and forgotten, and the page is `/sessions`

## REMOVED Requirements

### Requirement: Stop and forget is off for a session with open runs

**Reason**: A red button that is off read almost like one that works (LAD-189, F27).
**Migration**: "Stop and forget is not offered for a session with open runs" below.

## ADDED Requirements

### Requirement: Stop and forget is not offered for a session with open runs

The Stop popover SHALL show `Stop and forget` only once the stop preview is read and names no open
run. When it names open runs the popover SHALL say, below its buttons in 13 px `--muted`, "It has
open runs, so it can be forgotten only from the Stopped list after stopping."

#### Scenario: A session with open runs
- **WHEN** the human opens Stop on lad-80, which has two open runs
- **THEN** there is no `Stop and forget`, the line about open runs shows below the buttons, and
  `Stop lad-80` works as before

#### Scenario: While the preview loads
- **WHEN** the human opens Stop and the preview is not read yet
- **THEN** no `Stop and forget` shows
