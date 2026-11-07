## ADDED Requirements

### Requirement: A delivery a session's end cuts off is refused in plain words

When a message cannot be delivered because its session stopped or its tmux session is gone, LADO
SHALL refuse it with "The session stopped before this message reached <recipient>, so it was not
delivered. Send it again after Resume.", as a 400 at the server, whatever tmux said and however far
the delivery got. A tmux failure of a session that still runs SHALL stay an error.

#### Scenario: The session stops after the queue was taken
- **WHEN** the human sends a message and the session stops between the hand-over and the typing
- **THEN** the server answers 400 with that sentence, not 500, and the message is dropped

#### Scenario: The session stops before the queue is taken
- **WHEN** the session stops after the message was queued and before it was handed over
- **THEN** the refusal is the same sentence, with no list of running agents

#### Scenario: The tmux server ends with the session
- **WHEN** the stopped session was the last of its tmux server, so tmux says there is no server
- **THEN** the refusal is the same sentence

#### Scenario: Other sessions run on the tmux server
- **WHEN** other sessions run on the server, so tmux says it cannot find the session
- **THEN** the refusal is the same sentence

#### Scenario: tmux goes without a stop
- **WHEN** the session's tmux session is gone, the session is not marked stopped, and a message is
  sent
- **THEN** the refusal is the same sentence

#### Scenario: A reply to a question
- **WHEN** the human answers an agent's question and the session stops during the delivery
- **THEN** the refusal is the same sentence

#### Scenario: tmux fails in a running session
- **WHEN** typing fails and the session is not stopped and its tmux session is there
- **THEN** the error is not turned into the refusal

#### Scenario: A stopped agent of a running session
- **WHEN** a message goes to a stopped agent while its session runs
- **THEN** the refusal still names the running agents

### Requirement: The composer keeps a message refused by a stop

A message refused because the session stopped SHALL stay in the composer with its files, and the
refusal SHALL show under it after Resume.

#### Scenario: Resume after the refusal
- **WHEN** a message is refused by a stop and the human resumes the session
- **THEN** the composer holds the text and shows the refusal, and Send sends the text

### Requirement: LADO reaches a session's windows by their exact names

Every tmux call that types into, reads or adds to a session's windows SHALL name the session and
the window exactly, so that a session whose name starts with the same characters is never reached.

#### Scenario: A message of a stopped session
- **WHEN** session `lad` is gone, `lad-1` runs with a window of the same name, and text is typed
  to `lad`
- **THEN** the typing fails with the session not found, and nothing reaches `lad-1`

#### Scenario: A worker of a stopped session
- **WHEN** session `lad` is gone, `lad-1` runs, and a window is added to `lad`
- **THEN** adding it fails, and `lad-1` has no new window

#### Scenario: Reading a window of a stopped session
- **WHEN** session `lad` is gone, `lad-1` runs with a window of the same name, and the window of
  `lad` is read
- **THEN** reading it fails, and the text of `lad-1` is not returned
