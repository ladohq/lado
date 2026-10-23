## MODIFIED Requirements

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
