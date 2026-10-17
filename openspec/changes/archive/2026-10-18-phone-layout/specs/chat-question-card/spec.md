## MODIFIED Requirements

### Requirement: The card keeps the chat in view and expands within its page

The card SHALL be at most half the chat's height unless the human set another height
(requirement "The human can resize the card in the chat"); its list of questions
SHALL scroll inside it while its tabs and its Send row stay in view. An icon button at
the right of its tabs (no text; its name and tooltip "Expand the card") SHALL show the
card over its page's area, never over the whole window: in a session's chat over the
chat's whole area, the feed and the composer hidden, the session's head, tabs and team
row seen and usable; on Needs you over the page's content area under its session's name
line, the other sessions' cards and the waiting agents' rows hidden. Nothing around it
SHALL be dimmed. There an icon button ("Collapse the card") or Esc SHALL bring it back,
as it was before (minimized when it was), and it SHALL come back by itself when nothing
waits any more. While an artifact panel is open, Esc SHALL close the panel only and leave
the card expanded. In the phone layout held sideways (capability phone-layout) the team
row SHALL not be shown, expanded or not.

#### Scenario: Long questions
- **WHEN** the supervisor's tab holds three questions whose text is longer than half the
  chat
- **THEN** the card's list scrolls inside and "Send 3 answers to supervisor" stays in view

#### Scenario: Expanded and back
- **WHEN** the human clicks the expand icon, then presses Esc
- **THEN** the card covers the chat's area, then stands above the composer again

#### Scenario: Expanded from minimized
- **WHEN** the card is minimized and the human clicks the expand icon, then presses Esc
- **THEN** the whole card covers the chat's area, then stands minimized above the composer

#### Scenario: The session around an expanded card
- **WHEN** the human expands the card in session lad-46's chat
- **THEN** the feed and the composer are hidden, the card fills the chat's width and
  height, and the session's tabs (Activity, Agents, Flows, Artifacts) and the team row are
  seen and can be clicked, with no scrim

#### Scenario: An artifact from an expanded card
- **WHEN** the human clicks the chip `lad-46-plan` in the expanded card, presses Esc, then
  Esc again
- **THEN** the artifact panel shows on the right over the card, the first Esc closes it
  with the focus back on the chip and the card still expanded with its picks, and the
  second Esc folds the card with the focus on the expand button

#### Scenario: Expanded on Needs you
- **WHEN** Needs you shows the cards of lad-46 and docs-site and the human expands
  lad-46's
- **THEN** lad-46's name line and its card fill the page's content area, docs-site's card
  and the agents' rows are hidden, and folding it shows them again

### Requirement: The human can minimize the card in the chat

In a session's chat the waiting card SHALL have an icon button "Minimize the card" left
of its expand icon. Minimized, the card SHALL show its tabs and one line with the shown
tab's first item's question, cut to one line, and no answer buttons, choices or fields;
the icon SHALL then be "Restore the card". A click on that icon, on the line or on a tab
SHALL restore the whole card (a tab clicked is shown). The card SHALL stay minimized,
also across a reload in the same browser, while every tab it shows was there when it was
minimized, and SHALL restore itself when a new tab comes. Minimizing SHALL change nothing
of what waits: the gate or question stays open, and Needs you's count and the
notifications are as before. Needs you's cards SHALL have no minimize icon. In the phone
layout held sideways (capability phone-layout) the chat's card SHALL be minimized by the
layout, without the minimize icon and without changing what the browser keeps: a click on
a tab or on the line SHALL show it expanded, and folding it SHALL minimize it again.

#### Scenario: Minimized while talking to the supervisor
- **WHEN** gate #812 of run task/lad-52 waits and the human clicks "Minimize the card"
- **THEN** the card shows the tab "task/lad-52 1" and the line "Archive the change and
  merge the pull request…", no Approve or Reject, and the feed takes the freed height

#### Scenario: Restored by the line
- **WHEN** the card is minimized and the human clicks its line
- **THEN** the whole card is back with gate #812's question, note and buttons

#### Scenario: A new gate restores it
- **WHEN** the card is minimized with the tab of task/lad-52 and a gate of run task/lad-53
  opens
- **THEN** the card is restored with both tabs and task/lad-52's tab still shown

#### Scenario: A question added to a tab
- **WHEN** the card is minimized with supervisor's tab and the supervisor asks one more
  question
- **THEN** the card stays minimized and the tab reads "supervisor 2"

#### Scenario: After a reload
- **WHEN** the human minimized the card and reloads the page
- **THEN** the card is minimized

### Requirement: The human can resize the card in the chat

In a session's chat, in a window wider than 900 px, the edge between the feed and the
waiting card SHALL be a splitter: dragging it, or ↑ / ↓ on it when focused, SHALL set the
card's height between its least height and the chat's height less the feed's least height
(160 px), and a double click SHALL set the default height, half the chat's. The chosen
height SHALL be kept in the browser, one value for every session's chat; a chat too short
for it SHALL show the card lower without forgetting the chosen height. Dragging the edge
down past the card's least height SHALL minimize the card. Needs you SHALL have no such
edge, nor a window of 900 px or less, nor the phone layout (capability phone-layout),
whatever its width, where the card is at most half the chat's height.

#### Scenario: Made smaller
- **WHEN** the human drags the edge above the card down to 230 px
- **THEN** the card is 230 px high, its list scrolls inside with the buttons in view, and
  after a reload and in another session's chat the card is 230 px high

#### Scenario: Back to the default
- **WHEN** the human double-clicks the edge
- **THEN** the card is half the chat's height

#### Scenario: Dragged to the bottom
- **WHEN** the human drags the edge down past the card's least height
- **THEN** the card is minimized

#### Scenario: A narrow window
- **WHEN** the window is 800 px wide
- **THEN** there is no edge above the card, and "Minimize the card" works

