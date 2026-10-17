## ADDED Requirements

### Requirement: The card's answer fields take files as the composer does

The waiting card's fields of an own answer (Other…), of a Skip's comment and of a gate's
comment for the next step SHALL each take files as the composer does, wherever the card
or the gate's panel shows (a session's chat, Needs you, a run's page in Flows): a
paperclip at the field's left that opens the file picker, the attached files as chips
above the text (an image's thumbnail or its type's icon, the crossed-out eye when an
agent cannot read it, the name, the size, × to remove), a file or a text longer than a
message pasted into the field attached as in the composer, and files dropped on the field
attached to it, the field's frame the drop zone while files are dragged over it ("Drop to
attach · up to <n> files, <size> each"). The limits SHALL be the server's
(`GET /api/limits`), refused files named at the field. A picked choice SHALL have no field
and take no files. Files dropped in the chat outside the card SHALL go to the composer;
files dropped on the card SHALL never go to the composer. The files of each field SHALL be
kept across the card's tabs and its expanded view until they are sent or removed. Sending
(the tab's Send, a gate's button) SHALL upload every file not uploaded yet, then answer
with their full names; a file whose upload failed SHALL stay red with its reason, nothing
SHALL be answered, and the next Send SHALL retry it. Beside a gate's buttons SHALL stand
"<n> file(s), <size>" while it has files.

#### Scenario: A screenshot pasted into a gate's comment
- **WHEN** the human pastes a screenshot into the comment of task/lad-86's gate and
  clicks Reject
- **THEN** the file is uploaded, the gate is answered `reject` with the comment and the
  file, and the tab goes

#### Scenario: Files with an own answer
- **WHEN** the human picks Other… on #13, attaches `server.log` with the clip and types
  nothing
- **THEN** the question counts as answered and Send sends it with the file

#### Scenario: A choice takes no files
- **WHEN** the human picks the choice "main" on #12
- **THEN** #12 shows no field and no paperclip

#### Scenario: A drop on the card
- **WHEN** the human drops a file on the comment of a gate's tab
- **THEN** the file is attached to that comment and the composer gets nothing

#### Scenario: A drop elsewhere in the chat
- **WHEN** the human drops a file on the feed while the card is shown
- **THEN** the file is attached to the composer, as before

#### Scenario: An upload that fails
- **WHEN** one of two files of a gate's comment fails to upload on Approve
- **THEN** the gate stays open, that file's chip is red with the reason, and the next
  Approve uploads only that file

### Requirement: A closed question card shows the reply's files

The reply block of a closed question card ("You · answered", "You · skipped") SHALL show
the files the reply carries as the human's own message does: the images as previews (at
most 240 × 180), then a chip per file; each opens its record in the panel. The human's row
of an answer to a question not in the window SHALL show them the same way, and a skip of
such a question its chips. The quiet line of an answer given after other rows ("You
answered question #N ↑ · …") SHALL end with "· <n> file(s)" when the reply carries
files.

#### Scenario: An own answer with a screenshot and a log
- **WHEN** #41 was answered "like this" with a screenshot and `server.log`
- **THEN** its card's reply block shows "like this", the screenshot's preview, and the
  chips of both files

#### Scenario: A late answer with files
- **WHEN** the human answers #41 with two files after other rows of the chat
- **THEN** the quiet line where it was given ends with "· 2 files"

## MODIFIED Requirements

### Requirement: An agent's tab sends its answers together

An agent's tab SHALL list its open questions, numbered when it has more than one, each with
its text, its details (Markdown) and its attachments, its choices, **Other…** when the
question takes a free answer, and **Skip**. A choice SHALL be picked by a click and unpicked
by a second; Other… SHALL open a field for an own answer, Skip a field for an optional
comment, and each of the three SHALL exclude the other two. The tab's one button,
**Send answer to <agent>** or **Send <n> answers to <agent>**, SHALL be off until each of
its questions has a picked choice, an own answer that is not blank or has files, or Skip;
with more than one question "<k> of <n> answered" SHALL stand beside it until then. Send
SHALL send all of the tab's replies, each with its field's files, in one request
(`POST …/answers`); a refusal SHALL show on the tab with the core's reason, with the
human's picks and files kept.

#### Scenario: Two questions, one answered
- **WHEN** the supervisor's tab has two questions and only the first has a picked choice
- **THEN** "Send 2 answers to supervisor" is off and "1 of 2 answered" stands beside it

#### Scenario: All answered
- **WHEN** the first has the choice "short" and the second Other… with "main, then rebase"
- **THEN** Send is on, and a click posts both replies in one request

#### Scenario: A question that takes no own answer
- **WHEN** a question has choices and no free answer
- **THEN** it shows its choices and Skip, and no Other…

#### Scenario: An own answer of files only
- **WHEN** the only question has Other… picked with an empty field and one file
- **THEN** "Send answer to <agent>" is on

### Requirement: A gate's tab answers the gate at once

A gate's tab SHALL show the gate's question, the note that led to it with its artifacts,
the artifacts it reads, the comment for the next step with its files and the gate's
buttons (Approve / Reject, a choice gate's options, Continue / Cancel run at a loop limit),
which SHALL answer the gate at once through `runs.answer`, with the comment and the files,
as the gate's card did. In a stopped session the buttons SHALL be off and the tab SHALL
say "The session is stopped: resume it to answer."

#### Scenario: Approve
- **WHEN** the human clicks Approve on the tab of task/lad-27
- **THEN** the gate is answered `approve` with the comment, the run moves on and the tab
  goes

#### Scenario: A stopped session
- **WHEN** the session is stopped with its gate open
- **THEN** the card keeps the gate's tab, its buttons off, with "The session is stopped:
  resume it to answer."

#### Scenario: Reject with a file
- **WHEN** the human attaches `server.log` to the comment of task/lad-27's gate and
  clicks Reject
- **THEN** the gate is answered `reject` with the comment and `server.log`, and the tab
  goes
