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

### Requirement: The session's card shows labelled facts

The card of a row and of a strip's icon SHALL hold, in order: the title, with the name after it when
the session has a title; the state line; a line; then the labels Project, Ran, Folder, Kits, CLI and
Mode, each with its value. A row without a value SHALL not be drawn. Ran SHALL be the run time with
no word before it, and Folder the whole path.

#### Scenario: A session outside a project
- **WHEN** the human hovers a session in no project and with no permission mode
- **THEN** the card has neither Project nor Mode, with no empty label

#### Scenario: Keyboard
- **WHEN** a row gets the focus from the keyboard
- **THEN** the card shows at once and Esc closes it

### Requirement: The card's state line says the state with the row's mark

The state line SHALL be the mark and words of the session: `<n> of <m> agents working` with the
working dot in the group's colour; `idle` with the ring in `--muted`; `Needs you: <what waits>` with
the diamond in `--human`; a trouble's status with a `--danger` dot; `stopped <time> ago` in `--muted`,
or `stopped` when the session has no stop time.

#### Scenario: Stopped
- **WHEN** the human hovers a session stopped 5 hours ago after 3 hours 2 minutes
- **THEN** the state line reads `stopped 5 h ago` and Ran reads `3 h 2 min`

#### Scenario: Trouble while a gate waits
- **WHEN** a session's tmux session is gone and a gate waits in it
- **THEN** the card shows `tmux session is gone`, then `Needs you: 1 gate` on a line of its own

### Requirement: The card says how to go on from a stopped or broken session

The card's last line SHALL say what to do: `Open it and press Resume` for a stopped session and for
one whose tmux session is gone, `Open it and press Stop session, then Resume` for one whose session
loop does not run. A running session's card SHALL have no such line.

#### Scenario: The loop is down
- **WHEN** the human hovers a session whose loop does not run
- **THEN** the card ends with `Open it and press Stop session, then Resume`

### Requirement: The card names the session's project by its title

Project SHALL show the project's title, and its id where it has no title. `SessionInfo` SHALL carry
`project_title`, null for a session in no project and for a project without a title.

#### Scenario: A project with a title
- **WHEN** the session is in the project `crm-3` titled `CRM 3`
- **THEN** the card's Project reads `CRM 3`

#### Scenario: A project without a title
- **WHEN** the session is in the project `shop-api`, which has no title
- **THEN** the card's Project reads `shop-api`

### Requirement: A project's new title reaches the open session list

Setting or clearing a project's title SHALL send each of its sessions through the change feed, so an
open window shows the new title with no reload.

#### Scenario: A rename in a terminal
- **WHEN** a window is open and the human runs `lado project rename crm-3 "CRM"`
- **THEN** the feed sends the project's sessions with `project_title` `CRM`

### Requirement: The card opens beside the list and stays in the window

The session's card SHALL open right of its row or icon, level with it, its arrow on its left edge at
the trigger's middle, and SHALL stay inside the window. Where the window lacks room on the right it
SHALL open under or over the trigger, on the side with more room when neither fits.

#### Scenario: A wide window
- **WHEN** the human hovers a row in a window 1440×900
- **THEN** the card lies right of the list and covers no row of it

#### Scenario: The last row
- **WHEN** the human hovers the lowest row in the window
- **THEN** the whole card is inside the window, moved up past the row's level

#### Scenario: A row as wide as the window
- **WHEN** the human focuses a row in a window 590 px wide, where the list is the page
- **THEN** the card opens under or over the row and inside the window

#### Scenario: A window of 640 px
- **WHEN** the human focuses a strip's icon in a window 640 px wide, where the list is folded
- **THEN** the card opens right of the icon and inside the window

### Requirement: The card keeps one width and a bounded height

The card SHALL be 360 px wide, or the window less 16 px when that is less, whatever its content, and
at most the window less 16 px high. Kits SHALL show at most 6 names, then `+<n> more`.

#### Scenario: A short card
- **WHEN** the pointer moves from a session of many facts to one of few
- **THEN** both cards are 360 px wide

#### Scenario: Many kits
- **WHEN** a session has 9 kits
- **THEN** Kits shows 6 names and `+3 more`, and CLI stays in the card

### Requirement: The card stays a tooltip

The card SHALL take no pointer events and SHALL close when the pointer leaves its row or icon. The
human copies the session's path in Details.

#### Scenario: The pointer leaves the row
- **WHEN** the card is open and the pointer moves off the row towards the card
- **THEN** the card closes
