# chat-question-card Specification

## Purpose
An agent's question to the human (`ask_human`) as the web UI's session chat shows it: while
open, with the session's open gates, in one waiting card above the composer, a tab per
agent and per gate; once closed, its choices and the human's reply in one card in the
feed (docs/design/ui.md, A question; The waiting card).

## Requirements

### Requirement: A closed question card shows the chosen choice once

A closed question card whose reply is in the window SHALL show the choice the human picked
only in the card's list of choices, marked "✓". The reply block under the list SHALL show
the small "Y", "You · answered" and the reply's time, then only the comment that came with
the choice when there is one (Markdown with line breaks); it SHALL NOT repeat the choice.
A reply in the human's own words SHALL show those words in the reply block, and no choice
in the list SHALL be marked for it. The quiet line of the supervisor's recommendation in a
closed card (capability lead-recommendation) names the option the supervisor recommended,
not the human's choice: it is no repeat of the choice, and the choice stays marked only in
the list.

#### Scenario: A choice without a comment
- **WHEN** the human answers question #5 (choices "yes", "later") with the choice "yes"
- **THEN** its card lists "✓ yes" and "later", and its reply block holds "You · answered"
  and the time and no other text

#### Scenario: A choice with a comment
- **WHEN** the human answers question #8 with the choice "later" and the comment "after the
  tag"
- **THEN** its card lists "✓ later" once, and its reply block holds "You · answered", the
  time and "after the tag"

#### Scenario: An answer in the human's own words
- **WHEN** the human answers question #5 with the text "after the release" and no choice
- **THEN** no choice of its card is marked, and its reply block holds "You · answered", the
  time and "after the release"

#### Scenario: An answer given after other rows
- **WHEN** the human's choice "later" with the comment "after the tag" comes after other
  rows of the chat
- **THEN** the card shows it as in the scenario of a choice with a comment, and the quiet
  line "You answered question #8 ↑" where it was given still starts with "later" and the
  comment

#### Scenario: A choice the supervisor recommended too
- **WHEN** the human answers question #8 with the choice "later" and the supervisor had
  recommended "later"
- **THEN** its card lists "✓ later" once, the recommendation's quiet line reads
  "Supervisor recommended: later", and the reply block does not name the choice

### Requirement: What waits in a session is answered in one card above the composer

While a session has open questions to the human or open gates, its chat SHALL show exactly
one card above the composer, the waiting card, and no other place in the chat SHALL take an
answer to them. The card SHALL have a tab per agent with open questions, holding all of
that agent's open questions, and a tab per open gate; the tabs SHALL stand in the order in
which their first item was asked. With nothing open the card SHALL not be shown. Its open
questions SHALL come from the list of what waits for the human (`state.waiting_items`, as
Needs you shows it) and its gates from the session's gates. The composer SHALL stay a plain
message to its recipient and SHALL have no hint about gates.

#### Scenario: Three things wait
- **WHEN** the supervisor asked #12 and #13, a gate of run task/lad-27 opened, then
  developer asked #14
- **THEN** the chat's card has the tabs "supervisor 2", "task/lad-27 1" and "developer 1",
  in that order, and the first is shown

#### Scenario: Nothing waits
- **WHEN** every question is answered and every gate is closed
- **THEN** the chat shows no card and the composer as before

### Requirement: A tab shows whose items it holds

A tab of an agent SHALL show that agent's avatar letter in its avatar colour, its name and
the number of its open questions; a gate's tab the Flows icon in its run's colour (the
team's run colour), the run's name and 1. A tab's top edge SHALL be in that colour, dashed
for a gate. The number SHALL be a muted badge. The card's ground SHALL be the UI's "waits
for you" ground (`--human-ground`) with a `--human` frame; the shown tab SHALL lie on that
ground, tinted with its colour.

#### Scenario: Colours of an agent and a run
- **WHEN** the card has a tab of developer and a tab of run task/lad-27
- **THEN** developer's tab has the letter "D" in developer's avatar colour and a solid top
  in it, and the run's tab has the Flows icon and a dashed top in the run's colour

### Requirement: The shown tab is the human's choice

Clicking a tab SHALL show its items. The shown tab SHALL stay shown while items come or
go on other tabs; a new question SHALL add to its agent's tab, or add a tab, without
switching. When the shown tab has no item left, the first tab SHALL be shown.

#### Scenario: A new question meanwhile
- **WHEN** the human looks at developer's tab and the supervisor asks another question
- **THEN** developer's tab stays shown and the supervisor's tab's number grows by one

### Requirement: An agent's tab sends its answers together

An agent's tab SHALL list its open questions, numbered when it has more than one, each with
its text, its details (Markdown) and its attachments, its choices, **Other…** when the
question takes a free answer, and **Skip**. A choice SHALL be picked by a click and unpicked
by a second; Other… SHALL open a field for an own answer, Skip a field for an optional
comment, and each of the three SHALL exclude the other two. The tab's one button,
**Send answer to <agent>** or **Send <n> answers to <agent>**, SHALL be off until each of
its questions has a picked choice, an own answer that is not blank, or Skip; with more than
one question "<k> of <n> answered" SHALL stand beside it until then. Send SHALL send all of
the tab's replies in one request (`POST …/answers`); a refusal SHALL show on the tab with
the core's reason, with the human's picks kept.

#### Scenario: Two questions, one answered
- **WHEN** the supervisor's tab has two questions and only the first has a picked choice
- **THEN** "Send 2 answers to supervisor" is off and "1 of 2 answered" stands beside it

#### Scenario: All answered
- **WHEN** the first has the choice "short" and the second Other… with "main, then rebase"
- **THEN** Send is on, and a click posts both replies in one request

#### Scenario: A question that takes no own answer
- **WHEN** a question has choices and no free answer
- **THEN** it shows its choices and Skip, and no Other…

### Requirement: A gate's tab answers the gate at once

A gate's tab SHALL show the gate's question, the note that led to it with its artifacts,
the artifacts it reads, the comment for the next step and the gate's buttons (Approve /
Reject, a choice gate's options, Continue / Cancel run at a loop limit), which SHALL answer
the gate at once through `runs.answer`, as the gate's card did. In a stopped session the
buttons SHALL be off and the tab SHALL say "The session is stopped: resume it to answer."

#### Scenario: Approve
- **WHEN** the human clicks Approve on the tab of task/lad-27
- **THEN** the gate is answered `approve` with the comment, the run moves on and the tab
  goes

#### Scenario: A stopped session
- **WHEN** the session is stopped with its gate open
- **THEN** the card keeps the gate's tab, its buttons off, with "The session is stopped:
  resume it to answer."

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
the card expanded.

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

### Requirement: The feed shows an open item as one line leading to its tab

The chat's feed SHALL show each open question and each open gate where it was asked as one
quiet line: "<agent> asked: <question> ↓" and "Gate #<id> <run> · <state> waits:
<question> ↓", whose arrow SHALL select the item's tab and mark the item. Once answered, a
question SHALL show its closed card and a gate its closed line, as before. A link to an open
item (`#message-<id>`, `#gate-<id>`: Needs you, a notification) SHALL select its tab. A
dismissed question SHALL read "skipped": "You · skipped" in its closed card and "You skipped
question #<id> ↑" as its late line.

#### Scenario: An open question in the feed
- **WHEN** the supervisor asked "Which branch should the PR target?"
- **THEN** the feed has the line "supervisor asked: Which branch should the PR target? ↓",
  and its arrow shows the supervisor's tab with that question marked

#### Scenario: After the answer
- **WHEN** the human sent the supervisor's tab with "main" for that question
- **THEN** the line is gone and the question's closed card lists "✓ main"

### Requirement: Needs you shows each session's waiting card

Needs you SHALL show, for each session not stopped with open questions or gates, the
session's name, a link "In the chat" and the same waiting card with the same behaviour,
answered in place, but for minimizing and resizing, which only a session's chat has.
Agents waiting in their terminal SHALL stay rows with their reason and "Open terminal".

#### Scenario: Two sessions
- **WHEN** lad-28 has a question and a gate open and docs-site a question
- **THEN** Needs you shows two cards, one per session, each with its own tabs

#### Scenario: No minimize or edge on Needs you
- **WHEN** lad-28's card is minimized in its chat and the human opens Needs you
- **THEN** Needs you shows lad-28's whole card, with no "Minimize the card" icon and no
  edge above it

### Requirement: The human can minimize the card in the chat

In a session's chat the waiting card SHALL have an icon button "Minimize the card" left
of its expand icon. Minimized, the card SHALL show its tabs and one line with the shown
tab's first item's question, cut to one line, and no answer buttons, choices or fields;
the icon SHALL then be "Restore the card". A click on that icon, on the line or on a tab
SHALL restore the whole card (a tab clicked is shown). The card SHALL stay minimized,
also across a reload in the same browser, while every tab it shows was there when it was
minimized, and SHALL restore itself when a new tab comes. Minimizing SHALL change nothing
of what waits: the gate or question stays open, and Needs you's count and the
notifications are as before. Needs you's cards SHALL have no minimize icon.

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
edge, nor a window of 900 px or less.

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

### Requirement: The card's text fields grow with their text and stay in view

The waiting card's text fields, an own answer (Other…), the comment of a Skip and a gate's
comment for the next step, SHALL open 3 lines high, SHALL grow with their text up to
8 lines and then scroll inside, and SHALL have no resize handle; each SHALL be as wide as
its question. While the human types in one of them, its lower edge with the caret SHALL
stay in view within the card: when the field grows past the card's visible list, the list
SHALL scroll by as much. A gate's comment field SHALL grow the same way wherever the
gate's panel shows.

#### Scenario: A short own answer
- **WHEN** the human picks Other… and types one short line
- **THEN** the field is 3 lines high

#### Scenario: A long own answer
- **WHEN** the human types an answer of 12 lines in the field of Other…
- **THEN** the field is 8 lines high, scrolls inside, and its lower edge with the caret
  is within the card's list and within the window

#### Scenario: The expanded card
- **WHEN** the card is expanded and the human types an answer of 12 lines
- **THEN** the field is 8 lines high and its lower edge is above the Send row and within
  the window

#### Scenario: A gate's comment
- **WHEN** the human types a comment of 12 lines on a gate's tab
- **THEN** the field is 8 lines high, scrolls inside, and its lower edge is above the Send
  row and within the window
