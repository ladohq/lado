## MODIFIED Requirements

### Requirement: The New session window takes a first message

The New session window SHALL show, for every place, a visible field **Task** of three lines
with the placeholder `What should the team do?` and an info button whose text is `The team
gets this as its first message and answers in the chat. You can leave it empty.`; the Resume
window SHALL show the same field as **Message**. Neither SHALL be folded.

#### Scenario: Folded by default
- **WHEN** the human opens the New session window
- **THEN** the Task field shows, unfolded, under Where

#### Scenario: Folded with text
- **WHEN** the human types two lines in Task
- **THEN** the field shows both lines, and no folded row stands for it

### Requirement: The New session window sends the first message as prompt

The New session window SHALL send Task's text (the Resume window, Message's) as `prompt` of
`POST /api/sessions` or `POST /api/sessions/{name}/resume`, and no `prompt` when the field
holds only white space. A text longer than `Limits.max_message` SHALL show `<n> characters,
the limit is <limit>` under the field and keep the start button off.

#### Scenario: A first message sent
- **WHEN** the human types "Take LAD-19" in Task and presses the start button
- **THEN** the request carries `prompt: "Take LAD-19"`, and the session's Activity shows
  the message as the human's

#### Scenario: Over the limit
- **WHEN** the field holds 8001 characters
- **THEN** the note says `8001 characters, the limit is 8000`, the start button is off and
  the footer reads `To start: shorten the task`

#### Scenario: Resume with a first message
- **WHEN** the human resumes a stopped session from the Resume window with a Message
- **THEN** the resume request carries `prompt`, and the resumed supervisor gets it after
  LADO's `session resumed` message

#### Scenario: Clone and start with a first message
- **WHEN** the human clones from a URL with a task
- **THEN** the start after the clone carries the same `prompt`
