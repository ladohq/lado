## ADDED Requirements

### Requirement: The UI picks the phone layout by the screen and the pointer

The web UI SHALL use its phone layout exactly while the primary pointer is coarse (a touch
screen) and the window is no wider than 600 px or no higher than 500 px; the layout SHALL
follow the window when it turns or resizes, without a reload. With a fine pointer (a
mouse or a trackpad) the UI SHALL never use the phone layout, whatever the window's size,
and SHALL look and behave as before this change. There SHALL be no setting or switch for
it.

#### Scenario: A phone held upright
- **WHEN** the UI is opened on a touch screen 390 px wide and 844 px high
- **THEN** it shows the phone layout

#### Scenario: A phone held sideways
- **WHEN** the same phone turns to 844 px wide and 390 px high
- **THEN** the UI keeps the phone layout, in its sideways form, without a reload

#### Scenario: A computer's narrow window
- **WHEN** the UI is opened with a mouse in a window 390 px wide and 844 px high
- **THEN** it shows the rail, the session's head with its facts, the session strip and
  the terminal strip as before this change, and no Menu button

#### Scenario: A tablet
- **WHEN** the UI is opened on a touch screen 820 px wide and 1180 px high
- **THEN** it does not show the phone layout

### Requirement: On a phone the rail opens as a menu

In the phone layout the rail SHALL not be shown. The top bar SHALL start with a Menu
button (three lines, accessible name "Menu", or "Menu, N waiting" while N things wait for
the human) that shows the Needs you count as a badge while it is not zero. Menu SHALL open
the rail over the page from the left, with each section's icon and name, the Needs you
count, Launch, Report a bug and Settings, and dim the rest of the page. Choosing an item,
a tap on the dimmed page, or Esc SHALL close it; on closing the focus SHALL go back to
Menu.

#### Scenario: Two things wait
- **WHEN** a gate and a question wait and the human looks at the top bar on a phone
- **THEN** Menu shows the badge 2 and is named "Menu, 2 waiting"

#### Scenario: Going to Kits
- **WHEN** the human taps Menu, then Kits
- **THEN** the Kits page opens and the menu is closed

#### Scenario: A tap beside the menu
- **WHEN** the menu is open and the human taps the dimmed page
- **THEN** the menu closes and the page under it is as it was

### Requirement: On a phone the top bar is one line

In the phone layout the top bar SHALL be one line no higher than 52 px upright and 44 px
sideways, and SHALL not wrap. On a session's page it SHALL hold, left to right: Menu, the
session's status dot, the session's title (or name) as a button that opens the session's
details, cut with "…" when long, the change feed's mark and Stop session. On another page
it SHALL hold Menu and the page's title. The change feed's mark SHALL be a dot while the
feed is live and the word "reconnecting…" while it is not, and SHALL open the system panel
as before; a newer LADO's `↑ X.Y.Z` SHALL stay beside it.

#### Scenario: A session's page upright
- **WHEN** the human opens session lad-95 on a phone 390 px wide
- **THEN** the top bar is one line holding Menu, the status dot, "lad-95", the live dot and
  Stop, and no folder, git, kit or CLI fact

#### Scenario: A long title
- **WHEN** the session's title is longer than the room left
- **THEN** it is cut with "…" and the line does not wrap

#### Scenario: The feed is lost
- **WHEN** the change feed reconnects
- **THEN** the mark reads "reconnecting…" in place of the dot

### Requirement: On a phone the session's details open from its name

In the phone layout a tap on the session's name in the top bar SHALL open a sheet over the
page's bottom, named by the session, with: the status and the run time; the whole folder
(wrapped, never cut) with Copy path; git (the remote, the branch) as the head shows it on a
computer; the kits, each with its version; the CLI with its version and permission mode;
and the buttons Rename, Copy link and All sessions. Rename SHALL edit the title as the
pencil does on a computer. A tap outside the sheet, Esc or its close button SHALL close it.

#### Scenario: The whole folder
- **WHEN** the session's folder is `/Users/kao/Projects/lado/.lado/worktrees/lad-95/task-lad-95`
  and the human taps the session's name
- **THEN** the sheet shows the whole path, wrapped, and Copy path copies it

#### Scenario: Rename from the sheet
- **WHEN** the human taps Rename in the sheet, types "Phone layout" and confirms
- **THEN** the top bar shows "Phone layout"

### Requirement: On a phone the Sessions page is the session list

In the phone layout the session strip SHALL not be shown. The Sessions page SHALL show the
session list (its search, "+" and groups) across the content's width, and a session's page
SHALL show only that session. Opening a session from the list SHALL not change the list's
collapsed state remembered for a computer.

#### Scenario: Choosing a session
- **WHEN** the human opens Sessions on a phone and taps lad-95's row
- **THEN** lad-95's page opens with no session strip

### Requirement: On a phone a session's tabs fit the screen

In the phone layout a session's tabs SHALL show without their icons, each with its name
and count, and all four (Activity, Agents, Flows, Artifacts) SHALL be within a screen
360 px wide.

#### Scenario: The narrowest phone
- **WHEN** a session with 12 agents, 3 runs and 40 artifacts is opened on a phone 360 px
  wide
- **THEN** Activity, Agents 12, Flows 3 and Artifacts 40 are all within the screen

### Requirement: On a phone the composer stays at hand

In the phone layout the window SHALL not scroll as a page; each page's content SHALL
scroll by itself under the top bar, as on a computer's wide window. In a session's chat
the feed SHALL scroll by itself, and the waiting card and the composer SHALL stay at the
chat's bottom; the card SHALL be at most half the chat's height, its list scrolling
inside. The composer's text SHALL be at least 16 px, and its keys hint ("Enter to send ·
Shift+Enter …") SHALL not be shown on a touch screen. When the on-screen keyboard opens,
the composer SHALL stay above it.

#### Scenario: Writing with a gate waiting
- **WHEN** a gate waits and the human opens the session's chat on a phone 390×844
- **THEN** the composer is at the screen's bottom without scrolling, the card above it is
  at most half the chat's height, and the feed above scrolls by itself

#### Scenario: No keys hint
- **WHEN** the chat is shown on a touch screen
- **THEN** the composer shows "to supervisor" and no keys hint

### Requirement: On a phone a flow event's line wraps

In the phone layout a flow run's event in the chat SHALL start at the feed's left edge,
with its actor, chips and time on its first line, and its text SHALL wrap under them,
whole, never cut with "…".

#### Scenario: A long event
- **WHEN** run ship/x starts with the text "flow ship from kit uiflow 1.0.0: Add a login
  page" on a phone 390 px wide
- **THEN** the whole text shows under the actor's line, wrapped

### Requirement: On a phone held sideways the waiting card starts minimized

In the phone layout no higher than 500 px the waiting card in a session's chat SHALL show
minimized (its tabs and one line), and a tap on a tab or its line SHALL show the card
expanded over the chat's area; Esc or the card's fold button SHALL minimize it again. The
Team row and the composer's "to" line SHALL not be shown. This SHALL not change the
minimized state the card remembers for the session.

#### Scenario: Answering a gate sideways
- **WHEN** gate #1 of ship/x waits and the human opens the chat on a phone 844×390
- **THEN** the card is minimized above the composer; a tap on its tab ship/x shows the
  gate over the chat with Approve and Reject

#### Scenario: Turning back upright
- **WHEN** the human turns the phone upright with the card minimized only because it was
  sideways
- **THEN** the card shows whole, at most half the chat's height

### Requirement: On a phone a terminal fills the screen

In the phone layout the terminal panel and its strip SHALL not be shown. A team chip or
Open terminal SHALL show the agent's terminal over the whole screen, with its tabs and bar
as when expanded on a computer, and a button Close terminal in place of Restore terminal;
Close terminal or Esc (except in a terminal the human controls) SHALL go back to the page.

#### Scenario: The supervisor's terminal
- **WHEN** the human taps the team chip "supervisor" on a phone
- **THEN** the supervisor's terminal fills the screen, and Close terminal goes back to the
  chat

### Requirement: On a touch screen a hint's tooltip shows on a tap

On a touch screen a tap on a trigger of the UI's tooltip that is not a button or link (a
kit's name, the CLI, a hint with a dotted underline) SHALL show its tooltip, and a tap
anywhere else SHALL hide it. A button's or link's tooltip, which only names it, SHALL not
show on a tap.

#### Scenario: A kit's version
- **WHEN** the human taps the kit "uiflow" in the session's details on a phone
- **THEN** the tooltip "uiflow v1.0.0 …" shows; a tap elsewhere hides it

#### Scenario: A button
- **WHEN** the human taps Copy link in the session's details
- **THEN** the link is copied and no tooltip shows

### Requirement: On a phone the Kits tabs fit the screen

In the phone layout the Kits page's tabs (Installed, Available, Updates, each with its
count) SHALL all be within a screen 360 px wide.

#### Scenario: Three tabs
- **WHEN** the Kits page is opened on a phone 360 px wide with 2 kits installed
- **THEN** Installed 2, Available and Updates are within the screen
