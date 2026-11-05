## MODIFIED Requirements

### Requirement: On a phone the top bar is one line

In the phone layout the top bar SHALL be one line no higher than 52 px upright and 44 px
sideways, and SHALL not wrap. On a session's page it SHALL hold, left to right: Menu, the
session's status dot, the session's title (or name) with a chevron as a button that opens the
session's details, cut with "…" when long, the change feed's mark and Stop session. On another page
it SHALL hold Menu and the page's title. Menu and the session's actions SHALL be 44 by 44 px.

#### Scenario: A session's page upright
- **WHEN** the human opens session lad-95 on a phone 390 px wide
- **THEN** the top bar is one line holding Menu, the status dot, "lad-95", the live dot and
  Stop, and no folder, git, kit or CLI fact

#### Scenario: A long title
- **WHEN** the session's title is longer than the room left
- **THEN** it is cut with "…" and the line does not wrap

### Requirement: On a phone the session's details open from its name

In the phone layout a tap on the session's name in the top bar SHALL open a sheet over the
page's bottom, named by the session, with the content of Details on a computer, from the
same component (capability session-head): the state line, the session's id
and its project; the whole folder (wrapped, never cut) with Copy path; git (the remote, the
branch) with Copy URL; the kits, each with its version; the CLI with its version and
permission mode; and the buttons Rename, Copy link and All sessions. A tap outside the
sheet, Esc or its close button SHALL close it.

#### Scenario: The whole folder
- **WHEN** the session's folder is `/Users/kao/Projects/lado/.lado/worktrees/lad-95/task-lad-95`
  and the human taps the session's name
- **THEN** the sheet shows the whole path, wrapped, and Copy path copies it

#### Scenario: The state in the sheet
- **WHEN** a question waits in the session and the human taps the session's name
- **THEN** the sheet's state line starts with `needs you · 1 question`, then the run time

### Requirement: On a phone Rename in the session's details edits the title

In the phone layout Rename in the session's details SHALL edit the title in the sheet, with
the same field as in the head on a computer.

#### Scenario: Rename from the sheet
- **WHEN** the human taps Rename in the sheet, types "Phone layout" and confirms
- **THEN** the top bar shows "Phone layout"
