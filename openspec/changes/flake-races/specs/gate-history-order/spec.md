## ADDED Requirements

### Requirement: A gate and the event that opened it share one time

When a flow run enters a gate, LADO SHALL write the gate and its `gate_open` event with
the same `created_at`, so that the session's chat, which shows an event before a gate
of equal time, never shows the gate's line above the event that opened it.

#### Scenario: The millisecond turns between the two rows
- **WHEN** a run enters an approval gate and the clock's millisecond changes between
  writing the gate and writing its event
- **THEN** the gate's `created_at` and its `gate_open` event's `created_at` are equal

#### Scenario: The human's move after a gate
- **WHEN** the human approves a gate in the chat
- **THEN** the gate's line stays in the run group of the move that opened it, and the
  last run group holds the human's move without the gate's line
