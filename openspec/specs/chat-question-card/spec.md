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

### Requirement: An agent's tab lists its questions with their choices, Other… and Skip

An agent's tab SHALL show its open questions, numbered when it has more than one, each with
its text, its details (Markdown) and its attachments, its choices, **Other…** when the
question takes a free answer, and a text button **Skip question**, never a choice among the
choices. A choice SHALL be picked by a click and unpicked
by a second; Other… SHALL open a field for an own answer, Skip question a field for an
optional comment, and each of the three SHALL exclude the other two.

#### Scenario: A question that takes no own answer
- **WHEN** a question has choices and no free answer
- **THEN** it shows its choices and Skip question, and no Other…

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

A gate's tab SHALL show the gate's question, the note that led to it with its artifacts,
the artifacts it reads, the comment for the next step with its files and the gate's
buttons (Approve / Reject, a choice gate's options, Continue / Cancel run at a loop limit),
which SHALL answer the gate at once through `runs.answer`, with the comment and the files,
as the gate's card did. In a stopped session the buttons SHALL be off and the tab SHALL
say "The session is stopped: resume it to answer."

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

### Requirement: The card keeps the chat in view and expands within its page

The card SHALL be as high as its content. Its title and context together SHALL be at most
40 % of the chat's height unless the human set another height; its footer SHALL not count in
that limit and SHALL not be cut by it. Its context SHALL scroll inside it while its tabs and its
footer stay in view. Where the chat has no height of its own (a window of 900 px or less outside
the phone layout) the limit SHALL be 40 % of the window's height.

#### Scenario: Long questions
- **WHEN** the supervisor's tab holds three questions whose text is longer than half the
  chat
- **THEN** the card's context scrolls inside and "Send 3 answers to supervisor" stays in view

#### Scenario: A short gate
- **WHEN** a gate with a note of two lines waits in a chat 700 px high
- **THEN** the card is as high as its content, with no empty room in it

#### Scenario: A long note in a narrow window
- **WHEN** a gate with a note of 60 lines waits in a chat 800 px wide in a window 900 px high
- **THEN** its title and context are at most 360 px high, and its comment field and Approve
  follow right under them

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
no limit on its context, no fade and no "↓ more"; the page SHALL scroll, the footer right under
the context. Agents waiting in their terminal SHALL stay rows with their reason and "Open
terminal".

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
- **THEN** the card is as high as its content, its title and context at most 40 % of the
  chat

#### Scenario: Dragged to the bottom
- **WHEN** the human drags the edge down past the card's least height
- **THEN** the card is minimized

### Requirement: The card's chosen height is kept, and only a wide chat has the edge

The chosen
height of the card SHALL be kept in the browser, one value for every card of every session's
chat; a chat too short
for it SHALL show the card lower without forgetting the chosen height. Needs you SHALL have no such
edge, nor a window of 900 px or less, nor the phone layout (capability phone-layout),
whatever its width, where the card's title and context are at most 40 % of the chat's height.

#### Scenario: Made smaller
- **WHEN** the human drags the edge above the card down to 230 px
- **THEN** the card is 230 px high, its context scrolls inside with the footer in view, and
  after a reload, in another session's chat and for the next gate or question the card is
  230 px high

#### Scenario: A narrow window
- **WHEN** the window is 800 px wide
- **THEN** there is no edge above the card, and "Minimize the card" works

### Requirement: The card's text fields grow with their text and stay in view

The waiting card's text fields, an own answer (Other…), the comment of a Skip and a gate's
comment for the next step, SHALL open 1 line high (36 px, on a phone 44 px), SHALL grow with their text up to 4 lines,
in the expanded card up to 8, and then scroll inside, and SHALL have no resize handle; each
SHALL be as wide as its question. A gate's comment field on a run's page in Flows SHALL open
3 lines high and grow up to 8.

#### Scenario: A short own answer
- **WHEN** the human picks Other… and types one short line
- **THEN** the field is 1 line high

#### Scenario: A gate's comment
- **WHEN** the human types a comment of 12 lines on a gate's tab
- **THEN** the field is 4 lines high, scrolls inside, and its lower edge is above the Send
  row and within the window

### Requirement: A card's field being typed in stays in view

While the human types in one of the card's text fields, its lower edge with the caret SHALL
stay in view within the card: a field in the footer grows in place, and a field in the card's context (a
tab of several questions) brings the context along by as much as it grows past its edge.

#### Scenario: A long own answer
- **WHEN** the human types an answer of 12 lines in the field of Other…
- **THEN** the field is 4 lines high, scrolls inside, and its lower edge with the caret
  is within the card's footer and within the window

#### Scenario: The expanded card
- **WHEN** the card is expanded and the human types an answer of 12 lines
- **THEN** the field is 8 lines high and its lower edge is above the Send row and within
  the window

### Requirement: A ring around an item of the card shows whole

The waiting card SHALL show the ring around one of its items whole, on all four sides: the
focus ring of a gate's comment, of an own answer and of a Skip's comment, and the ring of a
question reached from the feed. Neither the context, the choices' area nor the panel SHALL cut a
ring at rest, while the human types, or after the context scrolled a field into view. The room
for a ring SHALL move nothing: the title, the context and the footer's items SHALL start at the
panel's padding.

#### Scenario: A gate's comment with the focus
- **WHEN** the human clicks into the comment field on a gate's tab
- **THEN** the field's focus ring is whole on the left, the top, the right and the bottom,
  within the card's footer

#### Scenario: A long gate's comment
- **WHEN** the human types a comment of 12 lines on a gate's tab
- **THEN** the field, 4 lines high, has its focus ring whole on all four sides

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

An open card's tab SHALL be made of a title, a context and a footer, in that order. The context
(a gate's note with its chips, the artifacts it reads, a question's details and attachments)
SHALL be the only part that scrolls, a focusable region named "Context of the card". The footer
SHALL always be whole: the recommendation, then a gate's comment or a question's choices and
field, then the buttons, under a line in `--human` at 30 %. Needs you has its own requirement.

#### Scenario: A long note
- **WHEN** a gate with a note of 60 lines waits in a window 1440×900
- **THEN** the note scrolls in the context, and the recommendation, the comment field,
  Approve and Reject are in sight without scrolling

#### Scenario: The same at other widths
- **WHEN** the same gate waits at 768 and at 390 px wide
- **THEN** the recommendation, the comment field and the buttons are in sight without
  scrolling the card

### Requirement: The card's title is at most two lines

The title (a gate's question, or a single question's text) SHALL not scroll and SHALL be at most
2 lines, cut with "…", with the item's meta at its right (`<run> · <state> · gate #<id>` or
`#<id>`), under it on a phone. When the text is cut, the whole of it SHALL stand first in the
context.

#### Scenario: A question of three lines
- **WHEN** an agent asks one question whose text takes three lines of the title
- **THEN** the title shows two lines ending in "…", and the context starts with the whole
  text

### Requirement: The context says there is more and leads to it

When the context does not fit, its lower edge SHALL fade over 28 px into the card's ground,
with a button "↓ more" of the card's expand action, 24 px high, next in the Tab order. The
fade and the button SHALL go when the context is scrolled to its end, and SHALL not show in
the expanded card.

#### Scenario: A context cut
- **WHEN** the context is cut and the human clicks "↓ more"
- **THEN** the card expands, as by "Expand the card"

#### Scenario: Scrolled to the end
- **WHEN** the human scrolls the context to its end, by wheel or by keys with the focus on it
- **THEN** the fade and "↓ more" are gone, and they come back when it scrolls up

### Requirement: A footer taller than its room gives way in order

The card's parts SHALL give up height in this order: the feed and the context down to 0, the
title down to 0, then the choices' area down to one row, the opened recommendation down to
one line, then the field stops at its height and scrolls inside. The buttons SHALL always be
in sight. A phone's field in focus SHALL take the choices' area out at once (capability
phone-layout). The chat's feed SHALL have no least height while a card shows, but the edge's
bounds SHALL still keep its 160 px.

#### Scenario: Six long choices in a low window
- **WHEN** a question with six long choices waits in a chat 420 px high
- **THEN** the choices' area is at least one row high and scrolls inside, and Send and Skip
  question are in sight

#### Scenario: A field that grew
- **WHEN** the human types 4 lines in a card with no room left above it
- **THEN** the field keeps the height it has, scrolls inside, and the buttons are in sight

### Requirement: A window that scrolls keeps the footer in sight

In a window of 900 px or less outside the phone layout, which scrolls as a page, the chat's card
SHALL stick to the window's lower edge and be at most the room from the chat's top down, its
parts giving way in their order; never less than a footer's least height or half the window,
which the page's scroll then brings up. The composer past the window's edge is LAD-193's.

#### Scenario: A low window
- **WHEN** a gate with a long note waits in a window 768×700
- **THEN** the recommendation, the field, Approve and Reject lie within the window at the page's
  top and at its end

#### Scenario: A card that grew
- **WHEN** the human opens the recommendation and types 4 lines in a window 768×700, 768×500 or
  768×420, or a question of six choices waits there with its own answer open
- **THEN** the context gives way, and the field and the buttons lie within the window at the
  page's top

#### Scenario: The chat low on the page
- **WHEN** the sessions' list stands open over the chat in a window 768×700
- **THEN** the card keeps half the window, and the page's scroll brings its footer into it

#### Scenario: The sessions' list opens or closes
- **WHEN** the human opens the sessions' list over the chat in a window 768×700, or closes it
- **THEN** the card takes the room as it is at once: its footer stays in sight, and closed, the
  card has its height back

### Requirement: In a window that scrolls the expanded card holds the page

In a window of 900 px or less outside the phone layout, the expanded card SHALL be the window's
height under the top bar, also after the window narrows or turns, and the page SHALL not scroll
until it folds.

#### Scenario: Expanded
- **WHEN** the human expands a card in a window 768×700 or 768×1024 and turns the wheel
- **THEN** the card stands under the top bar and its footer lies within the window

#### Scenario: The window narrows
- **WHEN** the card is expanded in a window 1440×900 and the window narrows to 768×700
- **THEN** the card stands under the top bar and its footer lies within the window

### Requirement: A field's placeholder is muted

Every field's placeholder SHALL wear `--muted` at full opacity in both themes, not the browser's
own colour.

#### Scenario: Dark
- **WHEN** a gate waits in the dark theme
- **THEN** the placeholders of its comment and of the composer are `--muted`, and so is an own
  answer's

### Requirement: A single question stands in the footer's choices

A tab of one question SHALL show its choices in the footer as chips of 32 px that wrap,
**Other…** with them and the field it opens under them, then **Send answer to <agent>** and
Skip question beside it. The choices' area SHALL be as high as its content up to 4 rows
(about 160 px) on a window, up to 148 px on a phone, and past that scroll inside with a fade,
as a focusable group named "Choices"; the buttons SHALL stand under it and not scroll.

#### Scenario: Four rows
- **WHEN** a question's choices take 4 rows on a window 1440×900
- **THEN** all of them show, with no scrolling

#### Scenario: Six rows
- **WHEN** they take 6 rows
- **THEN** the area is about 160 px high, scrolls inside with a fade at its lower edge, and
  Send stands under it

### Requirement: Several questions of a tab stand in the context

A tab of more than one question SHALL have no title: the numbered questions, each with its
details, recommendation, choices, Skip question and field, SHALL stand in the context, and the
footer SHALL hold Send and "<k> of <n> answered". Send SHALL stay off until each has an
answer.

#### Scenario: Three questions
- **WHEN** the supervisor's tab holds three questions
- **THEN** they scroll in the context under a fade, and the footer shows "Send 3 answers to
  supervisor" and "0 of 3 answered"

### Requirement: Skip question opens its comment and Send sends it

Skip question SHALL be a text button in `--action` with no frame, pressed while it is the
question's pick. It SHALL open the field "Why you skip it (optional)", and the skip SHALL go
with Send, as any answer. A second click SHALL take it back.

#### Scenario: Skipped with a reason
- **WHEN** the human clicks Skip question, types "not now" and clicks Send
- **THEN** the question is dismissed with the comment "not now"

### Requirement: The composer folds while an answer field is open

While the shown tab of the chat's card has a field of Other… or of Skip question open, and the
card is neither minimized nor expanded, the composer SHALL be replaced by a line of 40 px in a
dashed `--line` frame: "Answering question #<id> above · Write to supervisor instead", naming
the first such question. The composer's own text and files SHALL be kept while it is folded. In
a stopped session the composer SHALL not fold.

#### Scenario: Another tab
- **WHEN** Other… is open on the supervisor's tab and the human shows a gate's tab
- **THEN** the composer is back, and it folds again when they return to the tab

### Requirement: Write to supervisor instead keeps the field's draft

A click on "Write to supervisor instead" SHALL close the open fields of the shown tab and bring the
composer back with the focus in it; each field's words and files SHALL be kept and SHALL come back
when the human opens Other… or Skip question again. A quote sent to the composer SHALL do the same.

#### Scenario: Other… and back
- **WHEN** the human opens Other… on question #5, types "keep the worker" and clicks Write to
  supervisor instead
- **THEN** the field closes and the composer is back; a click on Other… shows "keep the
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
the composer hidden, the session's head, tabs and team row seen and usable (but on a phone:
capability phone-layout).

#### Scenario: The session around an expanded card
- **WHEN** the human expands the card in session lad-46's chat
- **THEN** the feed and the composer are hidden, the card fills the chat's width and
  height, and the session's tabs (Activity, Agents, Flows, Artifacts) and the team row are
  seen and can be clicked, with no scrim

#### Scenario: Expanded on a phone
- **WHEN** the human expands the card in session lad-46's chat on a phone
- **THEN** the session's tabs and the team row are hidden with the feed and the composer,
  and folding the card shows them again

### Requirement: The height the human gave leaves the footer whole

The height set by the edge SHALL be the whole card's, but its footer SHALL never give way to it:
a height lower than the card's tabs and footer SHALL show them whole, with no title or context.

#### Scenario: Lower than the footer
- **WHEN** the human gives the card a height lower than its tabs and footer
- **THEN** the tabs and the footer show whole, with no title or context
