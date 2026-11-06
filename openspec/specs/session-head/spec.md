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
broken session's status in words, the run time, the branch, then at the right end the team,
the session's actions, a vertical line and the link, and no other fact or Copy button.

#### Scenario: Only the line's items
- **WHEN** a session of 4 kits in a git repository is open in a window 1440 px wide
- **THEN** the head shows no folder, remote, kit or CLI, and no Copy button

#### Scenario: A broken session
- **WHEN** the session's tmux session is gone
- **THEN** `tmux session is gone` shows after the title, before the run time

#### Scenario: Editing the title beside the team
- **WHEN** the human renames a session of 12 agents in a window 1024 px wide
- **THEN** the field stands in the title's place and the line stays one line 48 px high

### Requirement: What lacks room in the head's line is cut, never wrapped

What lacks room in the line SHALL be cut with "…": first the title down to 8ch of its text,
then the project, then the run time, then the team's box, by its levels, then the status words.
The actions and the link SHALL never be cut.

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
time, with the remote and the path in its tooltip, unless the team is past level 0; on a
narrower one it SHALL not.

#### Scenario: A wide window
- **WHEN** the window is 1600 px wide and the session's repository is on `main`
- **THEN** the head shows `main`; at 1599 px it does not

#### Scenario: A large team
- **WHEN** the window is 1920 px wide and the team is at level 1
- **THEN** the head shows neither the branch nor the run time

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
terminals, which lie over the chat, SHALL be put back. On a computer the head of a running session SHALL have five Tab stops, in order: the project, the
title, the team, Stop, the link; the status dot SHALL be no stop.

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
- **THEN** Tab goes to the project, the title, the team, Stop and the link, in this order

### Requirement: Above a phone the team stands in the head

Outside the phone layout the head SHALL show the session's team on every tab, after the facts
and 16 px before the actions, and the Activity tab SHALL have no team row. Agents SHALL keep
`teamGroups`' order, each run in its frame; a frame with no visible agent SHALL not show. With
no agents, or before they load, the head SHALL be as without a team and hold no room for it.
When the agents fail to load it SHALL show `team not loaded` in `--danger`, the cause in a
tooltip.

#### Scenario: On another tab
- **WHEN** a session of 4 agents is open on Artifacts in a window 1440 px wide and an agent
  starts to wait for the human
- **THEN** the head shows the four agents and the agent's waiting diamond

#### Scenario: The team fails to load
- **WHEN** the session's agents cannot be read
- **THEN** the head shows `team not loaded` with `role="alert"`, and its tooltip says why

#### Scenario: Clicking an agent
- **WHEN** the human clicks an agent in the head
- **THEN** that agent's terminal opens in the panel and its chip or avatar shows as pressed

### Requirement: The team gives way in four levels, one for all its agents

The team SHALL show the first level that fits: 0 the word `Team` and whole names; 1 shortened
names, every agent to one length from the longest down to 4, with no word, run time or branch,
and a list button `All N agents`; 2 avatars and that button; 3 the first avatars that fit and a
button with the rest. No level SHALL mix names and avatars. A status change SHALL not change the level.

#### Scenario: Four agents
- **WHEN** a session of 4 agents and a run, titled with 20 characters, is open in a window 1920, 1440
  or 1280 px wide
- **THEN** the team is at level 0

#### Scenario: Twelve agents
- **WHEN** a session of 12 agents and 3 runs, titled with 47 characters, is open in a window 1440,
  1280 or 1024 px wide
- **THEN** the team shows 12 avatars and `All 12 agents`; at 768 px it shows 8 avatars and `+4`,
  at 601 px 4 avatars and `+8`

#### Scenario: A status changes
- **WHEN** the team is at level 3 and a hidden agent starts to wait for the human
- **THEN** the button gets the diamond and the number of avatars stays

#### Scenario: Nothing left to show
- **WHEN** no avatar fits at level 3
- **THEN** the button shows the Agents icon and the number of agents, with no plus

#### Scenario: The level follows
- **WHEN** the window's width, the agents, the title or the fonts change
- **THEN** the level is chosen again before the paint

### Requirement: A team with names leaves the title its first 24 characters

Levels 0 and 1 SHALL fit only while the title shows its first 24 characters, or the whole title
when it is shorter; otherwise the next one SHALL be tried. Levels 2 and 3 SHALL have no such
limit, and the title SHALL give way there down to 8ch as elsewhere. While the title's field is
open the limit SHALL not count.

#### Scenario: Many agents on a wide window
- **WHEN** a session of 12 agents and 3 runs, titled with 47 characters, is open in a window 1920 px
  wide
- **THEN** the team is at level 1 with names of 4 letters (`deve…-2`) and the title shows at
  least its first 24 characters

#### Scenario: The title before the names
- **WHEN** a session of 4 agents and a run, titled with 20 characters, is open in a window 1024 px
  wide
- **THEN** the team is at level 1 with whole names and the title is whole; at 768 px it is at
  level 2 and the title is whole

#### Scenario: A short title
- **WHEN** a session of 12 agents and 3 runs, titled `lad-197 fix`, is open in a window 1920 px wide
- **THEN** the title is whole and the team is at level 1

#### Scenario: Avatars take no more room from the agents
- **WHEN** a session of 12 agents and 3 runs, titled with 47 characters, is open in a window 1024 px
  wide
- **THEN** all 12 avatars show, though the title shows fewer than 24 characters

### Requirement: A shortened name keeps what tells agents apart

At level 1 a name SHALL be its stem cut to the length, `…` and its tail, the tail being
`[-_.]<digits>` at its end; a stem within the length SHALL leave the name whole. Shortened names
alike SHALL take the last word after `-`, `_` or `.` as the tail; those still alike SHALL take
`·2`, `·3` after the later one. The accessible name and the tooltip SHALL have the whole name.

#### Scenario: A number
- **WHEN** `developer-2` is cut to 4
- **THEN** it shows `deve…-2`

#### Scenario: A clash
- **WHEN** `frontend-lead` and `frontend-dev` are cut to 4
- **THEN** they show `fron…-lead` and `fron…-dev`

### Requirement: An agent's mark is told from the whole team

An agent's mark SHALL be its first letter in capitals, then the number of its tail when that has
fewer than 3 digits; otherwise the number's last 3 digits. Marks alike SHALL take the first
letter at which the group's stems part, `-`, `_` and `.` left out, before the number. Those still
alike SHALL take a digit after the later one. Colour SHALL carry no difference.

#### Scenario: Numbers
- **WHEN** the team has `supervisor`, `developer-2` and `worker-1042`
- **THEN** their marks are `S`, `D2` and `042`

#### Scenario: One letter
- **WHEN** the team has `frontend-lead`, `frontend-dev`, `designer` and `developer`
- **THEN** their marks are `FL`, `FD`, `DS` and `DV`

### Requirement: An avatar's status reads on its own ground

An avatar in the head SHALL be 24×24 px, with its mark at 10.5 px, its avatar colour and the
status mark in its corner on a 1.5 px ring in `--panel`. The terminal shown SHALL have a ring of
3 px in `--action` with a gap in `--panel`, and the focus ring SHALL stand clear of it. Agents'
marks in the head and the team's list SHALL not pulse on any tab; the session's dot SHALL.

#### Scenario: The terminal shown has the focus
- **WHEN** the keyboard's focus is on the avatar of the terminal shown
- **THEN** the pressed ring and the focus ring both show, a band of the ground between them

#### Scenario: A busy agent
- **WHEN** an agent works and the session's dot pulses
- **THEN** the agent's mark in the head stands still

### Requirement: The team's list shows every agent by its whole name

From level 1 the team's button SHALL open a non-modal `role="dialog"` named `Team`, 320 px wide
and at most the window less 32 px, under the button at its right edge, scrolling inside, headed
`Team · N agents`. It SHALL list every agent in the team's order with its status mark, whole name
and status in words, each run under a dashed line in its colour with a link to its page.

#### Scenario: Opening a terminal from the list
- **WHEN** the human presses `+4` and then a hidden agent's row
- **THEN** the agent's terminal opens and the list closes; opened again, that row is marked
  `aria-current`

#### Scenario: Closing the list
- **WHEN** the list is open and the human presses Esc or the button again
- **THEN** the list closes and the focus is on the button

#### Scenario: Going away
- **WHEN** the list is open and the human clicks elsewhere or the focus leaves it
- **THEN** the list closes and the focus stays where it went

#### Scenario: What the button says
- **WHEN** a hidden agent waits for the human, or the terminal shown is among the hidden
- **THEN** the button shows the diamond, or the pressed frame, and is named `4 more agents, 1
  waits for you`

### Requirement: An agent's popup says who it is and what it does

An agent's tooltip, in the head and on the terminal strip, SHALL read: the whole name; the status
in words (`working`, `in the background`, `idle`, `waits for you`, `starting`, `stopped`) and how
long, in `--human` when it waits; `<role> · <provider>`, the role left out when it is the name;
`flow <run>` when it has one; `Click to open the terminal`.

#### Scenario: A waiting reviewer
- **WHEN** the human holds the pointer over `reviewer`, which works for run `task/x` and waits
- **THEN** the tooltip reads `reviewer`, `waits for you` with the time, the provider, `flow
  task/x` and `Click to open the terminal`

### Requirement: The team is one stop of the keyboard

Outside the phone layout the team SHALL be a `role="toolbar"` named `Team`, one Tab stop, in which
the arrows, Home and End move among its agents, run links and list button. An agent SHALL be named
`<name>, <role>, <status>`, the role left out when it is the name, by the popup's words. The
button SHALL be named `All N agents`, `<M> more agents` or, with no avatar, `<M> agents`, with `,
<K> waits for you` when hidden agents wait.

#### Scenario: Arrows
- **WHEN** the focus is on the team's first agent and the human presses the right arrow, then End
- **THEN** the focus moves to the next item, then to the team's last item, and one Tab leaves the
  team for Stop

#### Scenario: A name
- **WHEN** a screen reader reads `reviewer`, with role `reviewer`, while it waits
- **THEN** it says `reviewer, waits for you`
