# session-head Specification

## Purpose
How a session's head reads on a computer: one line of the top bar that never wraps, with the
project, the title, the run time, the team in its levels, Stop and the link, and the session's
facts in a popover Details opened from the title, with the same content as the phone's sheet.

## Requirements

### Requirement: Above 600 px the session's head is one line of 48 px

Outside the phone layout, on a window wider than 600 px, the session's head SHALL be one
line `--head-h` (48 px) high that SHALL not wrap, while the title is edited too. It SHALL
hold, left to right: the status dot, the project and a `/`, the title with a chevron, a
broken session's status in words, the run time, the branch, then at the right end the
session's actions, a vertical line and the link, and no other fact or Copy button.

#### Scenario: Only the line's items
- **WHEN** a session of 4 kits in a git repository is open in a window 1440 px wide
- **THEN** the head shows no folder, remote, kit or CLI, and no Copy button

#### Scenario: A broken session
- **WHEN** the session's tmux session is gone
- **THEN** `tmux session is gone` shows after the title, before the run time

### Requirement: What lacks room in the head's line is cut, never wrapped

What lacks room in the line SHALL be cut with "…": first the title down to 8ch of its text,
then the project, then the run time, then the status words. The actions and the link SHALL
never be cut.

#### Scenario: A broken session on the narrowest line
- **WHEN** a session in `session loop not running` with a long title in a project with a long
  title is open in a window 601 px wide
- **THEN** the words are whole and the run time gave its room first

#### Scenario: Long names on a narrow window
- **WHEN** a session of 4 kits with a long title in a project with a long title is open in a
  window 768 px wide
- **THEN** the head is one line 48 px high, the project is at most 16ch wide with "…", and
  the title has the rest of the room

### Requirement: The branch shows in the head on a wide window only

On a window of 1600 px or more the head SHALL show the repository's branch after the run
time, with the remote and the path in its tooltip; on a narrower one it SHALL not.

#### Scenario: A wide window
- **WHEN** the window is 1600 px wide and the session's repository is on `main`
- **THEN** the head shows `main`; at 1599 px it does not

### Requirement: The head shows a session's project as a breadcrumb

For a session whose about has a project, the head SHALL show the project's title (its id
without one) in `--muted` at 14 px, at most 16ch wide, then a `/` that is hidden from
assistive technology. It SHALL be a link to the project's page, in `--ink` and underlined on
hover and focus, and its tooltip SHALL have the whole title and `Project <id>`. A session
without a project SHALL have neither.

#### Scenario: No project
- **WHEN** the human opens a session in no project
- **THEN** the head starts with the dot and the title, with no `/`

### Requirement: The head's title is a button that opens Details

The title (or the name) SHALL be a button inside the page's `h1`, with
`aria-haspopup="dialog"` and `aria-expanded`, cut with "…", followed by a chevron, on a
`--raised` ground on hover and while Details is open. A click, Enter or Space SHALL open
Details. A double click SHALL not open the title's field.

#### Scenario: Keyboard
- **WHEN** the focus is on the title and the human presses Space
- **THEN** Details opens and the title's `aria-expanded` is `true`

### Requirement: Stop and the link keep or lose their words by the window's width

Stop SHALL be 32 px high and named `Stop session…`, with its icon, and with the word `Stop`
on a window wider than 900 px. The link SHALL show its dot, and the word `live` on a window
wider than 1100 px; on a narrower one its tooltip SHALL read `live · LADO server`, unless it
says an update is available.

#### Scenario: Tablet width
- **WHEN** the window is 768 px wide and the feed is live
- **THEN** Stop shows only its icon, and the link only its dot with the tooltip
  `live · LADO server`

### Requirement: Details shows the session's facts in a popover

Details SHALL be a non-modal `role="dialog"` named `Session details`, under the title's
button, 470 px wide and at most the window less 32 px, as high as the window allows and
scrolling inside beyond that, with no focus trap. Opening it SHALL put the focus on Copy path. Its content SHALL come from the same component as the phone's
sheet. Until the about comes, or when it fails, it SHALL show the session's settings alone.

#### Scenario: A narrow window
- **WHEN** the window is 601 px wide and the human opens Details
- **THEN** it is 470 px wide and lies inside the window

### Requirement: Details names every fact of the session

Details SHALL hold: the whole title; the state line, `id <name>` and, in a project, `project`
with a link to its page; Folder, the whole path wrapped anywhere, with Copy path; Git, the
short remote and branch, with Copy URL when there is a remote; Kits, each with its version;
CLI with its version and `permissions: <mode>` when the session has a mode; then Rename, Copy
link and All sessions. Each kit's and the CLI's tooltip and the mark of an untested version
SHALL stay.

#### Scenario: The facts
- **WHEN** the human opens Details of a session in the project `LADO`
- **THEN** it shows the session's id, a link `LADO`, the whole folder, the remote and branch,
  each kit with its version and the CLI with its version and permission mode, and the focus
  is on Copy path

#### Scenario: A kit that does not load
- **WHEN** a kit of the session does not load and the human hovers its name in Details
- **THEN** the tooltip says why

### Requirement: Details' state line says the state once

The state line SHALL be the mark's words without `running`, then the run time. A stopped
session's line SHALL say `stopped` once, in its time.

#### Scenario: A running session
- **WHEN** the human opens Details of an idle session of 2 agents
- **THEN** the state line starts with `idle · 2 agents`, then the run time

#### Scenario: A stopped session
- **WHEN** the human opens Details of a session stopped 2 days ago after 4 hours
- **THEN** the state line starts with `stopped 2 d ago · ran 4 h`

### Requirement: Details takes Esc first and goes with the focus

Esc SHALL close only Details: an expanded waiting card or expanded terminals under it SHALL
stay. When the focus leaves Details and the title, Details SHALL close and the focus SHALL stay
where it went.

#### Scenario: Tab past its last control
- **WHEN** the focus is on All sessions and the human presses Tab
- **THEN** Details closes and the focus is on what follows it, not on the title

#### Scenario: Esc over the expanded terminals
- **WHEN** Details is open over the expanded terminals and the human presses Esc
- **THEN** Details closes and the terminals stay expanded

### Requirement: Details closes and gives the focus back

Esc, a click outside Details and a second click on the title SHALL close it. After Esc or a
second click the focus SHALL be on the title. After a click outside, the focus SHALL stay on
what was clicked when that is a field, a button, a link or another element that takes the
focus by a click, the terminal's input among them, and otherwise SHALL be on the title.

#### Scenario: A click on an empty place
- **WHEN** Details is open and the human clicks an empty place of the page
- **THEN** it closes and the focus is on the title

#### Scenario: A click in the terminal
- **WHEN** Details is open and the human clicks in a terminal
- **THEN** it closes and the focus is in the terminal's input

#### Scenario: A click in the composer
- **WHEN** Details is open and the human clicks in the composer
- **THEN** it closes and what the human types goes to the composer

### Requirement: Rename in Details edits the title in the head

Rename in Details SHALL close it and turn the title in the head into the title's field; the
field's hint SHALL show under the line without making it higher. When the field closes the
focus SHALL be on the title.

#### Scenario: Rename
- **WHEN** the human opens Details, presses Rename, types `Review` and presses Enter
- **THEN** the title is saved, the head shows `Review`, the line stayed 48 px high, and the
  focus is on the title

### Requirement: The keyboard reaches the chat in a few stops

A session's page SHALL start with a link `Skip to chat`, hidden until it has the focus, that
SHALL put the focus on the Activity tab's feed, opening that tab when another is open, or on
the selected tab of the waiting card when the card is expanded and hides the feed; expanded
terminals, which lie over the chat, SHALL be put back. On a computer the head of a running session SHALL have four Tab stops, in order: the project, the
title, Stop, the link; the status dot SHALL be no stop.

#### Scenario: From another tab
- **WHEN** the Flows tab is open and the human presses Tab once and then Enter
- **THEN** the Activity tab opens with the focus on the chat's feed

#### Scenario: With the waiting card expanded
- **WHEN** the waiting card is expanded and the human presses Enter on `Skip to chat`
- **THEN** the focus is on the card's selected tab

#### Scenario: With the terminals expanded
- **WHEN** the terminals are expanded and the human presses Enter on `Skip to chat`
- **THEN** the terminals go back to their place and the focus is on the chat's feed

#### Scenario: Through the head
- **WHEN** the focus is before the head of a running session in a project
- **THEN** Tab goes to the project, the title, Stop and the link, in this order
