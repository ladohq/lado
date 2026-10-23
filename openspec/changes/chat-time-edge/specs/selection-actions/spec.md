## MODIFIED Requirements

### Requirement: Messages have a Copy message button

Each message of the session's chat and of an agent's page, each closed question of the
chat and each answer of the human's to a question in the chat SHALL have an icon button
Copy message that copies its Markdown text: for the human's message its text, for an
agent's message its summary (when the chat shows it) and its body separated by a blank
line, for a question its summary and its body separated by a blank line, for the human's
answer its text (the choice or the own words) and its comment separated by a blank line.
An answer with neither (files only, a skip without a comment) SHALL have none. In the
chat the button SHALL stand right before the time of its row's head (of the reply block,
in a question's card), or at a continued row's top right.

#### Scenario: A message's text
- **WHEN** the human copies the analyst's message "Раунд 1" whose body is "1. Какие
  действия?"
- **THEN** the clipboard holds "Раунд 1", an empty line and "1. Какие действия?"

#### Scenario: A question's text
- **WHEN** the human copies the analyst's closed question "Где кнопка?" whose body is
  "Сейчас она только у сообщений."
- **THEN** the clipboard holds "Где кнопка?", an empty line and "Сейчас она только у
  сообщений."

#### Scenario: The human's answer
- **WHEN** the human answered a question with the choice "later" and the comment "after
  the tag", and copies the answer in the question's card
- **THEN** the clipboard holds "later", an empty line and "after the tag"

#### Scenario: Beside the time
- **WHEN** the pointer is over the supervisor's message
- **THEN** Copy message shows right before the message's time, and no button stands after
  the time
