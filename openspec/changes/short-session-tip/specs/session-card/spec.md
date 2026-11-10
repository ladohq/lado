## ADDED Requirements

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

#### Scenario: A stopped session
- **WHEN** the human hovers the icon of a session stopped 5 hours ago
- **THEN** the tooltip's state line reads `stopped 5 h ago`, and no line says how to go on

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
`--danger` dot; `stopped <time> ago` in `--muted`, or `stopped` when the session has no stop
time.

#### Scenario: Stopped
- **WHEN** the human hovers the icon of a session stopped 5 hours ago
- **THEN** the state line reads `stopped 5 h ago` with no dot

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

## REMOVED Requirements

### Requirement: The session's card shows labelled facts

**Reason**: The card covered the chat, flashed while the pointer crossed the list, and repeated
Details (LAD-264, the human's approval of the UX review).
**Migration**: "A row of the session list shows no tooltip" and "A strip icon's tooltip is the
session's name and state" replace it; the facts are in Details.

### Requirement: The card's state line says the state with the row's mark

**Reason**: The row has no card any more (LAD-264).
**Migration**: "The strip icon's state line says the state with the icon's mark" replaces it.

### Requirement: The card says how to go on from a stopped or broken session

**Reason**: Opening a session is one click, and its page has Resume (LAD-264).
**Migration**: None; the session's page shows Resume.

### Requirement: The card names the session's project by its title

**Reason**: The tooltip shows no project (LAD-264); the session's head shows the project as a
breadcrumb (session-head), and `SessionInfo.project_title` stays as what makes the head ask its
about again.
**Migration**: "A project's new title reaches the open session list" keeps the feed's part.

### Requirement: The card opens beside the list and stays in the window

**Reason**: The row has no card any more (LAD-264).
**Migration**: "The strip icon's tooltip opens beside the strip and stays in the window"
replaces it for the strip's icon.

### Requirement: The card keeps one width and a bounded height

**Reason**: The short tooltip is as wide as its text, as the UI's other tooltips (LAD-264).
**Migration**: "A strip icon's tooltip is the session's name and state" bounds its width.

### Requirement: The card stays a tooltip

**Reason**: The row has no card any more (LAD-264).
**Migration**: "The strip icon's tooltip stays a tooltip" replaces it.
