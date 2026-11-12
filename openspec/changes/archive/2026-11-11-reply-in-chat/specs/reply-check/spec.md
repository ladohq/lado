## MODIFIED Requirements

### Requirement: A turn that ended on an error decides no reply

At a turn's end with an error, of any provider, LADO SHALL leave the human's messages of that turn
unchecked, so the chat shows no "replied only in its terminal" on them. The next turn that ends without
an error SHALL check them as usual.

#### Scenario: A server's error

- **WHEN** a turn started by the human's message ends on an error
- **THEN** the message has no reply state, and the chat shows the turn's error alone

#### Scenario: The CLI reports the end twice

- **WHEN** an OpenCode or Kilo turn ends on an error, and a second `session.idle` with no error follows
- **THEN** only the first ends the turn, and the message has no reply state

#### Scenario: The next turn replies

- **WHEN** the next turn ends without an error and the agent wrote to the human in it
- **THEN** the message is `replied`

#### Scenario: The next turn does not reply

- **WHEN** the next turn ends without an error and the agent wrote nothing to the human
- **THEN** the agent gets the reminder, and the chat shows "replied only in its terminal" on the
  message only when the turn after the reminder writes nothing to the human either

## ADDED Requirements

### Requirement: Every agent is told the human does not see its terminal

The instructions of the supervisor and of every worker SHALL say, the supervisor's first after its
name: the human follows the session in LADO's UI and does not see the terminal; text outside a tool
call reaches nobody; a message `[from human] …` that needs an answer is answered with
`send_message(to="human")` or `ask_human`; one that needs no answer (thanks, "not now") needs no reply;
only text typed into the window without `[from human]` is answered in the window.

#### Scenario: The supervisor's instructions

- **WHEN** a session starts with any provider
- **THEN** the supervisor's instructions hold the rule right after its name, and no longer the
  sentence "answer text typed straight into your window in this window"

#### Scenario: A worker's instructions

- **WHEN** a worker starts, on its own or for a flow run
- **THEN** its instructions hold the same rule

### Requirement: The human's message says how to answer it

The line LADO types for a message from the human SHALL end with
` (reply with send_message(to="human") or ask_human)`, after its `(#<id>, …: call read_messages)`
part when it has one, for every agent and provider; an answer or dismissal of the agent's question
SHALL get no hint.

#### Scenario: A short message

- **WHEN** the human writes "hello" to the supervisor
- **THEN** the supervisor gets `[from human] hello (reply with send_message(to="human") or ask_human)`

#### Scenario: A message with a body

- **WHEN** the human's message #3 has a summary "hello" and a body of two lines
- **THEN** the line is `[from human] hello (#3, 2 lines: call read_messages) (reply with
  send_message(to="human") or ask_human)`

#### Scenario: An answer to a question

- **WHEN** the human answers the agent's question #5
- **THEN** the line has no hint

### Requirement: An answer left in the terminal gets one reminder

When a turn's end that decides replies finds a message from the human that the agent did not answer in
the chat, LADO SHALL queue the agent one message from `lado`, `your answer to the human's message #<id>
went only to your terminal, which the human does not see. If it needs an answer, use
send_message(to="human") or ask_human; else do nothing.`, and SHALL mark the message `reminded`. A
message SHALL get at most one reminder.

#### Scenario: The answer only in the terminal

- **WHEN** the agent ends a clean turn started by the human's message #7 and wrote nothing to the human
- **THEN** the agent gets one message from `lado` naming #7, and #7 is `reminded`

#### Scenario: No second reminder

- **WHEN** the turn after the reminder for #7 ends and the agent wrote nothing to the human again
- **THEN** no new reminder is queued, and #7 is `missing`

#### Scenario: An answer in the chat

- **WHEN** the agent answered the human's message with `send_message(to="human")` or `ask_human` in
  its turn
- **THEN** no reminder is queued, and the message is `replied`

### Requirement: The verdict on a reminded message waits for the reminder's turn

A `reminded` message SHALL be decided at the end of the first turn without an error that ends after the
reminder was handed over: `replied` when the agent wrote to the human after it got the message, else
`missing`. Until then the API and the chat SHALL show it as having no reply state, so no "replied only
in its terminal" shows.

#### Scenario: The reminder helps

- **WHEN** the agent answers the human with `send_message(to="human")` in the turn the reminder started
- **THEN** the message is `replied`, and the chat never showed "replied only in its terminal" on it

#### Scenario: The agent stays silent

- **WHEN** the reminder's turn ends and the agent wrote nothing to the human
- **THEN** the message is `missing`, and the chat shows "replied only in its terminal" on it

#### Scenario: While the reminder waits

- **WHEN** the message is `reminded` and the reminder is not handed over yet
- **THEN** a turn that ends leaves it `reminded`, and the API gives its reply state as none
