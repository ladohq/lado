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

#### Scenario: A choice without a comment
- **WHEN** the human answers question #5 (choices "yes", "later") with the choice "yes"
- **THEN** its card lists "✓ yes" and "later", and its reply block holds "You · answered"
  and the time and no other text

#### Scenario: A choice with a comment
- **WHEN** the human answers question #8 with the choice "later" and the comment "after the
  tag"
- **THEN** its card lists "✓ later" once, and its reply block holds "You · answered", the
  time and "after the tag"

#### Scenario: An answer given after other rows
- **WHEN** the human's choice "later" with the comment "after the tag" comes after other
  rows of the chat
- **THEN** the card shows it as in the scenario of a choice with a comment, and the quiet
  line "You answered question #8 ↑" where it was given still starts with "later" and the
  comment

### Requirement: An own answer and the recommendation's line repeat no choice

A reply in the human's own words SHALL show those words in the reply block, and no choice
in the list SHALL be marked for it. The quiet line of the supervisor's recommendation in a
closed card (capability lead-recommendation) names the option the supervisor recommended,
not the human's choice: it is no repeat of the choice, and the choice stays marked only in
the list.

#### Scenario: An answer in the human's own words
- **WHEN** the human answers question #5 with the text "after the release" and no choice
- **THEN** no choice of its card is marked, and its reply block holds "You · answered", the
  time and "after the release"

#### Scenario: A choice the supervisor recommended too
- **WHEN** the human answers question #8 with the choice "later" and the supervisor had
  recommended "later"
- **THEN** its card lists "✓ later" once, the recommendation's quiet line reads
  "Supervisor recommended: later", and the reply block does not name the choice

### Requirement: What waits in a session is answered in one card above the composer

While a session has open questions to the human or open gates, its chat SHALL show exactly
one card above the composer, the waiting card, and no other place in the chat SHALL take an
answer to them. With nothing open the card SHALL not be shown. The composer SHALL stay a plain
message to its recipient and SHALL have no hint about gates.

#### Scenario: Nothing waits
- **WHEN** every question is answered and every gate is closed
- **THEN** the chat shows no card and the composer as before

### Requirement: The waiting card has a tab per agent and per gate, in the order asked

The waiting card SHALL have a tab per agent with open questions, holding all of
that agent's open questions, and a tab per open gate; the tabs SHALL stand in the order in
which their first item was asked. Its open
questions SHALL come from the list of what waits for the human (`state.waiting_items`, as
Needs you shows it) and its gates from the session's gates.

#### Scenario: Three things wait
- **WHEN** the supervisor asked #12 and #13, a gate of run task/lad-27 opened, then
  developer asked #14
- **THEN** the chat's card has the tabs "supervisor 2", "task/lad-27 1" and "developer 1",
  in that order, and the first is shown

### Requirement: A tab shows whose items it holds

An agent's tab SHALL show the agent's avatar letter in its avatar colour, its name and the
number of its open questions; a gate's tab the Flows icon in its run's colour, the run's name
and 1. A tab's top edge SHALL be in that colour, dashed
for a gate. The number SHALL be a badge of `--count-ink` on `--raised`. The card's ground SHALL be the UI's "waits for you" ground (`--human-ground`) with a
`--human` frame; the shown tab SHALL lie on that ground, tinted with its colour.

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

### Requirement: An agent's tab lists its questions with their choices, Other… and Skip

An agent's tab SHALL show its open questions, numbered when it has more than one, each with
its text, its details (Markdown) and its attachments, its choices, **Other…** when the
question takes a free answer and has choices, and a pill **Skip** after them. A choice SHALL be
picked by a click and unpicked by a second; Other… SHALL open a field for an own answer, Skip a
field for an optional comment, and each of the three SHALL exclude the other two.

#### Scenario: A question that takes no own answer
- **WHEN** a question has choices and no free answer
- **THEN** it shows its choices and Skip, and no Other…

### Requirement: An agent's tab is sent only when each question is answered

The tab's one button,
**Send answer to <agent>** or **Send <n> answers to <agent>**, SHALL be off until each of
its questions has a picked choice, an own answer that is not blank or has files, or Skip;
with more than one question "<k> of <n> answered" SHALL stand beside it until then.

#### Scenario: Two questions, one answered
- **WHEN** the supervisor's tab has two questions and only the first has a picked choice
- **THEN** "Send 2 answers to supervisor" is off and "1 of 2 answered" stands beside it

#### Scenario: An own answer of files only
- **WHEN** the only question has Other… picked with an empty field and one file
- **THEN** "Send answer to <agent>" is on

### Requirement: An agent's tab sends its answers together

Send
SHALL send all of the tab's replies, each with its field's files, in one request
(`POST …/answers`); a refusal SHALL show on the tab with the core's reason, with the
human's picks and files kept.

#### Scenario: All answered
- **WHEN** the first has the choice "short" and the second Other… with "main, then rebase"
- **THEN** Send is on, and a click posts both replies in one request

### Requirement: A gate's tab answers the gate at once

A gate's tab SHALL show its question, the note that led to it (whole, no Show more), its
documents' chips, the comment for the next step with its files and its buttons (Approve /
Reject, Continue / Cancel run at a loop limit), which SHALL answer the gate at once through
`runs.answer`, with the comment and the files (a choice gate's: picked, then sent). No band at
the note's left. In a stopped session the
buttons SHALL be off and the tab SHALL say "The session is stopped: resume it to answer."

#### Scenario: Approve
- **WHEN** the human clicks Approve on the tab of task/lad-27
- **THEN** the gate is answered `approve` with the comment, the run moves on and the tab
  goes

#### Scenario: A stopped session
- **WHEN** the session is stopped with its gate open
- **THEN** the card keeps the gate's tab, its buttons off, with "The session is stopped:
  resume it to answer."

#### Scenario: Reject with a file
- **WHEN** the human attaches `server.log` to the comment of task/lad-27's gate and
  clicks Reject
- **THEN** the gate is answered `reject` with the comment and `server.log`, and the tab
  goes

#### Scenario: A loop limit
- **WHEN** run polish/look reaches its loop limit at step review
- **THEN** its tab's head reads "loop limit reached at review: what next?" and its buttons
  Continue (primary) and Cancel run, which answer at once, with no confirmation

### Requirement: The card keeps the chat in view and expands within its page

The card SHALL be as high as its content and at most half the chat's height unless the human
set another height, or its tabs, head, splitter and footer with a report of 56 px take more.
Short of room only its report SHALL give way, down to 56 px; its tabs, its head, the
recommendation's splitter and its footer SHALL not. The report SHALL scroll inside it while the
tabs, the head and the footer stay in view.

#### Scenario: Long questions
- **WHEN** the supervisor's tab holds three questions whose text is longer than half the
  chat
- **THEN** the card's report scrolls inside and "Send 3 answers to supervisor" stays in view

#### Scenario: A short gate
- **WHEN** a gate with a note of two lines waits in a chat 700 px high
- **THEN** the card is as high as its content, with no empty room in it

#### Scenario: A long note in a narrow window
- **WHEN** a gate with a note of 60 lines waits in a chat 800 px high in a window 800 px wide
- **THEN** the card is at most 400 px high, and its comment field and Approve are in it,
  under the report

### Requirement: The expanded card comes back as it was

Nothing around the expanded card
SHALL be dimmed. There an icon button ("Collapse the card") or Esc SHALL bring it back,
as it was before (minimized when it was), and it SHALL come back by itself when nothing
waits any more. While an artifact panel is open, Esc SHALL close the panel only and leave
the card expanded.

#### Scenario: Expanded and back
- **WHEN** the human clicks the expand icon, then presses Esc
- **THEN** the card covers the chat's area, then stands above the composer again

#### Scenario: Expanded from minimized
- **WHEN** the card is minimized and the human clicks the expand icon, then presses Esc
- **THEN** the whole card covers the chat's area, then stands minimized above the composer

#### Scenario: An artifact from an expanded card
- **WHEN** the human clicks the chip `lad-46-plan` in the expanded card, presses Esc, then
  Esc again
- **THEN** the artifact panel shows on the right over the card, the first Esc closes it
  with the focus back on the chip and the card still expanded with its picks, and the
  second Esc folds the card with the focus on the expand button

### Requirement: The feed shows an open item as one line leading to its tab

The chat's feed SHALL show each open question and each open gate where it was asked as one
quiet line: "<agent> asked: <question> ↓" and "Gate #<id> <run> · <state> waits:
<question> ↓", whose arrow SHALL select the item's tab and mark the item. A link to an open
item (`#message-<id>`, `#gate-<id>`: Needs you, a notification) SHALL select its tab.

#### Scenario: An open question in the feed
- **WHEN** the supervisor asked "Which branch should the PR target?"
- **THEN** the feed has the line "supervisor asked: Which branch should the PR target? ↓",
  and its arrow shows the supervisor's tab with that question marked

### Requirement: An answered item shows closed, and a dismissed question reads skipped

Once answered, a
question SHALL show its closed card and a gate its closed line, as before. A
dismissed question SHALL read "skipped": "You · skipped" in its closed card and "You skipped
question #<id> ↑" as its late line.

#### Scenario: After the answer
- **WHEN** the human sent the supervisor's tab with "main" for that question
- **THEN** the line is gone and the question's closed card lists "✓ main"

### Requirement: Needs you shows each session's waiting card

Needs you SHALL show, for each session not stopped with open questions or gates, the
session's name, a link "In the chat" and the same waiting card, answered in place, but for
minimizing, resizing and expanding, which only a session's chat has. The card SHALL be whole:
no limit on its report or its recommendation, no fade and no splitter; the page SHALL scroll,
the footer right under the report. Agents waiting in their terminal SHALL stay rows with their
reason and "Open terminal".

#### Scenario: Two sessions
- **WHEN** lad-28 has a question and a gate open and docs-site a question
- **THEN** Needs you shows two cards, one per session, each with its own tabs

#### Scenario: No minimize or edge on Needs you
- **WHEN** lad-28's card is minimized in its chat and the human opens Needs you
- **THEN** Needs you shows lad-28's whole card, with no "Minimize the card" or "Expand the card"
  icon and no edge above it

#### Scenario: A long note on Needs you
- **WHEN** a gate with a note of 60 lines waits on Needs you in a window 900 px high
- **THEN** the note shows with no scrolling of its own, and the comment field and Approve
  follow right under it, reached by the page's scroll

#### Scenario: A long recommendation and four questions on Needs you
- **WHEN** a gate with a recommendation of ten lines and a tab of four questions wait on Needs
  you
- **THEN** the whole recommendation and all four questions show, with no fade and no splitter

### Requirement: The human can minimize the card in the chat

In a session's chat the waiting card SHALL have an icon button "Minimize the card" left
of its expand icon. Minimized, the card SHALL show its tabs and one line with the shown
tab's first item's question, cut to one line, and no answer buttons, choices or fields;
the icon SHALL then be "Restore the card". A click on that icon, on the line or on a tab
SHALL restore the whole card (a tab clicked is shown).

#### Scenario: Minimized while talking to the supervisor
- **WHEN** gate #812 of run task/lad-52 waits and the human clicks "Minimize the card"
- **THEN** the card shows the tab "task/lad-52 1" and the line "Archive the change and
  merge the pull request…", no Approve or Reject, and the feed takes the freed height

#### Scenario: Restored by the line
- **WHEN** the card is minimized and the human clicks its line
- **THEN** the whole card is back with gate #812's question, note and buttons

### Requirement: The card stays minimized until a new tab comes

The card SHALL stay minimized,
also across a reload in the same browser, while every tab it shows was there when it was
minimized, and SHALL restore itself when a new tab comes. Minimizing SHALL change nothing
of what waits: the gate or question stays open, and Needs you's count and the
notifications are as before. Needs you's cards SHALL have no minimize icon.

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

### Requirement: On a phone held sideways the layout minimizes the card

In the phone
layout held sideways (capability phone-layout) the chat's card SHALL be minimized by the
layout, without the minimize icon and without changing what the browser keeps: a click on
a tab or on the line SHALL show it expanded, and folding it SHALL minimize it again.

#### Scenario: A phone held sideways
- **WHEN** a gate waits and the human opens the chat on a phone 844×390
- **THEN** the card is minimized with no "Minimize the card" icon, a tap on its tab shows
  it expanded, and folding it minimizes it again

### Requirement: The human can resize the card in the chat

In a session's chat, in a window wider than 900 px, the edge between the feed and the
waiting card SHALL be a splitter: dragging it, or ↑ / ↓ on it when focused, SHALL set the
card's height between its least height and the chat's height less the feed's least height
(160 px), and a double click SHALL give the card back the height of its content. Dragging the edge
down past the card's least height SHALL minimize the card.

#### Scenario: Back to the default
- **WHEN** the human double-clicks the edge
- **THEN** the card is as high as its content, at most half the chat

#### Scenario: Dragged to the bottom
- **WHEN** the human drags the edge down past the card's least height
- **THEN** the card is minimized

### Requirement: The card's chosen height is kept, and only a wide chat has the edge

The chosen
height of the card SHALL be kept in the browser, one value for every card of every session's
chat; a chat too short
for it SHALL show the card lower without forgetting the chosen height. Needs you SHALL have no such
edge, nor a window of 900 px or less, nor the phone layout (capability phone-layout),
whatever its width, where the card is at most half the chat's height.

#### Scenario: Made smaller
- **WHEN** the human drags the edge above the card down to 300 px
- **THEN** the card is 300 px high, its report scrolls inside with the footer in view, and
  after a reload, in another session's chat and for the next gate or question the card is
  300 px high

#### Scenario: A narrow window
- **WHEN** the window is 800 px wide
- **THEN** there is no edge above the card, and "Minimize the card" works

### Requirement: The card's text fields grow with their text and stay in view

The waiting card's text fields (an own answer, a question's answer without choices, a Skip's
comment, a gate's comment) SHALL open 1 line high (40 px; in a window of 600 px or less 44 px),
SHALL grow with their text up to 8 lines and then scroll inside, with no resize handle, each as
wide as its question. A gate's comment SHALL have the placeholder "Comment for the next step
(optional)", at 600 px or less "Comment (optional)". On a run's page in Flows it SHALL open 3
lines high.

#### Scenario: A short own answer
- **WHEN** the human picks Other… and types one short line
- **THEN** the field is 1 line high

#### Scenario: A gate's comment
- **WHEN** the human types a comment of 12 lines on a gate's tab
- **THEN** the field is 8 lines high, scrolls inside, and its lower edge is above the buttons'
  row and within the window

### Requirement: A card's field being typed in stays in view

While the human types in one of the card's text fields, its lower edge with the caret SHALL
stay in view within the card: a field in the footer grows in place, and a field in the card's
report (a tab of several questions) brings the report along by as much as it grows past its edge.

#### Scenario: A long own answer
- **WHEN** the human types an answer of 12 lines in the field of Other…
- **THEN** the field is 8 lines high, scrolls inside, and its lower edge with the caret
  is within the card's footer and within the window

#### Scenario: The expanded card
- **WHEN** the card is expanded and the human types an answer of 12 lines
- **THEN** the field is 8 lines high and its lower edge is above the Send row and within
  the window

### Requirement: A ring around an item of the card shows whole

The waiting card SHALL show the ring around one of its items whole, on all four sides: the
focus ring of a gate's comment, of an own answer and of a Skip's comment, and the ring of a
question reached from the feed. Neither the report, the choices' area nor the panel SHALL cut a
ring at rest, while the human types, or after the report scrolled a field into view. The room
for a ring SHALL move nothing: the head, the report and the footer's items SHALL start at the
panel's padding.

#### Scenario: A gate's comment with the focus
- **WHEN** the human clicks into the comment field on a gate's tab
- **THEN** the field's focus ring is whole on the left, the top, the right and the bottom,
  within the card's footer

#### Scenario: A long gate's comment
- **WHEN** the human types a comment of 12 lines on a gate's tab
- **THEN** the field, 8 lines high, has its focus ring whole on all four sides

#### Scenario: An own answer with the focus
- **WHEN** the human picks Other… on a question and its field gets the focus
- **THEN** the field's focus ring is whole on all four sides

#### Scenario: The first question marked
- **WHEN** the human comes to the card's first question from its line in the feed
- **THEN** the question's ring is whole on all four sides, its top too

#### Scenario: A narrow window
- **WHEN** the window is 600 px wide and the comment field on a gate's tab has the focus
- **THEN** the field's focus ring is whole on all four sides

#### Scenario: Nothing moves
- **WHEN** a gate's tab is shown
- **THEN** its question and its comment field start at the same distance from the panel's
  left edge

### Requirement: The card's answer fields take files as the composer does

The waiting card's fields of an own answer (Other…), of a Skip's comment and of a gate's
comment for the next step SHALL each take files as the composer does, wherever the card
or the gate's panel shows (a session's chat, Needs you, a run's page in Flows): a
paperclip at the field's left that opens the file picker, and the attached files as chips
above the text (an image's thumbnail or its type's icon, the crossed-out eye when an
agent cannot read it, the name, the size, × to remove).

#### Scenario: Files with an own answer
- **WHEN** the human picks Other… on #13, attaches `server.log` with the clip and types
  nothing
- **THEN** the question counts as answered and Send sends it with the file

### Requirement: A file pasted or dropped on a card's field is attached to it

Each of the card's answer fields SHALL also attach, as the composer does, a file or a text
longer than a message pasted into it, and files dropped on it, the field's frame the drop
zone while files are dragged over it ("Drop to
attach · up to <n> files, <size> each"). Files dropped in the chat outside the card SHALL go to the composer;
files dropped on the card SHALL never go to the composer.

#### Scenario: A screenshot pasted into a gate's comment
- **WHEN** the human pastes a screenshot into the comment of task/lad-86's gate and
  clicks Reject
- **THEN** the file is uploaded, the gate is answered `reject` with the comment and the
  file, and the tab goes

#### Scenario: A drop on the card
- **WHEN** the human drops a file on the comment of a gate's tab
- **THEN** the file is attached to that comment and the composer gets nothing

#### Scenario: A drop elsewhere in the chat
- **WHEN** the human drops a file on the feed while the card is shown
- **THEN** the file is attached to the composer, as before

### Requirement: A card's field keeps its files within the server's limits

The limits of the card's files SHALL be the server's
(`GET /api/limits`), refused files named at the field. A picked choice SHALL have no field
and take no files. The files of each field SHALL be
kept across the card's tabs and its expanded view until they are sent or removed.

#### Scenario: A choice takes no files
- **WHEN** the human picks the choice "main" on #12
- **THEN** #12 shows no field and no paperclip

### Requirement: Sending a card's answer uploads its files first

Sending
(the tab's Send, a gate's button) SHALL upload every file not uploaded yet, then answer
with their full names; a file whose upload failed SHALL stay red with its reason, nothing
SHALL be answered, and the next Send SHALL retry it. Beside a gate's buttons SHALL stand
"<n> file(s), <size>" while it has files.

#### Scenario: An upload that fails
- **WHEN** one of two files of a gate's comment fails to upload on Approve
- **THEN** the gate stays open, that file's chip is red with the reason, and the next
  Approve uploads only that file

### Requirement: A closed question card shows the reply's files

The reply block of a closed question card ("You · answered", "You · skipped") SHALL show
the files the reply carries as the human's own message does: the images as previews (at
most 240 × 180), then a chip per file; each opens its record in the panel. The human's row
of an answer to a question not in the window SHALL show them the same way, and a skip of
such a question its chips.

#### Scenario: An own answer with a screenshot and a log
- **WHEN** #41 was answered "like this" with a screenshot and `server.log`
- **THEN** its card's reply block shows "like this", the screenshot's preview, and the
  chips of both files

### Requirement: A late answer's line counts its files

The quiet line of an answer given after other rows ("You
answered question #N ↑ · …") SHALL end with "· <n> file(s)" when the reply carries
files.

#### Scenario: A late answer with files
- **WHEN** the human answers #41 with two files after other rows of the chat
- **THEN** the quiet line where it was given ends with "· 2 files"

### Requirement: The card's footer stays in sight and only its context scrolls

An open card's tab SHALL be a head, a report and a footer, in that order. The report (a gate's
note and chips, a question's details, a tab's questions) SHALL be the only part that scrolls, a
focusable region "Context of the card". The footer SHALL always be
whole: the recommendation, a gate's comment or a question's choices and field, the buttons.
Between them SHALL stand the recommendation's splitter, or else a line of `--human` at 35 %.
Needs you has its own requirement.

#### Scenario: A long note
- **WHEN** a gate with a note of 60 lines waits in a window 1440×900
- **THEN** the note scrolls in the report, and the recommendation, the comment field,
  Approve and Reject are in sight without scrolling

#### Scenario: The same at other widths
- **WHEN** the same gate waits at 768 and at 390 px wide
- **THEN** the recommendation, the comment field and the buttons are in sight without
  scrolling the card

### Requirement: The card's question is its head, on one line

The question (a gate's, or a single question's text) SHALL be the card's head: a band of
`--human-head` the frame's width, no border or line under it, never scrolling, its text 15 px
600 on one line cut with "…". A cut head SHALL
have the UI's tooltip with the whole text, on a hover, on the keyboard's focus and on a tap. No
meta (run, step, gate, number) SHALL stand beside it. A tab of several questions SHALL
have no head. The card's panel SHALL be named by its head.

#### Scenario: A question of three lines
- **WHEN** an agent asks one question whose text takes three lines of the head, and the human
  points at the head
- **THEN** the head shows one line ending in "…", the tooltip shows the whole text, and the
  report does not repeat it

#### Scenario: A short question
- **WHEN** the head's text fits on its line
- **THEN** it has no tooltip

#### Scenario: The report scrolled
- **WHEN** a gate's long report is scrolled to its end
- **THEN** the gate's question still stands in the head, with nothing beside it

### Requirement: The report and the recommendation fade while there is more

When the report does not fit, its lower edge SHALL fade out over 22 px, and the recommendation's
text that does not fit SHALL fade over 26 px, each while more stands below what it shows and not
at its end. The fade SHALL be the only sign: no "↓ more", "more" or "less". The text under a fade
SHALL stay in the page for a screen reader, and nothing SHALL fade in a whole card.

#### Scenario: A context cut
- **WHEN** a gate's report does not fit in the card
- **THEN** its lower edge fades and no "↓ more" shows

#### Scenario: Scrolled to the end
- **WHEN** the human scrolls the report to its end, by wheel or by keys with the focus on it
- **THEN** the fade is gone, and it comes back when it scrolls up

### Requirement: A footer taller than its room gives way in order

The card's parts SHALL give up height in this order: the feed and the report down to 56 px, then
the choices' area down to one row, the recommendation's text down to one line, then the field
stops at its height and scrolls inside. The buttons SHALL always be in sight: on a touch screen
with a field of the footer in focus the report SHALL go past 56 px, then the head (a phone:
phone-layout). The feed SHALL have no least height while a card shows, but the edge's bounds
SHALL keep its 160 px.

#### Scenario: Six long choices in a low window
- **WHEN** a question with six long choices waits in a chat 420 px high
- **THEN** the choices' area is at least one row high and scrolls inside, Skip among the
  choices, and Send is in sight

#### Scenario: A field that grew
- **WHEN** the human types 8 lines in a card with no room left above it
- **THEN** the field keeps the height it has, scrolls inside, and the buttons are in sight

### Requirement: A field's placeholder is muted

Every field's placeholder SHALL wear `--muted` at full opacity in both themes, not the browser's
own colour.

#### Scenario: Dark
- **WHEN** a gate waits in the dark theme
- **THEN** the placeholders of its comment and of the composer are `--muted`, and so is an own
  answer's

### Requirement: A single question stands in the footer's choices

A tab of one question SHALL show its choices in the footer as pills of 32 px that wrap,
**Other…** and **Skip** with them and the field they open under them, then **Send answer to
<agent>**. The choices' area SHALL be as high as its content up to 4 rows (about 160 px) on a
window, up to 148 px on a phone, and past that scroll inside with a fade, as a focusable group
named "Choices"; the buttons SHALL stand under it and not scroll. The recommended choice SHALL be
the one picked ahead.

#### Scenario: Four rows
- **WHEN** a question's choices take 4 rows on a window 1440×900
- **THEN** all of them show, with no scrolling

#### Scenario: Six rows
- **WHEN** they take 6 rows
- **THEN** the area is about 160 px high, scrolls inside with a fade at its lower edge, and
  Send stands under it

### Requirement: Several questions of a tab stand in the context

A tab of more than one question SHALL have no head: the numbered questions, each with its
details, recommendation, choices, Other…, Skip and field, SHALL stand in the report on the card's
ground with no block of their own, each after the first under a line of `--human` at 35 % the
frame's width, and the footer SHALL hold Send and "<k> of <n> answered". Send SHALL stay off
until each has an answer.

#### Scenario: Three questions
- **WHEN** the supervisor's tab holds three questions
- **THEN** they scroll in the report under a fade, parted by two lines, and the footer shows
  "Send 3 answers to supervisor" and "0 of 3 answered"

### Requirement: The composer folds while an answer field is open

Only in the phone layout, while a field of the shown tab of the chat's card has the focus and the
card is neither minimized nor expanded, the composer SHALL be a line of 40 px in a dashed
`--line` frame: on a question's tab "Answering question #<id> above · Write to supervisor
instead" (the first question with an open field), on a gate's "Commenting on gate #<id> above".
The composer's text and files SHALL be kept meanwhile. Elsewhere, and in a stopped session, the
composer SHALL not fold.

#### Scenario: Another tab
- **WHEN** on a phone the field of Other… has the focus on the supervisor's tab and the human
  shows a gate's tab
- **THEN** the composer is back

#### Scenario: A computer
- **WHEN** the human opens Other… on a question in a window 1440×900
- **THEN** the composer stays as it was, with its text

### Requirement: Write to supervisor instead keeps the field's draft

A click on "Write to supervisor instead" SHALL close the open fields of the shown tab and bring the
composer back with the focus in it; each field's words and files SHALL be kept and SHALL come back
when the human opens Other… or Skip again. A quote sent to the composer while the composer is
folded (a phone, a field in focus) SHALL do the same. A question without choices keeps its field,
its answer or its skip.

#### Scenario: Other… and back
- **WHEN** on a phone the human opens Other… on question #5, types "keep the worker" and taps
  Write to supervisor instead
- **THEN** the field closes and the composer is back; a tap on Other… shows "keep the
  worker" again

#### Scenario: A quote
- **WHEN** Other… is open and the human quotes a message in reply
- **THEN** the composer is back with the quote and the focus

### Requirement: A Send that is off says why

**Send answer to <agent>** off because an answer is missing SHALL have the tooltip "Choose an
answer first", on a hover, on the keyboard's focus and on a tap. In a stopped session a tab of
questions SHALL say "The session is stopped: resume it to answer." beside it, as a gate does.

#### Scenario: Nothing chosen
- **WHEN** nothing is picked and the human points at Send
- **THEN** the tooltip says "Choose an answer first"

### Requirement: The expanded card covers the chat's area, not the window

An icon button at
the right of the card's tabs in a session's chat (no text; its name and tooltip "Expand the
card") SHALL show the card over the chat's whole area, never over the whole window: the feed and
the composer hidden, the session's head, with the team, and its tabs seen and usable (but on a phone:
capability phone-layout; in a window of 601 to 900 px: the requirement "At 601 to 900 px the
expanded card fills the window under the top bar").

#### Scenario: The session around an expanded card
- **WHEN** the human expands the card in session lad-46's chat
- **THEN** the feed and the composer are hidden, the card fills the chat's width and
  height, and the session's tabs (Activity, Agents, Flows, Artifacts) and the team in the head
  are seen and can be clicked, with no scrim

#### Scenario: Expanded on a phone
- **WHEN** the human expands the card in session lad-46's chat on a phone
- **THEN** the session's tabs and the team row are hidden with the feed and the composer,
  and folding the card shows them again

### Requirement: The height the human gave leaves the footer whole

The height set by the edge SHALL be the whole card's, but its head, the recommendation's splitter
and its footer SHALL never give way to it: a height lower than the card's tabs, head and footer
SHALL show them whole, with the report at its least.

#### Scenario: Lower than the footer
- **WHEN** the human gives the card a height lower than its tabs, head and footer
- **THEN** the tabs, the head and the footer show whole, the report 56 px high

### Requirement: At 601 to 900 px the footer and the composer stay in sight

In a window 601 to 900 px wide outside the phone layout, the chat's card SHALL stand above the
composer at the chat's lower edge, its parts giving way in their order, and its footer and the
composer SHALL lie within the window however long the note and however far the feed is scrolled.
A window too low for both SHALL keep the card's buttons before the composer.

#### Scenario: A low window
- **WHEN** a gate with a long note waits in a window 768×700
- **THEN** the recommendation, the field, Approve, Reject and the composer lie within the window

#### Scenario: A card that grew
- **WHEN** the human drags the recommendation's splitter up and types 8 lines in a window 768×700
  or 768×500, or a question of six choices waits there with its own answer open
- **THEN** the report gives way, and the field and the buttons lie within the window

#### Scenario: The sessions' list opens or closes
- **WHEN** the human opens the sessions' list over the chat in a window 768×700, or closes it
- **THEN** the card and its footer stay where they are

### Requirement: At 601 to 900 px the expanded card fills the window under the top bar

In a window 601 to 900 px wide outside the phone layout, the expanded card SHALL be the window's
height under the top bar, the session strip and the tabs hidden with the feed and the
composer, also after the window narrows or turns, until it folds.

#### Scenario: Expanded
- **WHEN** the human expands a card in a window 768×700 or 768×1024 and turns the wheel
- **THEN** the card stands under the top bar, its footer lies within the window and nothing moves

#### Scenario: The window narrows
- **WHEN** the card is expanded in a window 1440×900 and the window narrows to 768×700
- **THEN** the card stands under the top bar and its footer lies within the window

### Requirement: A gate's tab names its step and who wrote its report

A gate's tab SHALL have the UI's tooltip, on a hover and on the keyboard's focus, of two lines:
"step <state>" and "report by <author>", the author of the note that led to the gate
(`GateInfo.note_by`); a gate with no note SHALL have only the first line. As a button's tooltip
it SHALL not show on a tap. A gate's tab SHALL be at most 220 px wide (170 px in a window of 600
px or less), its run's name cut with "…".

#### Scenario: Hovering a gate's tab
- **WHEN** gate #1 of run ship/x waits at step check after a note of reviewer, and the human
  points at its tab
- **THEN** the tab reads "ship/x 1" and the tooltip "step check" and "report by reviewer"

#### Scenario: A gate with no note
- **WHEN** a gate whose run kept no note waits and the human focuses its tab with Tab
- **THEN** the tooltip has the one line "step <state>"

### Requirement: A gate's documents are one row of chips with their titles

A gate's tab SHALL show the note's artifacts and then the artifacts the gate reads in one row of
chips, an artifact named twice shown once, with no label over them. A chip SHALL show the
artifact's title, its short name when it has none, and no size or path; it SHALL open the
artifact panel as the chat's chips do, in the chat and on Needs you alike. It SHALL keep the
name "Open artifact <full name>" for a screen reader.

#### Scenario: A note's artifact and a read one
- **WHEN** gate #1's note carries `ship/x/review` (no title) and the gate reads `ship/x/plan`
  (title "The plan") and `ship/x/review`
- **THEN** the tab shows the chips "review" and "The plan", once each, and no "It reads" or size

#### Scenario: A chip on Needs you
- **WHEN** the human clicks the chip "The plan" on Needs you
- **THEN** the artifact panel opens over the page, as in the chat

### Requirement: The card's splitters have no tooltip

The edge above the card ("Resize the card") and the recommendation's splitter ("Resize the
recommendation") SHALL have no `title` and no tooltip; each SHALL keep its name as its
aria-label. On a hover, a focus or a drag only the splitter's line and the pointer SHALL change.

#### Scenario: Hovering the edges
- **WHEN** the human points at the edge above the card, then at the recommendation's splitter
- **THEN** no tooltip shows, each line turns `--action` and the pointer is `row-resize`

### Requirement: The recommendation's height is set by a splitter in the chat

In a session's chat, while the shown tab of one item has a given recommendation, a splitter with
the UI's grip SHALL stand between the report and the footer. Dragging it or ↑ / ↓ SHALL set the
recommendation's text from one line (20 px) up to its whole text, taking room from the report
down to 56 px, then from the feed down to 160 px; a double click SHALL give back 4 lines (a
phone: 2). The height SHALL be kept in the browser, one value for every card.

#### Scenario: Where there is none
- **WHEN** a tab has no given recommendation, or the card is on Needs you or a run's page
- **THEN** it has no splitter

#### Scenario: Dragged up
- **WHEN** a gate with a long recommendation waits in the chat and the human drags the splitter
  up by 60 px
- **THEN** the recommendation's text is 60 px higher, the report as much lower, and after a
  reload it is as high

#### Scenario: No recommendation
- **WHEN** a gate with no recommendation waits in the chat
- **THEN** no splitter stands in the card, and the footer has a line of `--human` at 35 % above it

### Requirement: The recommendation's splitter stands only with something to drag

When the recommendation's whole text is a line, nothing to drag, its splitter SHALL not stand,
and the footer SHALL have its line above it. The room the card has SHALL not count. Its grip
SHALL lie over its line.

#### Scenario: A recommendation of a line
- **WHEN** a gate with a recommendation of one line waits in the chat
- **THEN** no splitter stands in the card, and the footer has the line above it

### Requirement: A choice gate's option is picked, then sent

A choice gate's options SHALL be pills above the comment that a click picks and unpicks, the
recommended one picked ahead with its ✓; Send SHALL answer the gate with the one picked and the
comment, and SHALL be off with "Choose an answer first" until one is, so a slip of the pointer
sends nothing. The card SHALL keep the pick across its tabs and its minimizing, as the comment.

#### Scenario: A choice gate
- **WHEN** a choice gate with the options ship and rework waits, the supervisor recommending
  ship, and the human clicks rework
- **THEN** rework is picked and nothing is sent; Send answers the gate `rework`

#### Scenario: The pick kept
- **WHEN** the human picks rework, opens another tab of the card and comes back
- **THEN** rework is still picked, not the recommended ship

### Requirement: A question without choices shows its field at once

A question with no choices that takes a free answer SHALL show its field at once, with the
placeholder "Your answer" and the name "Your answer to: <question>", and no Other…; Skip SHALL
stand beside it. It SHALL count as answered once the field has words or files.

#### Scenario: A free question
- **WHEN** the supervisor asks "What should the welcome e-mail say?" with no choices
- **THEN** its field "Your answer" shows with Skip, and the question counts as answered once the
  human types a line

### Requirement: Skip opens its comment and Send sends it

Skip SHALL be a pill after the choices and Other…, in their style, pressed while it is the
question's pick. It SHALL open the field "Why you skip it (optional)", and the skip SHALL go with
Send, as any answer. A second click SHALL take it back.

#### Scenario: Skipped with a reason
- **WHEN** the human clicks Skip, types "not now" and clicks Send
- **THEN** the question is dismissed with the comment "not now"
