# stopped-session Specification

## Purpose
What a stopped session's page shows: a bar with Resume in the composer's place, a feed text of its
own, the head's actions by tab, and terminals that fold and say the agent is not running, while the
human's stored choices stay as they were.

## Requirements

### Requirement: A stopped session's Activity has a bar in the composer's place

On Activity a stopped session SHALL show, in place of the composer, a bar with "This session is
stopped", the line "Its branches, runs and history are kept" and the primary button Resume session.
The bar's text SHALL have `role="status"`. It SHALL repeat no stop time. Above a phone it SHALL be
one row at least 52 px high.

#### Scenario: A stopped session with messages
- **WHEN** the human opens Activity of a stopped session with messages, at 1440, 768 or 390 px
- **THEN** the bar stands under the feed, no composer shows, and the feed's last entry is as before

#### Scenario: A session stops while it is open
- **WHEN** the session shown stops
- **THEN** the bar takes the composer's place without a reload

### Requirement: The bar fits a phone

On a phone held upright the bar's button SHALL stand under the text at full width and 44 px high.
On a phone held sideways the bar SHALL stay one row with a button 44 px high.

#### Scenario: Upright
- **WHEN** the window is 390 px wide
- **THEN** both lines of text stay whole and the button spans the bar

#### Scenario: Sideways
- **WHEN** the window is 844 by 390 px on a touch screen
- **THEN** the text and the button stand in one row

### Requirement: Resume session is the head's Resume

Resume session SHALL open the Resume window, as Resume in the head does, and send no request of its
own. While the connection is lost it SHALL be disabled and say "Waiting for connection" in a tooltip.
What the composer held when the session stopped SHALL be there after the resume.

#### Scenario: Resume
- **WHEN** the human presses Resume session and confirms the window, and the session runs
- **THEN** the composer stands in the bar's place

#### Scenario: A draft
- **WHEN** the composer holds text, the session stops and is resumed
- **THEN** the composer holds the same text

#### Scenario: No connection
- **WHEN** the connection is lost
- **THEN** Resume session is disabled and its tooltip reads "Waiting for connection"

### Requirement: A stopped session's empty feed says what it shows

A stopped session's empty feed SHALL say "Nothing was said in this session." while it shows the
messages between agents, and "No messages with you. Messages between agents are hidden." while it
does not, centred in `--muted`. A running session's empty feed SHALL not change.

#### Scenario: All
- **WHEN** a stopped session's feed shows all messages and is empty
- **THEN** it says "Nothing was said in this session."

#### Scenario: Yours
- **WHEN** a stopped session's feed shows only the human's conversation and is empty
- **THEN** it says "No messages with you. Messages between agents are hidden."

#### Scenario: A running session
- **WHEN** a running session's feed is empty
- **THEN** it says "No messages yet. Write to the supervisor below."

### Requirement: A stopped session's head has Resume only where no bar stands

On Activity the head of a stopped session SHALL show Forget alone. On every other tab it SHALL show a
secondary Resume with its icon and the word `Resume` at 14 px before Forget, at any window width.
What lacks room SHALL be the title, not the button. A session whose tmux session is gone SHALL keep
its actions.

#### Scenario: Activity
- **WHEN** the human opens Activity of a stopped session
- **THEN** the head has the button `Forget…` and no `Resume…`

#### Scenario: Other tabs
- **WHEN** the human opens Agents, Flows or Artifacts of a stopped session, at 1440, 768 or 390 px
- **THEN** `Resume…` with its word stands before `Forget…`

#### Scenario: A long title on a phone
- **WHEN** the window is 320 px wide and the title is long
- **THEN** the title is cut, Resume keeps its word and the page has no sideways scroll

#### Scenario: No connection
- **WHEN** the connection is lost on Flows
- **THEN** Resume is disabled and Forget is not

### Requirement: A stopped session shows no team

A stopped session SHALL show no team in the head. On a phone its Activity SHALL show neither the
word Team nor chips. Held upright, the toggle "Messages between agents" SHALL stay, with its words,
44 px high and its pressed state; held sideways, it SHALL be the icon button at the end of the tab
row.

#### Scenario: Above a phone
- **WHEN** the human opens a stopped session at 1440 px
- **THEN** the head has no group named Team

#### Scenario: A phone
- **WHEN** the human opens Activity of a stopped session at 390 px
- **THEN** no word Team shows and the toggle reads "Messages between agents"

#### Scenario: An empty feed sideways
- **WHEN** a stopped session's feed says "No messages with you. Messages between agents are hidden."
  on a touch screen of 844×390 and the human taps the icon button
- **THEN** the button is pressed and the feed shows what All shows

### Requirement: A stopped session's terminals start folded and store nothing

A stopped session's terminals SHALL be folded whatever is stored. What the human does to them there
SHALL last while the session is shown and SHALL write nothing to `lado.terminals` or the column
opened last, but a width set on the edge. When the session runs, or another session shows, the
stored choice SHALL show.

#### Scenario: Stored open
- **WHEN** `lado.terminals` says open and the human opens a stopped session at 1440 px
- **THEN** the terminals are in their strip and `lado.terminals` is as it was

#### Scenario: Opened by hand
- **WHEN** the human opens the terminals of a stopped session and reloads
- **THEN** they are in their strip, and storage is as it was

#### Scenario: Resume
- **WHEN** `lado.terminals` says open and the stopped session is resumed
- **THEN** the terminals are open

#### Scenario: Stored folded
- **WHEN** `lado.terminals` says folded, the human opens the terminals of a stopped session, then
  resumes it
- **THEN** the terminals are folded

### Requirement: A stopped session's terminal says the agent is not running

An opened terminal of a stopped session SHALL say "Agent not running — resume the session to start
it" in mono 13 on `--term-ground`, and SHALL have no Reconnect, no Take control and no socket. After
the resume it SHALL open by itself. A running session's terminal closed for good SHALL keep
Reconnect.

#### Scenario: Opened
- **WHEN** the human opens the supervisor's terminal of a stopped session
- **THEN** it shows the text, and no socket is opened

#### Scenario: Resume with the panel open
- **WHEN** the session is resumed with its terminals open
- **THEN** the supervisor's terminal connects without a press

#### Scenario: A running session
- **WHEN** a running session's terminal closes for good
- **THEN** it shows `closed: <reason>` and Reconnect
