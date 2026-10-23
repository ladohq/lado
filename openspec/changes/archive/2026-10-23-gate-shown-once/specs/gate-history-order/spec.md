## MODIFIED Requirements

### Requirement: A gate and the event that opened it share one time

When a flow run enters a gate, LADO SHALL write the gate and its `gate_open` event with
the same `created_at`, so that the session's chat, which shows an event before a gate
of equal time, never shows the gate's row above the run's move that led to it.

#### Scenario: The millisecond turns between the two rows
- **WHEN** a run enters an approval gate and the clock's millisecond changes between
  writing the gate and writing its event
- **THEN** the gate's `created_at` and its `gate_open` event's `created_at` are equal

#### Scenario: The human's move after a gate
- **WHEN** the human approves a gate in the chat
- **THEN** the gate's row stays right under the run group of the move that led to it,
  and the last run group holds the human's move without the gate's row

## ADDED Requirements

### Requirement: The gate's opening is no line of its run

The chat SHALL show a flow gate only in the gate's own row: the run's `gate_open` event
SHALL be no line of the run's group, whether the gate is open or closed.

#### Scenario: A gate waits
- **WHEN** a run moves from review to step_ok and opens gate #96 there
- **THEN** the run's group ends with the move "review → step_ok next", the row
  "Gate #96 epic/epic-projects · step_ok waits: <question>" stands right under it, and
  no line of the chat says "waits for you"

#### Scenario: The gate answered
- **WHEN** the human approves gate #96 and the run moves on
- **THEN** the chat shows the folded card "Gate #96 · approve by you" under the group
  that ends with "review → step_ok next", then the group with the human's move, and no
  line with the gate's question outside the card
