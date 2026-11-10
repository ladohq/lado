## ADDED Requirements

### Requirement: A stopped session of the place leaves the new session the free name

When the place has a stopped session of its default name, the New session window SHALL name the
new session by the free name, say `Session <name> stopped here <when>` under Where, and show one
start button, `Start new session <free name>`, the primary; it SHALL NOT offer to resume the
stopped session, which the human resumes from its page or the session list.

#### Scenario: Back to a stopped session
- **WHEN** `~/workspace/webapp` has the stopped session `webapp` and the window opens on it
- **THEN** Team reads `Name webapp-2`, the line under Where says `Session webapp stopped here`,
  and the footer shows Cancel and `Start new session webapp-2` as the primary, no `Resume webapp`

#### Scenario: A new task
- **WHEN** the human types a task and presses `Start new session webapp-2`
- **THEN** the window starts `webapp-2` with the task, and `webapp` stays stopped

#### Scenario: The last launch was on another CLI's model
- **WHEN** the Claude Code session `nologin` on `CloudClaude` is stopped in a folder whose last
  launch is a Codex session on `CloudCodex`, neither CLI logged in, and the window opens there
- **THEN** it offers no Resume, and the Resume window of `nologin` (from its page) resumes it on
  Claude Code and `CloudClaude`

## MODIFIED Requirements

### Requirement: The footer says what is missing

While the start button is off, the footer SHALL show `To start: ` and the missing items as
links that focus their fields (opening Team when needed): choose a place, wait for the check,
name the folder, wait for the agent CLIs, choose an agent (also when their list failed),
choose a team setup, choose a smaller folder, choose another folder, tell git who you are,
wait for the count, fix the model, shorten the task, log in to `<CLI>`.

#### Scenario: The agent CLIs not known yet
- **WHEN** the folder will do and `/api/providers` has not answered
- **THEN** the start button is off and the footer reads `To start: wait for the agent CLIs`

#### Scenario: Enter beside a stopped session
- **WHEN** the place has a stopped session, Task is empty and the human presses Enter in a
  field of the window
- **THEN** the window starts the new session under the free name, as its button `Start new
  session <free name>` would; the stopped session stays stopped

#### Scenario: No agent chosen
- **WHEN** two CLIs are installed and none is suggested
- **THEN** Team shows Agent `choose…` in its summary and the footer reads `To start: choose
  an agent`; the link puts the focus on Agent

## REMOVED Requirements

### Requirement: A stopped session of the place offers Resume beside a new start

**Reason**: The window's one Team was filled for the new session, and `Resume <name>` sent its
model to the stopped session (LAD-261); the human chose that New session is for a new session
only (answer #5411).
**Migration**: Resume a stopped session from its page or the session list (the Resume window, on
the session's own team), or with `lado resume`; "A stopped session of the place leaves the new
session the free name" keeps the free name and the line under Where.
