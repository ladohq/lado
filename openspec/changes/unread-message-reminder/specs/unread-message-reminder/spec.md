## Purpose
That an agent which ended its turn without reading the text of a message it got is told so once, so a weak model does not lose a request it never read.

## ADDED Requirements

### Requirement: A text left unread gets one reminder

At the end of an agent's turn that ended without an error, of any provider, LADO SHALL queue the agent one message from `lado`, `you have not read message #<id> from <sender>: call read_messages to get its text; if it asks nothing of you, do nothing.`, naming each message to that agent that is `delivered`, has a body or artifacts, is not `read` and was never reminded, and SHALL mark each named one reminded; with none, nothing.

#### Scenario: The agent answers without reading

- **WHEN** w1 got `[from supervisor] Thanks, one last note for you (#3, 1 line: call read_messages)`, called no `read_messages` and ended a clean turn
- **THEN** w1 gets one message from `lado`, `you have not read message #3 from supervisor: call read_messages to get its text; if it asks nothing of you, do nothing.`, and #3 is reminded

#### Scenario: Two texts unread

- **WHEN** the supervisor ends a clean turn with #3 from w1 and #5 from w2 delivered and unread, both with a body
- **THEN** it gets one message from `lado` naming `#3 from w1` and `#5 from w2`

#### Scenario: The agent read it

- **WHEN** w1 called `read_messages` in the turn and then ended it
- **THEN** no reminder is queued

#### Scenario: A line with nothing to read

- **WHEN** w1 ended a clean turn after a message with no body and no artifacts
- **THEN** no reminder is queued

#### Scenario: Attached artifacts only

- **WHEN** w1 ended a clean turn after `[from w2] the report (#4, 1 artifact: call read_messages)` without calling `read_messages`
- **THEN** w1 gets the reminder naming `#4 from w2`

### Requirement: A message is reminded at most once

A message SHALL get at most one reminder of its unread text, whatever the turns after it do; a message not yet confirmed as delivered (`pending` or `sent`) SHALL NOT be reminded at that turn's end.

#### Scenario: The reminder is ignored too

- **WHEN** w1 got the reminder for #3, ended the turn the reminder started without `read_messages`, and ends further turns so
- **THEN** no second reminder for #3 is queued

#### Scenario: A message handed over at this turn's end

- **WHEN** a message with a body is handed over to w1 at the end of its turn, in the hook's output or typed in
- **THEN** that end queues no reminder for it; the end of the turn that got it checks it

### Requirement: A turn that ended on an error reminds of nothing

At a turn's end with an error, LADO SHALL queue no reminder of an unread text and SHALL mark nothing reminded; the next turn that ends without an error SHALL check the messages as usual.

#### Scenario: A provider's error

- **WHEN** w1's turn ends on a 429 with #3 delivered and unread
- **THEN** no reminder is queued and #3 is not reminded; at the next clean turn's end, if #3 is still unread, w1 gets the reminder

### Requirement: Texts left unread before the update are not reminded

The schema migration that brings the mark SHALL mark every message that exists then as reminded, so an agent resumed after the update gets no reminder of a message it left unread before it.

#### Scenario: An old unread report

- **WHEN** the supervisor's report #9 from w1 was left unread under 0.46 and the session is resumed under 0.47
- **THEN** the supervisor's first clean turn's end queues no reminder for #9
