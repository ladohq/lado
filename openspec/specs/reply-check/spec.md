# reply-check Specification

## Purpose
Which turns decide whether the human's message was answered in the chat, so that a turn that failed
is not called a reply.

## Requirements

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
- **THEN** the chat shows "replied only in its terminal" on the message
