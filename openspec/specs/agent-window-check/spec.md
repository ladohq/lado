# agent-window-check Specification

## Purpose
How the session loop tells an agent whose window is not made yet from one whose window is
gone: the mark of when an agent's window opened, the two looks that end an agent whose
window closed without a session-end hook, and the deadline of a spawn that died before
its window (`runtime.check_windows`, docs/design/agents.md).

## Requirements

### Requirement: The window check waits for an agent's window to open

LADO SHALL mark when an agent's window opened, right after tmux made it (a worker's
spawn, and a session's start or resume for its supervisor). The session loop's window
check SHALL leave an agent alone while its window has not opened, however long its spawn
takes up to the deadline of a dead spawn, and SHALL end an agent with "its window closed
without a session-end hook" only when its window, once opened, is missing in two looks
in a row.

#### Scenario: A spawn that stalls before its window
- **WHEN** a worker's row is written and its spawn stalls 1 s before `tmux new-window`,
  while the session loop looks every 0.25 s
- **THEN** no look ends it; once its window opens it starts, gets its task and has no
  `ended` event

#### Scenario: A window gone after it opened
- **WHEN** an agent's window opened and is then missing in two looks in a row
- **THEN** the agent is stopped with the reason "its window closed without a session-end
  hook", its undelivered messages are dropped and the supervisor is told the way out

#### Scenario: A window back in the next look
- **WHEN** an agent's window opened, one look misses it and the next one lists it
- **THEN** nothing is ended

### Requirement: A spawn that died before its window ends its agent

When an agent's window has not opened 60 s after its row was written (the process that
spawned it died), the session loop's window check SHALL end the agent with the reason
"its start ended before its window opened", through the same transition as any other end
of an agent.

#### Scenario: The spawning process killed
- **WHEN** an agent's row has been in lado.db for more than 60 s with no window opened
  and no window listed
- **THEN** the agent is stopped with the reason "its start ended before its window
  opened", and the supervisor is told the way out

#### Scenario: Agents of an older LADO
- **WHEN** lado.db is upgraded to the schema with the window mark while a session's
  agents run
- **THEN** their windows count as opened, and the window check treats them as before
