## ADDED Requirements

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

### Requirement: The card keeps the chat in view and expands to the window

The card SHALL be at most half the chat's height; its list of questions SHALL scroll inside
it while its tabs and its Send row stay in view. An icon button at the right of its tabs
(no text; its name and tooltip "Expand the card") SHALL show the card over the whole window,
the rest dimmed; there an icon button ("Collapse the card") or Esc SHALL bring it back, and
it SHALL come back by itself when nothing waits any more.

#### Scenario: Long questions
- **WHEN** the supervisor's tab holds three questions whose text is longer than half the
  chat
- **THEN** the card's list scrolls inside and "Send 3 answers to supervisor" stays in view

#### Scenario: Expanded and back
- **WHEN** the human clicks the expand icon, then presses Esc
- **THEN** the card covers the window, then stands above the composer again

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
answered in place. Agents waiting in their terminal SHALL stay rows with their reason and
"Open terminal".

#### Scenario: Two sessions
- **WHEN** lad-28 has a question and a gate open and docs-site a question
- **THEN** Needs you shows two cards, one per session, each with its own tabs
