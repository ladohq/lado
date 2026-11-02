## ADDED Requirements

### Requirement: A busy agent gets its queue with the result of a lado tool

When an agent of any provider calls any tool of LADO's MCP server, LADO SHALL take that
agent's pending messages, whole and in order, mark them `delivered` by the channel
`tool_result`, and add their lines, as a hand-over types them, to the tool's result after
its own content; a tool that fails SHALL carry them in its error text.

#### Scenario: The lines and the state
- **WHEN** a busy agent with two pending messages, one with a body, calls a `lado` tool
- **THEN** the result ends with the two lines in their order, as `runtime.format_messages`
  gives them, and both messages are `delivered` with channel `tool_result` and `sent_at`
  set

#### Scenario: A worker's report during the supervisor's turn
- **WHEN** the supervisor is busy, worker `w1` sends it a report with a body, and the
  supervisor then calls `list_agents`
- **THEN** the result holds the agent list and the line
  `[from w1] <summary> (#<id>, <n> lines: call read_messages)`, and the message is
  `delivered` with channel `tool_result`

#### Scenario: Nothing queued
- **WHEN** a busy agent with no pending message calls `list_agents`
- **THEN** the result is the agent list alone

#### Scenario: A tool that fails
- **WHEN** a busy agent with a pending message calls `read_artifact` with a name that does
  not exist
- **THEN** the error says the artifact is not found and carries the message's line, and
  the message is `delivered`

### Requirement: A message taken by a tool is not handed over again

A message delivered by the channel `tool_result` SHALL NOT be handed over at the agent's
turn's end, typed into its window or failed by the sweep; a message to read among them
SHALL be returned once by `read_messages`.

#### Scenario: The turn's end after a mid-turn delivery
- **WHEN** a busy supervisor got worker `w1`'s report in a tool's result and then ends its
  turn
- **THEN** the turn-end hook hands over nothing for that report, and the supervisor's
  `read_messages` returns its body once

### Requirement: read_messages returns a waiting message at once

`read_messages` SHALL first take the caller's pending messages as any tool call does, so
that a message with a body that waited in the queue is returned and marked `read` in the
same call, and one without a body is in the result's lines.

#### Scenario: Reading in the middle of a turn
- **WHEN** a busy supervisor has worker `w1`'s report with a body pending and calls
  `read_messages`
- **THEN** the call returns the report's body and the report is `read`

### Requirement: A reminder to an agent whose message waits is refused

`send_message(to=X)` by agent A SHALL be refused, with nothing queued, while a message
from X to A waits that A has not received: `pending`, or handed over with a body or
attachments and not read. The error SHALL name that message (`X's message #<id> waits for
you`), carry A's queue's lines as any tool call does, and say to read it with
`read_messages` and send again if it still needs saying. Once A has received it, the same
call SHALL go through. A message to `human` SHALL never be refused so.

#### Scenario: The supervisor reminds a worker whose report waits
- **WHEN** worker `w1`'s report with a body waits pending for the busy supervisor, and the
  supervisor calls `send_message(to="w1", summary="send your report")`
- **THEN** the call is refused, nothing is queued for `w1`, the error names `w1`'s message
  and carries its line, and the report is `delivered`

#### Scenario: Sending again after reading
- **WHEN** the supervisor then calls `read_messages` and sends `w1` the same message again
- **THEN** the message is queued for `w1`

#### Scenario: A message without a body
- **WHEN** worker `w1`'s message without a body waits pending for the busy supervisor and
  the supervisor sends `w1` a message
- **THEN** the call is refused with `w1`'s line, and the supervisor's next send to `w1`
  goes through

#### Scenario: A message to the human
- **WHEN** worker `w1`'s report waits pending for the busy supervisor and the supervisor
  sends a message to `human`
- **THEN** the message to `human` is sent, and the result carries `w1`'s line

### Requirement: The instructions say where mid-turn messages come from

The messaging instructions every agent gets SHALL say that a message that comes during the
agent's turn arrives with the result of its next `lado` tool call. The supervisor's
instructions SHALL say not to wait for a worker inside a turn but to end the turn, and to
call `read_messages` before reminding an agent or telling the human it waits for one.

#### Scenario: A supervisor's instructions
- **WHEN** LADO writes a supervisor's instructions
- **THEN** they hold the line on mid-turn messages and the one on not waiting inside a turn
