## ADDED Requirements

### Requirement: A gate's answer carries the files the human attached to the next step

`runs.answer` SHALL take the full names of files the human uploaded for the answer, at
most `artifacts.MAX_HUMAN_FILES` (10), resolved before anything is written; a name not
found, or more files than the limit, SHALL refuse the answer with the gate left open. The
note the answer keeps for the next step SHALL carry their latest records as its
attachments, in the transaction that closes the gate, so the step's agent gets them in
`Note from the previous step: …` with its `Artifacts:` line, as it gets a step's
artifacts. A comment of files only SHALL be an answer: the note is the outcome alone with
the files. At a loop limit, Cancel run SHALL send the files with LADO's message to the
supervisor about the cancel; Continue SHALL carry them as any answer's note.

#### Scenario: Reject with a screenshot
- **WHEN** the human rejects task/lad-86's design_ok gate with the comment "the button
  covers the field" and `screenshot-142210-9c0d4b17.png`
- **THEN** the run goes back to design and the analyst's step says `Note from the
  previous step: reject: the button covers the field` with `Artifacts:
  /screenshot-142210-9c0d4b17.png`

#### Scenario: Files only
- **WHEN** the human approves a gate with no comment and `server-3f7a91c2.log`
- **THEN** the next step's note is `approve` and carries `server-3f7a91c2.log`

#### Scenario: A file that is not there
- **WHEN** the answer names `gone-00000000.png`, which the session has no artifact of
- **THEN** the answer is refused and the gate stays open

#### Scenario: Cancel at a loop limit
- **WHEN** the human cancels a run at its loop limit with `notes-b81e6d04.md`
- **THEN** the run is cancelled and the supervisor's message about it carries `notes-b81e6d04.md`

### Requirement: A closed gate keeps the note its answer wrote

The core SHALL keep, with a gate closed by an answer that wrote a note, that note's id
(`gates.answer_note`, schema 31), set in the closing's transaction; a gate closed
otherwise, or before schema 31, SHALL keep none. The server SHALL give each gate
`answer_attachments`, that note's attachments as `AttachmentInfo`, empty when there is no
such note.

#### Scenario: A rejected gate with files
- **WHEN** the human rejected a gate with two files
- **THEN** `GET …/gates` gives that gate `answer_attachments` with the two files, in the
  order they were attached

#### Scenario: A gate closed by a cancel
- **WHEN** the supervisor cancelled the run whose gate was open
- **THEN** the gate's `answer_attachments` is empty

### Requirement: The server takes a gate's answer with files

`POST /api/sessions/{name}/gates/{gate}/answer` SHALL take `{"option": <str>, "comment":
<str>, "artifacts": [<full name>, …]}`, `artifacts` optional and empty by default, through
`runs.answer_text`, with 400 and the core's reason for what it refuses.

#### Scenario: The UI answers with a file
- **WHEN** the UI posts `{"option": "reject", "comment": "", "artifacts":
  ["server-3f7a91c2.log"]}` for an open gate
- **THEN** the answer is 200, the gate is closed `reject` and its `answer_attachments`
  holds `server-3f7a91c2.log`
