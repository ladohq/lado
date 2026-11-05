## ADDED Requirements

### Requirement: The card's footer stays in sight and only its context scrolls

An open card's tab SHALL be made of a title, a context and a footer, in that order. The context
(a gate's note with its chips, the artifacts it reads, a question's details and attachments)
SHALL be the only part that scrolls, a focusable region named "Context of the card". The footer
SHALL always be whole: the recommendation, then a gate's comment or a question's choices and
field, then the buttons, under a line in `--human` at 30 %. This SHALL hold in a session's chat
and on Needs you.

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

### Requirement: In a window that scrolls the expanded card holds the page

In a window of 900 px or less outside the phone layout, the expanded card SHALL be the window's
height under the top bar, on Needs you too, also after the window narrows or turns, and the page
SHALL not scroll until it folds.

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

## MODIFIED Requirements

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

### Requirement: The card keeps the chat in view and expands within its page

The card SHALL be as high as its content. Its title and context together SHALL be at most
40 % of the chat's height unless the human set another height (requirement "The human can
resize the card in the chat"); its footer SHALL not count in that limit and SHALL not be cut
by it. Its context SHALL scroll inside it while its tabs and its footer stay in view. Where
the chat has no height of its own (Needs you, a window of 900 px or less outside the phone
layout) the limit SHALL be 40 % of the window's height. In the phone layout held sideways (capability phone-layout) the team
row SHALL not be shown, expanded or not.

#### Scenario: Long questions
- **WHEN** the supervisor's tab holds three questions whose text is longer than half the
  chat
- **THEN** the card's context scrolls inside and "Send 3 answers to supervisor" stays in view

#### Scenario: A short gate
- **WHEN** a gate with a note of two lines waits in a chat 700 px high
- **THEN** the card is as high as its content, with no empty room in it

#### Scenario: A long note on Needs you
- **WHEN** a gate with a note of 60 lines waits on Needs you in a window 900 px high
- **THEN** its title and context are at most 360 px high, and its comment field and Approve
  follow right under them

### Requirement: The human can resize the card in the chat

In a session's chat, in a window wider than 900 px, the edge between the feed and the
waiting card SHALL be a splitter: dragging it, or ↑ / ↓ on it when focused, SHALL set the
card's height between its least height and the chat's height less the feed's least height
(160 px), and a double click SHALL give the card back the height of its content. Dragging the edge
down past the card's least height SHALL minimize the card. The height set SHALL be the whole
card's, but its footer SHALL never give way to it: a height lower than the card's tabs and
footer shows them whole, with no title or context.

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

The waiting card SHALL show the ring drawn around one of its items whole, on all four
sides: the focus ring of a gate's comment for the next step, of an own answer and of a
Skip's comment, and the ring of a question the human came to from the feed. Neither the
card's context, its choices' area nor the panel around them SHALL cut a ring at rest, while
the human types, or after the context scrolled a field into view. The room for a ring SHALL
move nothing: the title, the context and the footer's items SHALL start at the panel's
padding.

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
