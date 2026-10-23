# closed-gate-card Specification

## Purpose
How the chat shows a flow gate once it is closed: the answer's comment once, under the
run's move it made; the closed gate as a folded card that opens to its question and
answer first, keeping the event that closed it; and the human's move on the human's
ground.

## Requirements

### Requirement: The answer's comment shows once in the chat

The chat SHALL show the comment given with a gate's answer in one place: under the run's
move that the answer made, where it was given. The closed gate's line, where the gate
opened, SHALL show its title and time without the comment, whoever closed the gate.

#### Scenario: The human rejects with a comment
- **WHEN** the human rejects a gate with a comment of two lines and nothing else comes
  into the chat between the gate's opening and the answer
- **THEN** the chat shows the comment once, under the move "You <state> → <state>
  rejected", and the line "Gate #<id> · <run> · <state>: reject by human" has no comment
  under it

#### Scenario: The same gate answered twice
- **WHEN** the human rejects a run's design_ok gate with one comment, and later approves
  its next design_ok gate with another
- **THEN** each move shows the comment of its own gate, and each opened gate's card
  names its own move's target state

#### Scenario: A gate closed otherwise
- **WHEN** the supervisor cancels a run whose gate is open, with a reason
- **THEN** the closed gate's line says "cancelled by supervisor" without the reason
  under it, and the reason shows on the cancel's line of the run

### Requirement: A closed gate keeps the event that closed it

LADO SHALL keep with each closed gate, in the transaction that closes it, the id of the
run's event its closing wrote, and the UI server SHALL give it with the gate:
the human's move for an answer, the `flow_set` event for `lado flow-set`, the
`flow_cancel` event for a run's or a loop limit's cancel; an open gate SHALL have none.
The chat SHALL link a gate's comment and its card to the move by that id alone.

#### Scenario: An answer's move
- **WHEN** the human approves a gate and the run moves on
- **THEN** the gate's `closed_by_event` is the id of the `flow` event of `human` that
  moved the run from the gate's state

#### Scenario: A cancel
- **WHEN** the supervisor cancels a run whose gate is open
- **THEN** the gate's `closed_by_event` is the id of the run's `flow_cancel` event

#### Scenario: Another run writes in between
- **WHEN** two runs of a session close their gates one after the other
- **THEN** each gate's `closed_by_event` is an event of its own run

#### Scenario: A gate closed before the upgrade
- **WHEN** a lado.db of the version before this change, with gates closed by an answer,
  by `lado flow-set` and by a cancel, is migrated
- **THEN** each of those gates has the id of its closing's event, and an open gate has
  none

### Requirement: A closed gate is a folded card that says it opens

The chat SHALL show a closed gate as one folded card: a chevron that turns when it
opens, the gate's flag, "Gate #<id>", its run and state, the answer as a chip coloured by
the run's direction when the move is known, who answered ("by you" for the human) and the
time, last. The whole card SHALL open and close on a click and on Enter or Space, and
SHALL keep the accessible name "Gate #<id> · <run> · <state>: <answer> by <who>".

#### Scenario: A rejected gate, folded
- **WHEN** the human rejected gate #387 of task/lad-83 at merge_ok and the run went back
  to build
- **THEN** the chat shows a card with a chevron pointing down, "Gate #387 task/lad-83 ·
  merge_ok", an orange chip "reject" with the return mark, "by you" and the time

#### Scenario: Opened from the keyboard
- **WHEN** the human focuses the folded card and presses Enter
- **THEN** the card opens down in the same frame and its chevron points up

### Requirement: The human's move stands on the human's ground

In a run's group, the chat SHALL show each line of the human's own (an answer's move, a
`lado flow-set`), with the answer's comment under it, on the ground of the human's own
messages, and the agents' lines without it.

#### Scenario: The move after an answer
- **WHEN** the human rejects a gate with a comment
- **THEN** the line "You <state> → <state> rejected" and the comment under it stand on
  the human's ground, and the agents' lines of the same group do not

### Requirement: An opened closed gate shows its question and answer first

A click on a closed gate's card SHALL open it to show the gate's question and its
answer on the human's ground (who answered, the answer, where the run went when the chat
knows the move, the time, and the comment in full), and SHALL fold the note that led to the gate and the
supervisor's recommendation into one line each, which open on a click. The note opened
SHALL show at most 6 lines of its body with Show more, and its artifacts.

#### Scenario: A long note
- **WHEN** the human opens the line of a gate whose note has a body of 30 lines and two
  artifacts
- **THEN** the card shows the question, the answer with its comment, a line "Note" with
  the note's summary and "2 artifacts", and no line of the note's body; a click on that
  line shows 6 lines of the body, Show more and the two artifacts

#### Scenario: The recommendation folded
- **WHEN** the human opens the line of a gate whose supervisor recommended Approve and
  the human rejected it
- **THEN** the card shows a line "Supervisor" that says "recommended Approve · you
  answered otherwise" and not the recommendation's text, until a click on the line

#### Scenario: The answer agreed
- **WHEN** the supervisor recommended Approve and the human approved
- **THEN** the line "Supervisor" says "recommended Approve · you agreed"

#### Scenario: Nothing to fold
- **WHEN** the human opens the line of a gate with no note and no recommendation
- **THEN** the card shows the question and the answer only, with no folded line

#### Scenario: Closed by an agent
- **WHEN** the human opens the line of a gate the supervisor closed by cancelling its run
- **THEN** the answer shows the supervisor as who closed it, "cancelled" and the reason

### Requirement: The answer's files show with its comment

The files the human attached to a gate's answer (`answer_attachments`) SHALL show under
the run's move that the answer made, after its comment, as the human's own message shows
its files: the images as previews (at most 240 × 180), then a chip per file. The opened
closed gate's card SHALL show them as chips only, in its answer block after the comment.
The closed gate's folded line SHALL NOT show them.

#### Scenario: Reject with a screenshot and a log
- **WHEN** the human rejected task/lad-86's design_ok gate with a comment, a screenshot
  and `server.log`
- **THEN** under the move "You … reject" stand the comment, the screenshot's preview and
  the chips of both files, and the opened gate's card shows the comment and the two chips
  without a preview

#### Scenario: Files without a comment
- **WHEN** the human approved a gate with one file and no comment
- **THEN** under the move stands that file's chip, with no comment
