# phone-layout Specification

## Purpose
How the web UI reads on a phone: a window no wider than 600 px, or a touch screen no higher
than 500 px, gets a layout of its own (the rail as a menu, a one-line top bar, the session's
details in a sheet, a chat whose composer stays at hand, terminals over the screen,
tooltips on a tap), while a wider window with a mouse keeps its layout, however low.

## Requirements

### Requirement: The UI picks the phone layout by the screen and the pointer

The web UI SHALL use its phone layout exactly while the window is no wider than 600 px, with any
pointer, or the primary pointer is coarse (a touch screen) and the window is no higher than
500 px; the layout SHALL follow the window when it turns or resizes, without a reload. A wider
window with a fine pointer (a mouse or a trackpad) SHALL never use the phone layout, however low.
There SHALL be no setting or switch for it.

#### Scenario: A phone held upright
- **WHEN** the UI is opened on a touch screen 390 px wide and 844 px high
- **THEN** it shows the phone layout

#### Scenario: A phone held sideways
- **WHEN** the same phone turns to 844 px wide and 390 px high
- **THEN** the UI keeps the phone layout, in its sideways form, without a reload

#### Scenario: A computer's narrow window
- **WHEN** the UI is opened with a mouse in a window 390 px wide and 844 px high
- **THEN** it shows the phone layout, with Menu and the session's title in place

#### Scenario: A computer's low window
- **WHEN** the UI is opened with a mouse in a window 1280 px wide and 400 px high
- **THEN** it does not show the phone layout

#### Scenario: A touch laptop
- **WHEN** the UI is opened on a touch screen 1440 px wide and 900 px high
- **THEN** it does not show the phone layout

#### Scenario: A tablet
- **WHEN** the UI is opened on a touch screen 820 px wide and 1180 px high
- **THEN** it does not show the phone layout

### Requirement: On a phone the rail opens as a menu

In the phone layout the rail SHALL not be shown. Menu SHALL open
the rail over the page from the left, with each section's icon and name, the Needs you
count, New session, Help and Settings, and dim the rest of the page. Choosing an item,
a tap on the dimmed page, or Esc SHALL close it; on closing the focus SHALL go back to
Menu. Help SHALL open its menu within the drawer, and choosing one of its items SHALL close
both.

#### Scenario: Going to Kits
- **WHEN** the human taps Menu, then Kits
- **THEN** the Kits page opens and the menu is closed

#### Scenario: A tap beside the menu
- **WHEN** the menu is open and the human taps the dimmed page
- **THEN** the menu closes and the page under it is as it was

#### Scenario: Report a bug on a phone
- **WHEN** the human taps Menu, Help, then Report a bug
- **THEN** the Report a bug page opens, and the drawer and Help's menu are closed

### Requirement: On a phone the top bar starts with Menu and its count

In the phone layout the top bar SHALL start with a Menu
button (three lines, accessible name "Menu", or "Menu, N waiting" while N things wait for
the human) that shows the Needs you count as a badge while it is not zero.

#### Scenario: Two things wait
- **WHEN** a gate and a question wait and the human looks at the top bar on a phone
- **THEN** Menu shows the badge 2 and is named "Menu, 2 waiting"

### Requirement: On a phone the top bar is one line

In the phone layout the top bar SHALL be one line no higher than 52 px upright and 44 px
sideways, and SHALL not wrap. On a session's page it SHALL hold, left to right: Menu, the
session's status dot, the session's title (or name) with a chevron as a button that opens the
session's details, cut with "…" when long, the change feed's mark and Stop session. On another page
it SHALL hold Menu and the page's title. Menu and the session's actions SHALL be 44 by 44 px.

#### Scenario: A session's page upright
- **WHEN** the human opens session lad-95 on a phone 390 px wide
- **THEN** the top bar is one line holding Menu, the status dot, "lad-95", the live dot and
  Stop, and no folder, git, kit or CLI fact

#### Scenario: A long title
- **WHEN** the session's title is longer than the room left
- **THEN** it is cut with "…" and the line does not wrap

### Requirement: On a phone the change feed's mark is a dot or a word

In the phone layout the change feed's mark SHALL be a dot while the
feed is live and the no-network icon on the warning ground, named "reconnecting…", while it is
lost (capability connection-loss), and SHALL open the system panel
as before while live; a newer LADO's `↑ X.Y.Z` SHALL stay beside it.

#### Scenario: The feed is lost
- **WHEN** the change feed reconnects
- **THEN** the mark is the no-network icon in place of the dot, named "reconnecting…"

### Requirement: On a phone the session's details open from its name

In the phone layout a tap on the session's name in the top bar SHALL open a sheet over the
page's bottom, named by the session, with the content of Details on a computer, from the
same component (capability session-head, "Details names every fact of the session"). A tap
outside the sheet, Esc or its close button SHALL close it.

#### Scenario: The whole folder
- **WHEN** the session's folder is `/Users/kao/Projects/lado/.lado/worktrees/lad-95/task-lad-95`
  and the human taps the session's name
- **THEN** the sheet shows the whole path, wrapped, and Copy path copies it

#### Scenario: The state in the sheet
- **WHEN** a question waits in the session and the human taps the session's name
- **THEN** the sheet's state line starts with `needs you · 1 question`, then the run time

### Requirement: On a phone Rename in the session's details edits the title

In the phone layout Rename in the session's details SHALL edit the title in the sheet, with
the same field as in the head on a computer.

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
scroll by itself under the top bar. The app SHALL be as high as the part of the window
the human sees, its bottom never cut by the browser's bars. In a session's chat the feed
SHALL scroll by itself, and the waiting card and the composer SHALL stay whole at the
chat's bottom; the card SHALL be at most half the chat's height, its head and footer whole and
only its report giving way.

#### Scenario: Writing with a gate waiting
- **WHEN** a gate waits and the human opens the session's chat on a phone 390×844
- **THEN** the composer is at the screen's bottom without scrolling, the card above it has
  its footer whole, and the feed above scrolls by itself

#### Scenario: The browser's bottom bar
- **WHEN** a question waits and the human opens the session's chat in a phone's browser
  whose bottom bar covers the window's last 90 px
- **THEN** the composer's lower edge is above that bar, and the whole composer and the
  card's Send button are in sight without scrolling

#### Scenario: The expanded card
- **WHEN** the human expands the waiting card on a phone
- **THEN** the card fills the page under the top bar, the session's tabs and the Team row
  are not shown, and its Send button is in sight, above the browser's bottom bar

### Requirement: On a phone the composer's text is large and shows no keys hint

In the phone layout the composer's text SHALL be at least 16 px, and its keys hint ("Enter to send ·
Shift+Enter …") SHALL not be shown on a touch screen. The line under the composer SHALL not show
`to supervisor`, and with nothing to show it SHALL take no height.

#### Scenario: No keys hint
- **WHEN** the chat is shown on a touch screen
- **THEN** the composer shows no "to supervisor", no keys hint and no empty line

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
- **THEN** the card shows whole, its footer in sight

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

### Requirement: On a phone the app shrinks above the on-screen keyboard

When the on-screen keyboard opens on a phone, the app SHALL shrink to the part of the
window above it: the top bar SHALL stay at the screen's top, and the composer and the
waiting card's Send row SHALL stay above the keyboard. When the keyboard closes, the app
SHALL be as high as the visible part of the window again.

#### Scenario: The on-screen keyboard
- **WHEN** a question waits and the human taps the composer on a phone, and the keyboard
  covers the lower 300 px of the screen
- **THEN** the top bar stays at the screen's top, the composer and the card's Send button
  are above the keyboard

#### Scenario: The keyboard closes
- **WHEN** the human closes the keyboard
- **THEN** the app is as high as the visible part of the window again, the composer at its
  bottom

### Requirement: On a phone an expanded card hides the session's tabs and the Team row

In the phone layout an expanded waiting card in a session's chat SHALL fill the session's
page under the top bar: the feed, the composer, the session's tabs and the Team row SHALL
not be shown while it is expanded, whether its button or the phone held sideways expanded
it, and SHALL show again when it folds.

#### Scenario: Expanded by its button
- **WHEN** the human taps Expand the card in the session's chat on a phone
- **THEN** the session's tabs and the Team row are not shown

#### Scenario: Folding the expanded card
- **WHEN** the human taps Collapse the card on a phone
- **THEN** the card stands above the composer again, and the session's tabs and the Team
  row show again

### Requirement: On a phone a field in focus keeps the card and folds what is around it

In the phone layout, in a session's chat, while a field of the waiting card's footer has the
focus, the card SHALL not expand: the session's tabs, the Team row, the card's report, the
recommendation's splitter and the choices' area SHALL not be shown, and the composer SHALL be a
line: on a gate's tab "Commenting on gate #<id> above", on a question's the line of capability
chat-question-card. When the field loses the focus all of it SHALL show again.

#### Scenario: A gate's comment above the keyboard
- **WHEN** a gate waits in the session's chat on a phone 402×874, the human taps the
  gate's comment field and the keyboard leaves 440 px of the window visible
- **THEN** the card is not expanded, the session's tabs, the Team row and the report do not
  show, and the field, Approve, Reject and "Commenting on gate #1 above" lie within the
  visible 440 px

#### Scenario: An own answer
- **WHEN** a question with a free answer waits on the same phone and the human taps
  Other…
- **THEN** the field has the focus, the choices' area does not show, and the field, "Send
  answer to supervisor" and "Answering question #5 above" lie within the visible 440 px

#### Scenario: The keyboard closes
- **WHEN** the human closes the keyboard and the field loses the focus
- **THEN** the session's tabs, the report, the choices' area, the Team row and the composer
  show again, and the comment typed stays in the field

### Requirement: Only a phone's chat folds around a field

On Needs you, and outside the phone layout, a field's focus SHALL change nothing.

#### Scenario: A computer
- **WHEN** the human clicks a gate's comment field with a mouse in a window 700 px wide
- **THEN** the card and the composer stay as they were

#### Scenario: Needs you on a phone
- **WHEN** the human taps a card's field on Needs you on a phone and the keyboard opens
- **THEN** nothing folds, the browser keeps the field in sight, and the page scrolls on to the
  buttons under it, which the keyboard may cover

### Requirement: On a phone a field keeps the context it needs

A field in the context of several questions SHALL keep that context, and SHALL stay in its view
when the keyboard opens; the session's tabs and the Team row SHALL not be shown while it has the
focus. An expanded card SHALL keep its context with a field in focus.

#### Scenario: Several questions
- **WHEN** a tab of three questions waits and the human taps Other… on the last, and the keyboard
  leaves 440 px visible
- **THEN** the context still shows, and the field lies within its visible part

#### Scenario: The expanded card
- **WHEN** the human expands the card to read its note and taps the comment field
- **THEN** the context stays

### Requirement: On a phone the card's field and buttons stay above the keyboard

With a field of the card in focus, the field, the buttons and the composer's line SHALL stay above
the on-screen keyboard, by the order of capability chat-question-card, requirement "A footer
taller than its room gives way in order"; the head SHALL go before the recommendation.

#### Scenario: Less room than the frame
- **WHEN** the keyboard leaves 350 px of the window visible and a gate's comment has the focus,
  under a recommendation of two lines
- **THEN** the head is gone or cut, and the field, Approve, Reject and the line lie within the
  visible 350 px

#### Scenario: Six choices
- **WHEN** the keyboard leaves 350 px of the window visible and Other… of a question of six
  choices has the focus
- **THEN** the field and Send answer lie within the visible 350 px

#### Scenario: Six choices under a recommendation
- **WHEN** the keyboard leaves 340 px of the window visible and the field of Other… or Skip
  has the focus, on a question of six choices under a recommendation of two lines
- **THEN** the choices' area does not show, and the recommendation, the field and Send answer
  lie whole within the visible 340 px

### Requirement: On a phone a gate's and a question's tabs stand whole

In the phone layout two tabs of the waiting card SHALL stand whole in their row, a name cut with
an ellipsis before the row scrolls, and each SHALL keep its count.

#### Scenario: Two tabs
- **WHEN** a gate of ship/x and a question of the supervisor wait on a phone 390×844 or 360×780
- **THEN** both tabs lie within their row and show their counts, whichever is shown

### Requirement: On a phone the waiting card's targets are 44 px

In the phone layout the card's tabs, Minimize and Expand (44×44), its fields, its chips, its
choices, Other… and Skip, and Approve, Reject and Send answer SHALL be 44 px high, and the answer's
buttons SHALL share the footer's width.

#### Scenario: Measured
- **WHEN** a question waits on a phone 390×844
- **THEN** its tab, a choice, Skip and Send answer are each 44 px high

### Requirement: On a phone the top bar's title and link are easy to tap

In the phone layout the session's title SHALL have a target 44 px high, the height of the top bar.
The change feed's link SHALL have a target 44 px high and 33 px wide, taken from the gaps at its
sides, so that the title loses no width. What is drawn SHALL not change.

#### Scenario: The title
- **WHEN** the human taps the top bar's height above the title's text
- **THEN** the session's details open

#### Scenario: The link
- **WHEN** the human taps 8 px beside the link's dot
- **THEN** the System panel opens

### Requirement: On a phone the recommendation's splitter is easy to take

In the phone layout the recommendation's splitter of the chat's card SHALL take a touch 24 px
high, drawn as on a computer, and SHALL not scroll the page while it is dragged. It SHALL not show
while a field of the card has the focus.

#### Scenario: Dragged by a finger
- **WHEN** a gate with a long recommendation waits on a phone 390×844 and the human drags 8 px
  above the splitter's line upward
- **THEN** the recommendation's text grows and the feed does not scroll
