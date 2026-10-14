# turn-end-hand-over Specification

## Purpose
How an agent's queue is handed over at the end of its turn (AGENTS.md, How agents talk):
the hook makes the agent idle and takes its queue in one transaction, so the session loop's
sweep never sees the agent idle with that queue and never types the hook's batch in.

## Requirements

### Requirement: A turn's end takes the queue in the transaction that makes the agent idle

At a turn's end, and at every other switch of an agent to idle or background by its hook,
LADO SHALL set the status and take the agent's pending queue in one write transaction,
by the channel the hook delivers through (`hook_output` when the provider can carry the
queue on in the turn-end hook's output and its CLI does not ignore that output, else
`typed`). No other process (the session loop's sweep, a sender) SHALL see the agent idle
or background with a queue that this hook is about to take. A sender SHALL still queue
first and take the queue of an agent that takes input second, so a message queued at
any time is handed over by exactly one of them. With an empty queue the transaction
SHALL leave the agent idle or background, with its `status` event, as before.

#### Scenario: The session loop sweeps during a turn's end
- **WHEN** an agent of a provider that delivers on turn end ends its turn with one
  message pending, and the session loop sweeps the agent at that moment
- **THEN** the message is handed over by the hook's output with channel `hook_output`
  and one attempt, and is never typed into the agent's window

#### Scenario: A turn's end with nothing queued
- **WHEN** an agent ends its turn with no message pending
- **THEN** it is idle, a `status` event records it, and the hook prints nothing

#### Scenario: A message sent right after the turn's end
- **WHEN** a message is sent to the agent after its turn-end hook's transaction
- **THEN** the sender types it in (the agent is idle) and it is handed over exactly once
