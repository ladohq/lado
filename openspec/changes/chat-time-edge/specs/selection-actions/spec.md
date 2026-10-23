## MODIFIED Requirements

### Requirement: Messages have a Copy message button

Each message of the session's chat and of an agent's page SHALL
have an icon button Copy message in its head that copies the message's Markdown text: for
the human's message its text, for an agent's message its summary (when the chat shows it)
and its body separated by a blank line. In the chat the button SHALL stand right before
the head's time, or at a continued row's top right.

#### Scenario: A message's text
- **WHEN** the human copies the analyst's message "Раунд 1" whose body is "1. Какие
  действия?"
- **THEN** the clipboard holds "Раунд 1", an empty line and "1. Какие действия?"

#### Scenario: Beside the time
- **WHEN** the pointer is over the supervisor's message
- **THEN** Copy message shows right before the message's time, and no button stands after
  the time

### Requirement: Code blocks and messages have copy buttons shown on hover

Copy code and Copy message SHALL say "Copied" for 2 seconds after a copy.
With a pointer that can hover, both SHALL be hidden until the pointer is over the code
block or the message, or the keyboard's focus is on the button. On a touch screen Copy
code SHALL always be shown and Copy message SHALL NOT be shown.

#### Scenario: Hidden without the pointer
- **WHEN** the pointer is not over a message
- **THEN** its head shows no Copy message button, and moving the pointer over the message
  shows it

#### Scenario: A touch screen
- **WHEN** the chat is shown on a touch screen
- **THEN** every code block shows Copy code without a hover, no message shows Copy
  message, and each message's time stands on the same edge as the run lines' times
