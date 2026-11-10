# session-card Specification

## Purpose
What the session list's rows say and how the session's card reads: labelled facts of a session on
hover or focus of its row or strip icon, beside the list and inside the window.

## Requirements

### Requirement: A row's line names no agents' count

A row of the session list SHALL say what waits for the human when something waits; else, in a live
session, `ran` and its run time, and in a stopped one its stopped text. Under a title the line SHALL
start with the session's name. No row SHALL show how many agents the session has.

#### Scenario: A running session
- **WHEN** a session of 5 agents has run for 10 days and 6 hours and nothing waits
- **THEN** its row's line reads `ran 10 d 6 h`, and the row's dot still says `working` or `idle`

#### Scenario: A session with a title
- **WHEN** the session `lad-189` with a title has run for 2 days and 2 hours
- **THEN** its row's line reads `lad-189 · ran 2 d 2 h`

#### Scenario: A session in trouble with nothing waiting
- **WHEN** a session's tmux session is gone and nothing waits in it
- **THEN** its row's line shows `ran` and its run time, and the row its status in words

#### Scenario: A session in trouble in which a gate waits
- **WHEN** a session's tmux session is gone and a gate waits in it
- **THEN** its row's line reads `1 gate`

### Requirement: A project's new title reaches the open session list

Setting or clearing a project's title SHALL send each of its sessions through the change feed, so an
open window shows the new title with no reload.

#### Scenario: A rename in a terminal
- **WHEN** a window is open and the human runs `lado project rename crm-3 "CRM"`
- **THEN** the feed sends the project's sessions with `project_title` `CRM`

### Requirement: A row of the session list shows no tooltip

A row of the session list SHALL show no tooltip on hover or keyboard focus: the row already
shows the whole title, wrapped when long, the session's name and what it is in. The session's
facts SHALL be in Details, opened by the title in the session's head.

#### Scenario: Hover
- **WHEN** the human hovers a row in a window 1440×900 and waits 500 ms
- **THEN** no tooltip shows, nothing covers the chat, and the pointer is the hand of a link

#### Scenario: Keyboard
- **WHEN** a row gets the focus from the keyboard
- **THEN** no tooltip shows

#### Scenario: A long title
- **WHEN** a session's title is longer than the row is wide
- **THEN** the row shows the whole title on more than one line, with no tooltip

### Requirement: A strip icon's tooltip is the session's name and state

The tooltip of a session strip's icon SHALL hold the title in bold, with the session's name
after it in `--muted` when the session has a title, then the state line, and nothing else. A
session in trouble in which something waits SHALL have `Needs you: <what waits>` on a line of
its own under its trouble, as its icon is the waiting one. The tooltip SHALL be as wide as its
text, at most the UI's tooltip width (320 px).

#### Scenario: A titled session that needs the human
- **WHEN** the human hovers the icon of the session `lad-264` titled `Session popup UI`, where a
  gate waits
- **THEN** the tooltip reads `Session popup UI lad-264`, then `Needs you: 1 gate`, and has no
  Project, Ran, Folder, Kits, CLI or Mode

#### Scenario: A session whose loop does not run
- **WHEN** the human hovers the icon of a session whose session loop does not run
- **THEN** the tooltip's state line reads its status in words with the `--danger` dot, and no
  line says how to go on

#### Scenario: Trouble while a gate waits
- **WHEN** a session's tmux session is gone and a gate waits in it
- **THEN** its icon's tooltip shows `tmux session is gone`, then `Needs you: 1 gate` on a line
  of its own

#### Scenario: Keyboard
- **WHEN** an icon gets the focus from the keyboard
- **THEN** the tooltip shows at once and Esc closes it

### Requirement: The strip icon's state line says the state with the icon's mark

The state line of a strip icon's tooltip SHALL be the mark and words of the session:
`<n> of <m> agents working` with the working dot in the group's colour; `idle` with the ring in
`--muted`; `Needs you: <what waits>` with the diamond in `--human`; a trouble's status with a
`--danger` dot. A stopped session has no icon in the strip, so no tooltip there.

#### Scenario: Idle
- **WHEN** the human hovers the icon of a running session where no agent works
- **THEN** the state line reads `idle` after the ring

#### Scenario: Agents at work
- **WHEN** the human hovers the icon of a session where 2 of its 3 agents work
- **THEN** the state line reads `2 of 3 agents working` after the working dot

### Requirement: The strip icon's tooltip opens beside the strip and stays in the window

The tooltip of a strip's icon SHALL open right of the icon, level with it, its arrow on its
left edge at the icon's middle, and SHALL stay inside the window. Where the window lacks room
on the right it SHALL open under or over the icon, on the side with more room when neither
fits.

#### Scenario: A wide window
- **WHEN** the human hovers an icon of the strip in a window 1440×900
- **THEN** the tooltip lies right of the strip

#### Scenario: A window of 640 px
- **WHEN** the human focuses a strip's icon in a window 640 px wide, where the list is folded
- **THEN** the tooltip opens right of the icon and inside the window

### Requirement: The strip icon's tooltip stays a tooltip

The tooltip of a strip's icon SHALL take no pointer events and SHALL close when the pointer
leaves the icon. The human copies the session's path in Details.

#### Scenario: The pointer leaves the icon
- **WHEN** the tooltip is open and the pointer moves off the icon towards it
- **THEN** the tooltip closes
