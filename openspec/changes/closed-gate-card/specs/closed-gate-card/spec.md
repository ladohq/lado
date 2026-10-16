## ADDED Requirements

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

### Requirement: The server names the event that closed a gate

The UI server SHALL give each closed gate the id of the run's event its closing wrote:
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

### Requirement: An opened closed gate shows its question and answer first

A click on a closed gate's line SHALL open a card that shows the gate's question and its
answer (who answered, the answer, where the run went when the chat knows the move, the
time, and the comment in full), and SHALL fold the note that led to the gate and the
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
