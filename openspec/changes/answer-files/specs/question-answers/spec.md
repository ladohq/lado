## ADDED Requirements

### Requirement: A reply carries the files the human attached

Each reply SHALL take the full names of files the human uploaded for it (artifacts of the
session's scope, as the composer's), at most `artifacts.MAX_HUMAN_FILES` (10), and the
core SHALL attach their latest records to the reply's message in the transaction that
queues it, as a composer message's files are attached; a name that is not found, or more
files than the limit, SHALL refuse the whole call with nothing changed. An own answer of
files only, with no text, SHALL be an answer: its summary `Answer to #<id>: <n> file(s):
<names>`, cut to the summary's limit, and an empty body. A skip SHALL take files with or
without its comment. The agent SHALL get the files with the reply as it gets a composer
message's.

#### Scenario: An own answer with a screenshot
- **WHEN** the human answers #13 (a free answer) with the text "like this" and
  `screenshot-142731-5e1f02aa.png`
- **THEN** the agent gets `Answer to #13: like this` with that artifact attached, in the
  same hand-over as the tab's other replies

#### Scenario: Files only
- **WHEN** the human answers #13 with no text and `server-3f7a91c2.log`
- **THEN** #13 is answered and the reply's summary is `Answer to #13: 1 file: /server.log`

#### Scenario: A skip with a file
- **WHEN** the human skips #12 with `notes-b81e6d04.md` and no comment
- **THEN** #12 is dismissed and the agent gets `Dismissed #12` with `notes-b81e6d04.md` attached

#### Scenario: A file that is not there
- **WHEN** a reply names `gone-00000000.png`, which the session has no artifact of
- **THEN** the call is refused, every question stays open and nothing is queued

#### Scenario: Too many files
- **WHEN** a reply names 11 files
- **THEN** the call is refused with `11 files, the limit is 10` and nothing changes

## MODIFIED Requirements

### Requirement: The server takes a tab's replies in one request

The server SHALL take the human's replies as `POST /api/sessions/{name}/answers` with
`{"answers": [{"question": <id>, "choice": <str|null>, "text": <str|null>, "skip": <bool>,
"artifacts": [<full name>, …]}]}` (`artifacts` optional, empty by default) under the same
guard as the composer, through `runtime.answer_questions`, answering `{result}` with what
became of the replies, 400 with the core's reason for what it refuses, 404 for an unknown
session. The endpoints `POST …/questions/{id}/answer` and `POST …/questions/{id}/dismiss`
SHALL be gone.

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
