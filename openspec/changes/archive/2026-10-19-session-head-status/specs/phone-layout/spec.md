## MODIFIED Requirements

### Requirement: On a phone the session's details open from its name

In the phone layout a tap on the session's name in the top bar SHALL open a sheet over the
page's bottom, named by the session, with: the mark's words and the run time; the whole
folder (wrapped, never cut) with Copy path; git (the remote, the branch) as the head shows
it on a computer; the kits, each with its version; the CLI with its version and
permission mode; and the buttons Rename, Copy link and All sessions. A tap outside the
sheet, Esc or its close button SHALL close it.

#### Scenario: The whole folder
- **WHEN** the session's folder is `/Users/kao/Projects/lado/.lado/worktrees/lad-95/task-lad-95`
  and the human taps the session's name
- **THEN** the sheet shows the whole path, wrapped, and Copy path copies it

#### Scenario: The state in the sheet
- **WHEN** a question waits in the session and the human taps the session's name
- **THEN** the sheet's state line starts with `needs you · 1 question`, then the run time
