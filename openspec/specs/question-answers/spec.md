# question-answers Specification

## Purpose
The human's replies to an agent's questions (`ask_human`) as the core takes them: several
replies to one agent at once, from the web UI's waiting card, handed over in one batch.

## Requirements

### Requirement: The human's replies to an agent's questions are handed over together

The core SHALL take the human's replies to several open questions of one agent in one call
(`runtime.answer_questions`): each reply a choice of its question, an own answer (only for
a question with a free answer), or a dismissal with an optional comment. It SHALL check
every reply first and SHALL refuse the whole call, with nothing changed, when any question
is not open, is not that session's, was not asked by the same agent as the others, or a
reply is not one its question takes. Otherwise it SHALL queue every reply and set every
question's outcome in one transaction, then take the agent's queue once, so an idle agent
with no unconfirmed batch gets all the replies in one hand-over. Each reply SHALL be the
message the core writes for one answer today: `Answer to #<id>: <choice or first line>`
with the rest in its body, or `Dismissed #<id>` with the comment as its body.

#### Scenario: Two answers reach an idle agent in one hand-over
- **WHEN** the supervisor, idle, has open questions #12 (choices "short", "long") and #13
  (a free answer), and the human sends `[#12: "short", #13: "main, then rebase"]`
- **THEN** both questions are answered and the supervisor's window gets one paste holding
  `[from human] Answer to #12: short` and `[from human] Answer to #13: main, then rebase`

#### Scenario: A skipped question is a dismissal
- **WHEN** the human sends `[#12: "short", #13: skip with "later"]`
- **THEN** #12 is answered, #13 is dismissed, and the agent gets
  `Answer to #12: short` and `Dismissed #13` with the body "later" in one hand-over

#### Scenario: One question closed meanwhile
- **WHEN** #13 was answered in another tab before the human sends `[#12, #13]`
- **THEN** the call is refused with `question #13 is answered`, #12 stays open and nothing
  is queued

#### Scenario: Questions of two agents
- **WHEN** a call holds a question of the supervisor and one of developer
- **THEN** it is refused, with nothing changed: one call answers one agent

### Requirement: The server takes a tab's replies in one request

The server SHALL take the human's replies as `POST /api/sessions/{name}/answers` with
`{"answers": [{"question": <id>, "choice": <str|null>, "text": <str|null>, "skip": <bool>}]}`
under the same guard as the composer, through `runtime.answer_questions`, answering
`{result}` with what became of the replies, 400 with the core's reason for what it refuses,
404 for an unknown session. The endpoints `POST …/questions/{id}/answer` and
`POST …/questions/{id}/dismiss` SHALL be gone.

#### Scenario: The UI sends a tab
- **WHEN** the UI posts two replies for the supervisor's questions
- **THEN** the answer is 200 and both questions are closed

#### Scenario: An empty list
- **WHEN** the UI posts `{"answers": []}`
- **THEN** the answer is 400 and nothing changes
