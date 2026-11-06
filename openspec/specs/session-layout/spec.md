# session-layout Specification

## Purpose
How a session's page fits the window outside the phone layout: above 900 px the chat keeps its
width while the list and the terminals fold and come back, and at 601 to 900 px the page stands
still with the list and the terminals over it. It also covers the session strip, the terminal
strip and the tabs when short of room, and a touch screen's visible height.

## Requirements

### Requirement: Above 900 px the chat keeps 420 px

In a window wider than 900 px that is not the phone layout, the session's column SHALL be at
least 420 px wide. Short of room, terminals the human did not open SHALL fold to their strip;
terminals the human opened SHALL stay and the session list SHALL fold to its strip instead. The
rail SHALL never fold by itself.

#### Scenario: Terminals nobody opened
- **WHEN** nothing is stored and the window is 1024 px wide
- **THEN** the list is open, the terminals are in their strip and the chat is 672 px wide

#### Scenario: Terminals the human opened
- **WHEN** the human opens the terminals in a window 1024 px wide
- **THEN** the terminals stay open, the list folds to its strip of 48 px and the chat is at
  least 420 px wide

#### Scenario: Every width
- **WHEN** the window is 901, 1024, 1101, 1280 or 1440 px wide, with the terminals opened by the
  human or not
- **THEN** the chat is at least 420 px wide

### Requirement: When folding one column is not enough the other gives way

If the chat is still short of 420 px after the first fold, the other of the two columns SHALL
fold as well, but terminals opened by the human SHALL first narrow, no further than their least
width of 280 px, their stored width kept. A terminal in control SHALL count as opened by the
human; if it folds all the same, control SHALL end with no message of its own.

#### Scenario: The rail opened by hand
- **WHEN** the human opened the rail and the terminals and the window is 901 px wide
- **THEN** the list is in its strip, the terminals are in theirs and the chat is at least 420 px
  wide, and the rail stays open

#### Scenario: A wide panel
- **WHEN** the human set the terminals to 640 px and opened them in a window 1024 px wide
- **THEN** the list is in its strip, the panel is 496 px wide, and at 1440 px it is 640 px again

#### Scenario: A terminal in control
- **WHEN** the human controls a terminal of a panel opened by default and the window narrows
  to 1024 px
- **THEN** the panel stays open with control, and the list folds

### Requirement: A column folded for room comes back and leaves no trace

A column folded for room SHALL open again by itself once it and 420 px of chat fit, the list
before the terminals. Folding for room SHALL write nothing to the browser's storage. What the
human does (folds, opens, sets a width) SHALL be stored as before and survive a reload, and SHALL
be what a column returns to. When the human opens a column short of room, it SHALL stay open and
the other SHALL fold.

#### Scenario: The window widens
- **WHEN** the terminals folded for room at 1024 px and the window widens to 1440 px
- **THEN** the terminals are open again

#### Scenario: Both come back in order
- **WHEN** both columns folded for room and the window widens to where only the list fits
- **THEN** the list is open and the terminals are in their strip

#### Scenario: A fold stored nowhere
- **WHEN** the terminals fold for room
- **THEN** `lado.terminals` and `lado.sessionsList` are as they were

#### Scenario: The column opened last survives a reload
- **WHEN** the human opened the terminals, then the list, in a window 1024 px wide and reloads
- **THEN** the list is open and the terminals are in their strip

#### Scenario: The human's fold
- **WHEN** the human folds the terminals in a window 1440 px wide and reloads
- **THEN** they stay folded, also after the window narrows and widens

#### Scenario: The list opened short of room
- **WHEN** the terminals opened by the human stand beside the folded list at 1024 px and the
  human presses Sessions
- **THEN** the list is open and the terminals fold to their strip

### Requirement: The rail and the terminals start by the window

With no stored choice the rail SHALL be collapsed in a window narrower than 1600 px and expanded
from 1600 px, following the window. The human's choice by the rail's button SHALL be kept and SHALL
win. With no width set on their edge the terminals SHALL be 40 % of the session's area (the width
beside the rail and the list), at least 360 px and at most 640 px. A width set on the edge SHALL be
kept as before.

#### Scenario: A laptop
- **WHEN** nothing is stored and the window is 1440 px wide
- **THEN** the rail is 60 px wide, the terminals 448 px and the chat 672 px

#### Scenario: A large screen
- **WHEN** nothing is stored and the window is 1600 px wide
- **THEN** the rail is expanded

#### Scenario: The human's rail
- **WHEN** the human expands the rail at 1280 px and reloads
- **THEN** the rail stays expanded

### Requirement: The list's strip is 48 px and opens the list

The session list folded to a strip SHALL be 48 px wide, with its Sessions button, "+" and the
sessions' badges.

#### Scenario: Opening it
- **WHEN** the human presses Sessions on the strip
- **THEN** the list opens

### Requirement: A strip's badges tell sessions apart

A session's badge SHALL be, when its title or else its name starts with `<word>-<number>`, the
last 3 digits of that number, whatever follows it. Otherwise it SHALL be the two letters of the
title, or else of the name, as before. Two badges alike in the strip SHALL differ by a mark
after the later one (`154·2`).

#### Scenario: Task sessions
- **WHEN** the strip shows `lad-154-epic` and `lad-189` titled `lad-189 (session UI review)`
- **THEN** their badges are `154` and `189`

#### Scenario: A plain title
- **WHEN** the strip shows a session titled `Checkout redesign`
- **THEN** its badge is `CR`

#### Scenario: A clash
- **WHEN** the strip shows `lad-154` and `web-2154`
- **THEN** their badges are `154` and `154·2`

### Requirement: A strip's badge says what waits and stays in view

A session that needs the human SHALL show the waiting diamond on the corner of its badge, not its
colour alone. The strip SHALL scroll the open session's badge into view when a session opens.

#### Scenario: A gate waits
- **WHEN** a gate waits in a session of the strip
- **THEN** its badge has the diamond on its corner

#### Scenario: More sessions than fit
- **WHEN** the human opens a session whose badge lies past the strip's edge
- **THEN** the strip scrolls until the badge is whole

### Requirement: A session's tabs give way in levels

When a session's tabs do not fit their bar they SHALL lose first their icons, then their counts.
When they still do not fit, the bar SHALL scroll sideways with a fade of 56 px at its right end and
a button › of 26 px; once scrolled, the same ‹ SHALL show at its left end, and each SHALL go at
its end of the bar. The level SHALL follow the bar's width without a reload. The tab shown SHALL be
in view.

#### Scenario: A little short
- **WHEN** the tabs with icons and counts are wider than the bar and fit without icons
- **THEN** the tabs show no icons and keep their counts

#### Scenario: Very short
- **WHEN** the tabs without icons and counts are wider than the bar
- **THEN** a fade and › show at the right, and › scrolls the tabs until Artifacts is seen, when ›
  goes and ‹ shows

### Requirement: The terminal strip has a button per agent

The terminals' strip SHALL be 32 px wide. It SHALL hold, top to bottom, a button that opens the
panel, a button of 24×24 per agent of the session, and the caption Terminals. An agent's button
SHALL show the agent's avatar colour and letter, as in the feed, and a status mark of 8 px in its
corner, and SHALL be named `Open <agent>'s terminal`. It SHALL open the panel on that agent's
terminal. With more agents than fit the strip SHALL scroll.

#### Scenario: Opening an agent's terminal
- **WHEN** the human presses `Open critic's terminal` on the strip
- **THEN** the panel opens with critic's terminal shown

#### Scenario: A waiting agent
- **WHEN** an agent waits for the human
- **THEN** its button shows the waiting diamond in its corner

### Requirement: At 601 to 900 px a session's page stands still

In a window 601 to 900 px wide that is not the phone layout, a session's page SHALL not scroll as
a window; it SHALL be the window's height. Top to bottom it SHALL show the top bar, the session
strip as a row of 48 px, the tabs, the team row, the feed that scrolls inside and stays at its
end, the waiting card and the composer. Other pages SHALL scroll as before.

#### Scenario: A tablet
- **WHEN** the window is 768 or 880 px wide with a gate open on a session's page
- **THEN** the window does not scroll, and the card and the composer are in sight at once

#### Scenario: Needs you
- **WHEN** the window is 768 px wide and the human opens Needs you
- **THEN** the page scrolls as before and its card is whole

### Requirement: A touch screen wider than a phone fits the part of the window it sees

On a touch screen wider than 600 px that is not the phone layout, the app SHALL be as high as the
part of the window the human sees, where it stands still: a session's page at 601 to 900 px, every
page above 900 px. A computer with a mouse SHALL keep the window's height.

#### Scenario: A tablet held sideways
- **WHEN** a touch screen 1180 px wide shows 688 px of its 734 px, or 312 px with the keyboard open
- **THEN** the app is that high and the card's field and buttons lie in the part seen

#### Scenario: A large tablet upright
- **WHEN** a touch screen 1032 px wide and 1366 px high shows 1320 px
- **THEN** the app is 1320 px high and the composer lies in the part seen

### Requirement: At 601 to 900 px the columns start folded

In a window 601 to 900 px wide that is not the phone layout, the list and the terminals SHALL
start folded whatever is stored, and opening them SHALL not be stored.

#### Scenario: A choice stays where it was
- **WHEN** the human opened the list and the terminals at 1440 px, then narrows to 768 px and
  back to 1440 px
- **THEN** at 768 px both are folded, and at 1440 px both are open

#### Scenario: A team chip
- **WHEN** the human presses a team chip at 768 px
- **THEN** the panel opens over the session on that agent's terminal, and nothing is stored

### Requirement: At 601 to 900 px the list opens over the session

In a window 601 to 900 px wide that is not the phone layout, the strip's Sessions SHALL open the
list as a panel of 300 px over the session's column, on its left, with the session in place under
it. Choosing a session, Esc, a click beside it and Sessions SHALL close it.

#### Scenario: The list
- **WHEN** the human presses Sessions at 768 px, then Esc
- **THEN** the list lies over the session, the window does not scroll, and then the list closes
  with the focus on Sessions

#### Scenario: A choice
- **WHEN** the human chooses a session in the open list at 768 px
- **THEN** the session opens and the list is closed

### Requirement: At 601 to 900 px the terminals open over the session

In a window 601 to 900 px wide that is not the phone layout, the terminals' strip SHALL stay on the
right; open, the panel SHALL lie over the session's column, `min(560px, 100% − 48px)` wide. Esc
SHALL close it with the focus back on the strip, but in control Esc SHALL stay the terminal's.
Closing it SHALL end control.

#### Scenario: Terminals over the session
- **WHEN** the human opens the terminals at 768 px
- **THEN** the panel is 560 px wide over the session, and Esc closes it

#### Scenario: Esc in control
- **WHEN** the human controls a terminal in the open panel at 768 px and presses Esc
- **THEN** the terminal gets the key and the panel stays open
