# question-answers Specification

## Purpose
The human's replies to an agent's questions (`ask_human`) as the core takes them: several
replies to one agent at once, from the web UI's waiting card, handed over in one batch.

## Requirements

### Requirement: The human's replies to an agent's questions are handed over together

The core SHALL take the human's replies to several open questions of one agent in one call
(`runtime.answer_questions`): each reply a choice of its question, an own answer (only for
a question with a free answer), or a dismissal with an optional comment. When its check of
the replies refuses none, it SHALL queue every reply and set every
question's outcome in one transaction, then take the agent's queue once, so an idle agent
with no unconfirmed batch gets all the replies in one hand-over.

#### Scenario: Two answers reach an idle agent in one hand-over
- **WHEN** the supervisor, idle, has open questions #12 (choices "short", "long") and #13
  (a free answer), and the human sends `[#12: "short", #13: "main, then rebase"]`
- **THEN** both questions are answered and the supervisor's window gets one paste holding
  `[from human] Answer to #12: short` and `[from human] Answer to #13: main, then rebase`

### Requirement: A call of replies is checked whole before anything changes

`runtime.answer_questions` SHALL check
every reply first and SHALL refuse the whole call, with nothing changed, when any question
is not open, is not that session's, was not asked by the same agent as the others, or a
reply is not one its question takes.

#### Scenario: One question closed meanwhile
- **WHEN** #13 was answered in another tab before the human sends `[#12, #13]`
- **THEN** the call is refused with `question #13 is answered`, #12 stays open and nothing
  is queued

#### Scenario: Questions of two agents
- **WHEN** a call holds a question of the supervisor and one of developer
- **THEN** it is refused, with nothing changed: one call answers one agent

### Requirement: Each reply is the message of one answer

Each reply SHALL be the
message the core writes for one answer today: `Answer to #<id>: <choice or first line>`
with the rest in its body, or `Dismissed #<id>` with the comment as its body.

#### Scenario: A skipped question is a dismissal
- **WHEN** the human sends `[#12: "short", #13: skip with "later"]`
- **THEN** #12 is answered, #13 is dismissed, and the agent gets
  `Answer to #12: short` and `Dismissed #13` with the body "later" in one hand-over

### Requirement: The server takes a tab's replies in one request

The server SHALL take the human's replies as `POST /api/sessions/{name}/answers` with
`{"answers": [{"question": <id>, "choice": <str|null>, "text": <str|null>, "skip": <bool>,
"artifacts": [<full name>, …]}]}` (`artifacts` optional, empty by default) under the same
guard as the composer, through `runtime.answer_questions`, answering `{result}` with what
became of the replies, 400 with the core's reason for what it refuses, 404 for an unknown
session.

#### Scenario: The UI sends a tab
- **WHEN** the UI posts two replies for the supervisor's questions
- **THEN** the answer is 200 and both questions are closed

#### Scenario: An empty list
- **WHEN** the UI posts `{"answers": []}`
- **THEN** the answer is 400 and nothing changes

#### Scenario: A reply with a file
- **WHEN** the UI posts a reply with `"artifacts": ["screenshot-142731-5e1f02aa.png"]`
- **THEN** the answer is 200 and the reply's message lists that artifact among its
  attachments

### Requirement: The server answers no question on its own

The endpoints `POST …/questions/{id}/answer` and `POST …/questions/{id}/dismiss`
SHALL be gone.

#### Scenario: A single question's endpoint
- **WHEN** a client posts to `POST /api/sessions/{name}/questions/12/answer`
- **THEN** the server has no such endpoint, and question #12 stays open

### Requirement: A reply carries the files the human attached

Each reply SHALL take the full names of files the human uploaded for it (artifacts of the
session's scope, as the composer's), at most `artifacts.MAX_HUMAN_FILES` (10), and the
core SHALL attach their latest records to the reply's message in the transaction that
queues it, as a composer message's files are attached; a name that is not found, or more
files than the limit, SHALL refuse the whole call with nothing changed.

#### Scenario: An own answer with a screenshot
- **WHEN** the human answers #13 (a free answer) with the text "like this" and
  `screenshot-142731-5e1f02aa.png`
- **THEN** the agent gets `Answer to #13: like this` with that artifact attached, in the
  same hand-over as the tab's other replies

#### Scenario: A file that is not there
- **WHEN** a reply names `gone-00000000.png`, which the session has no artifact of
- **THEN** the call is refused, every question stays open and nothing is queued

#### Scenario: Too many files
- **WHEN** a reply names 11 files
- **THEN** the call is refused with `11 files, the limit is 10` and nothing changes

### Requirement: The agent gets a reply's files, and a reply of files alone is an answer

The agent SHALL get the files with the reply as it gets a composer message's. An own answer of
files only, with no text, SHALL be an answer: its summary `Answer to #<id>: <n> file(s):
<names>`, cut to the summary's limit, and an empty body. A skip SHALL take files with or
without its comment.

#### Scenario: Files only
- **WHEN** the human answers #13 with no text and `server-3f7a91c2.log`
- **THEN** #13 is answered and the reply's summary is `Answer to #13: 1 file: /server.log`

#### Scenario: A skip with a file
- **WHEN** the human skips #12 with `notes-b81e6d04.md` and no comment
- **THEN** #12 is dismissed and the agent gets `Dismissed #12` with `notes-b81e6d04.md` attached
