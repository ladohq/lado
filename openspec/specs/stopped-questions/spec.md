# stopped-questions Specification

## Purpose
What becomes of the open questions to the human when a session stops: each closes saying
the session stopped, the stop names how many it closes, and the resumed supervisor is told
once of those left unanswered, so that no question is lost without a word.

## Requirements

### Requirement: A question a stop closes says the session stopped

Every stop of a session (`lado stop`, the UI's Stop, `lado update`, the container's stop, a
resume after its tmux went away) SHALL set the session's open questions to the state
`stopped`, and a closed card of that state SHALL read "Closed: the session stopped". A
question whose agent ended or was finished while the session runs SHALL stay `closed`, its
card reading "Closed: the agent left".

#### Scenario: The container stops
- **WHEN** the UI server ends in a container while the supervisor's question #12 is open
- **THEN** #12 has the state `stopped` and its card reads "Closed: the session stopped"

#### Scenario: A worker is finished
- **WHEN** a worker with the open question #13 is finished and the session goes on
- **THEN** #13 has the state `closed` and its card reads "Closed: the agent left"

#### Scenario: A reply to a stopped question
- **WHEN** a tab still sends a reply to #12 after the stop
- **THEN** the call is refused with `question #12 is stopped` and nothing is queued

### Requirement: The resumed supervisor gets the questions a stop closed

A resume SHALL queue for the new supervisor, after its message about the open runs, one
message from LADO listing each `stopped` question of the session not yet told: its id, asker,
text, details and choices, with its attachments, and saying to ask again what is still
needed. With no such question it SHALL queue no such message.

#### Scenario: A worker's and the supervisor's question
- **WHEN** the session stops with the supervisor's #12 and the developer's #13 open, and is
  resumed
- **THEN** the new supervisor gets `2 questions to the human closed unanswered by the stop`,
  whose body names #12 from supervisor and #13 from developer with their texts

#### Scenario: Nothing was open
- **WHEN** a session with no open question is stopped and resumed
- **THEN** the supervisor gets the open-runs message and no message about questions

### Requirement: A stopped question is told once

A resume SHALL NOT list a question whose message the supervisor of an earlier resume received,
and SHALL list again one whose message was dropped.

#### Scenario: A second stop and resume
- **WHEN** the supervisor read the message about #12, and the session is stopped and resumed
  again
- **THEN** the new supervisor gets no message about #12

#### Scenario: A resume that failed
- **WHEN** a resume fails before its supervisor runs, and the next resume succeeds
- **THEN** the supervisor of the next resume gets the message about #12

### Requirement: A stop says how many open questions it closes

`GET /api/sessions/{name}/stop-preview` SHALL answer `questions`, the number of the session's
open questions. Stop's popover SHALL then list `1 open question to you is closed` or `<n>
open questions to you are closed`, after the line of dropped messages, and no such line for
none. `lado stop` SHALL add `; 1 open question closed` or `; <n> open questions closed` to its
`Stopped session` line, after the dropped messages, and nothing for none.

#### Scenario: The popover with two questions
- **WHEN** the human opens Stop session… with two open questions in the session
- **THEN** the popover lists "2 open questions to you are closed"

#### Scenario: lado stop with one question
- **WHEN** `lado stop s` stops a session with one open question and no dropped message
- **THEN** it prints `Stopped session "s"; 1 open question closed.`

#### Scenario: None open
- **WHEN** the session has no open question
- **THEN** neither the popover nor `lado stop` mentions questions
