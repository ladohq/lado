## ADDED Requirements

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
sends nothing.

#### Scenario: A choice gate
- **WHEN** a choice gate with the options ship and rework waits, the supervisor recommending
  ship, and the human clicks rework
- **THEN** rework is picked and nothing is sent; Send answers the gate `rework`

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

## RENAMED Requirements

- FROM: `### Requirement: The card's title is at most two lines`
- TO: `### Requirement: The card's question is its head, on one line`
- FROM: `### Requirement: The context says there is more and leads to it`
- TO: `### Requirement: The report and the recommendation fade while there is more`

## MODIFIED Requirements

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

### Requirement: An agent's tab lists its questions with their choices, Other… and Skip

An agent's tab SHALL show its open questions, numbered when it has more than one, each with
its text, its details (Markdown) and its attachments, its choices, **Other…** when the
question takes a free answer and has choices, and a pill **Skip** after them. A choice SHALL be
picked by a click and unpicked by a second; Other… SHALL open a field for an own answer, Skip a
field for an optional comment, and each of the three SHALL exclude the other two.

#### Scenario: A question that takes no own answer
- **WHEN** a question has choices and no free answer
- **THEN** it shows its choices and Skip, and no Other…

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

## REMOVED Requirements

### Requirement: Skip question opens its comment and Send sends it
**Reason**: Skip is a pill among the choices again, as in 0.44 (LAD-266): the text button beside
Send added a control of its own to the footer.
**Migration**: "Skip opens its comment and Send sends it".
