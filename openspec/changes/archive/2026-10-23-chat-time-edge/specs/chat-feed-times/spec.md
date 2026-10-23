## ADDED Requirements

### Requirement: Every time on the right of a chat row ends on one edge

The session's chat SHALL end every time that stands on the right of its row (a head's, a
run's event line's, a closed gate's card's, a quiet line's) on one vertical line, the right
edge of the text column. No button and no chevron SHALL stand to the right of such a time,
and showing or hiding a button SHALL NOT move it.

#### Scenario: Rows of every kind
- **WHEN** the chat shows the supervisor's message, the analyst's closed question, the
  human's answer row, a run's group with the developer's move and the human's own move, a
  closed gate, an open gate's line and a late reply's line
- **THEN** the right edges of their times are equal within 1 px, in a wide chat and in a
  phone's chat

#### Scenario: The pointer over a message
- **WHEN** the human moves the pointer over the supervisor's message and Copy message
  appears
- **THEN** the message's time stays where it was, on the same edge as the run lines' times

#### Scenario: Times not on the edge
- **WHEN** a row continues a group, or a card holds a time of its own (the reply block of
  a question's card, an opened gate's answer)
- **THEN** the continued row's time stays in the avatar's column and the card's time ends
  on the card's own padding
