## MODIFIED Requirements

### Requirement: The window opens on the last place

The New session window SHALL open with Where on the first recent place and the focus in
Task; with no recent places, on New empty folder with the focus in Folder name; opened from a
project's page, on that project (and repository). It SHALL show no message above Where. When the
recent places come after the human moved the focus within the window, the window SHALL set Where
and leave the focus where the human put it.

#### Scenario: Back where the human worked
- **WHEN** the latest started session ran in `~/workspace/webapp`, and the human opens New
  session
- **THEN** Where shows `webapp`, the folder is checked, the focus is in Task, and the start
  button names the place

#### Scenario: The first session ever
- **WHEN** LADO has no sessions and the human opens New session
- **THEN** Where shows New empty folder and no message stands above it

#### Scenario: The recent places come late
- **WHEN** the human opens New session and moves the focus to Cancel before the recent places
  come
- **THEN** Where shows the last place once they come, the focus stays on Cancel, and Enter
  closes the window

### Requirement: The window keeps its draft until a start

Closing the New session window without a start SHALL keep Where's choice, Task and the Team
fields, the model picked too (for the agent CLI it was picked for), for its next opening in
the page; a start SHALL clear them, and a reload of the page loses them. A Where nobody chose
before the close SHALL NOT be kept as a choice.

#### Scenario: Esc with a task typed
- **WHEN** the human types a task, presses Esc and opens New session again
- **THEN** Task holds the text and Where the same place

#### Scenario: A place chosen before the recent places came
- **WHEN** the recent places answer late, the human picks New empty folder, presses Esc before
  the answer, and opens New session again
- **THEN** Where shows New empty folder, not the last place

### Requirement: Permissions are named in words

Permissions SHALL list the agent's modes as radio rows titled by the provider's words for
each, the description shown under the chosen row and always under a risky one; a mode with
no words SHALL be listed by its CLI value; a mode the provider takes only as another name of
one of its modes SHALL NOT be listed; an agent with no modes SHALL show `No permission
modes.` and Team no Permissions.

#### Scenario: Claude Code's risky mode
- **WHEN** Team is open for Claude Code
- **THEN** the row `Full access, never ask ⚠` shows its description even when not chosen,
  and `Ask before changes (recommended)` is chosen by default

#### Scenario: A mode with no words
- **WHEN** a provider lists a mode `manual` with no words
- **THEN** the row reads `manual` and has no description

#### Scenario: Claude Code's auto mode
- **WHEN** Team is open for Claude Code and the human chooses `Let Claude judge the risk`
- **THEN** the row shows `Checks each action for risk, runs what it judges safe and stops the
  rest. Needs a plan and model with Claude Code's auto mode.`, Team reads `Permissions Claude
  judges the risk`, and no row reads `auto` or `manual`

## ADDED Requirements

### Requirement: A draft without a chosen place opens on the last place

A New session window opened with a draft whose place nobody chose (it was closed before the
recent places came) SHALL set Where on the last place when the recent places come, as a window
without a draft does, and keep the draft's Task and Team.

#### Scenario: Closed before the recent places came
- **WHEN** the recent places answer after 3 s, the human opens New session, types a task,
  presses Esc before the answer, and opens New session again
- **THEN** Where shows the last place once the recent places come, Task holds the text, and
  every later opening shows the last place too
