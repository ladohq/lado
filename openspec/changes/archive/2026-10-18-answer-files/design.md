## Context

The composer (`web/src/Composer.tsx`, docs/design/ui.md, Composer) takes files: a
paperclip and a hidden file input, paste (a file, or a text longer than `max_message`
becomes `pasted-<time>.txt`; `image.png` becomes `screenshot-<time>.png`), drop anywhere in
`.chat` / `.agent-page`, chips (`FileChip`) with the unseen eye from `GET /api/limits`, and
on Send uploads each file not uploaded yet (`uploadFile`, an artifact of the session's
scope, `artifacts.upload`) before `writeMessage(..., names)`. Its whole file handling
lives in that one component.

The waiting card (`WaitingCard.tsx`) answers questions through `POST …/answers`
(`models.Reply` → `runtime.HumanReply` → `runtime.answer_questions` → `_reply_of` →
`state.Reply` → `state.reply_to_questions`, which inserts the reply messages with no
attachments) and gates through `GatePanel` (`GateCard.tsx`) → `POST …/gates/{id}/answer`
(`models.GateAnswer` → `runs.answer_text` → `runs.answer` → `_answer_note` → `_commit` →
`state.update_run`, which already takes `attachments` for the note it keeps, as
`flow_advance` uses). Messages and notes share one `attachments` table
(`state._attach`); agents get a message's attachments on delivery and a note's in the
step's text (`runs._attached`, `artifacts.attached_line`: `Artifacts: /<name>` for a
run's worker).

Options held against AGENTS.md's Design principles and ROADMAP (stage 7, the desktop app,
shows the same web UI; nothing in the coming stages changes how answers travel):

1. **Chosen: carry the files through both answer paths into the attachments the store
   already has** (the reply's message, the answer's note). Cost: two optional API fields,
   one schema column, a shared web module; the agent side needs nothing new. Neutral core:
   no provider is involved; every provider reads the files with `read_artifact`. One
   source of truth: the files live once, on the message or the note. No silent drops: a
   name not found or too many files refuse the answer whole; Cancel at a loop limit, which
   has no next step, sends them to the supervisor instead of dropping them.
2. Send the files as a separate composer message next to the answer. No core change, but
   the files go to the supervisor, not to the step's agent or the asking agent, in a
   second hand-over, apart from the answer they explain; refused.
3. Paste links or contents of the files into the comment's text. Breaks the artifacts
   model (size limits, images agents read as images), and the feed could not show them as
   files; refused.

## Decisions

### D1. The composer's file handling becomes one shared module

`web/src/attachFiles.tsx` (name free to the developer) takes out of `Composer.tsx`: the
`Attached` type, `mediaTypeOf`, `stamp`, the attach rule with the server's limits (refused
files as one problem line), remove, the upload of what is not uploaded yet with the
failed-file state and its problem text, the paste rule, `FileChip` / the chips list, the
clip button with its hidden input, and a drop-zone hook for an element. The composer uses
it and behaves exactly as before (`Composer.test.tsx` unchanged). An `AnswerBox`
component of the module is the card's field: the `composer-box` frame with the chips, the
clip and the textarea (grown by `useGrow` 3–8 lines as now), its frame the drop zone.
Reason: Share, don't copy; "the same as the main chat" is the task.

### D2. The card keeps each field's files, as it keeps comments

The waiting card keeps the files per question (one list for Other… and Skip: switching
between them keeps the files, as it keeps the text) and per gate, in its state next to
`picks` and `comments`, so they survive tab switches and the expanded view; items no
longer open drop theirs, revoking thumbnails. `GatePanel` takes `files` / `onFiles` as it
takes `comment` / `onComment`, with its own state when shown alone (Flows). Reason: the
card already owns the comments for the same reason (LAD-28).

### D3. A drop goes to the field under it; the composer ignores the card

Each `AnswerBox` listens to drag events on its own frame (`preventDefault`,
`stopPropagation`) and shows the drop zone there. The composer's area listener ignores
events whose target is inside `.waiting-card`, and the card prevents the default of a
drop elsewhere on it, so the browser never opens the file and the composer never gets it.
Reason: the human's choice (round 1, q. 4), and the composer's area listener is what
caught the card's drops.

### D4. Upload on Send, then one answer request

Send (an agent's tab) uploads the files of every reply of the tab that are not uploaded
yet, then posts `POST …/answers` with each reply's `artifacts`; a gate's button uploads
its files, then posts the answer with `artifacts`. Any failed upload stops the answer, as
in the composer: its chip red with the reason, the uploaded ones kept (an upload of the
same file writes nothing new, `artifacts.upload`). Reason: the composer's proven order.

### D5. The core takes files on every reply and resolves them first

`runtime.HumanReply` gains `attached: tuple[str, ...] = ()`; `_reply_of` checks the
count against `artifacts.MAX_HUMAN_FILES` (`<n> files, the limit is 10`) and resolves
them with `artifacts.resolve_attachments(session, None, names)` before the transaction;
`state.Reply` gains `attachments`, which `reply_to_questions` attaches to each inserted
message (`_attach`). An own answer with no text and files has the summary
`Answer to #<id>: ` + `_files_line(names)`, cut to the limit, and an empty body; "choose
one of the choices or write an answer" stands only with neither text nor files. A choice
with files is taken (the API takes `text` with a choice already); the UI sends none.
Reason: one check point, all or nothing as the call is now.

### D6. A gate's answer: the files on the answer's note

`runs.answer` gains `attached: list[str] | None`; it checks the count and resolves them
before anything is written (a refusal leaves the gate open), and passes them to `_commit`
→ `state.update_run(..., attachments)`, which attaches them to the note it keeps for the
next step. `answer_text` passes them through; `lado answer` and the popup pass none. A
comment of files only gives the note `<outcome>` (as an empty comment does now). At a loop
limit Cancel sends them with LADO's message to the supervisor (`_tell_supervisor` gains
`attachments`, through `runtime.post(..., attachments=...)`); Continue keeps them on its
note like any answer. Reason: the note is what the next step reads (`Note from the
previous step` with its `Artifacts:` line), already built for `flow_advance`.

### D7. Schema 31: `gates.answer_note`

`ALTER TABLE gates ADD COLUMN answer_note INTEGER REFERENCES notes(id)`, set by
`update_run` in the closing's transaction to the note it inserts when `closes` and `noted`
are both given; `state.Gate.answer_note`. No backfill: answers before schema 31 carried no
files, so NULL means none. The server's `GateInfo.answer_attachments` is that note's
attachments (`runs.gate_answer_attachments`, as `gate_attachments` for the note before).
`SCHEMA_VERSION` 31, `MIGRATIONS[30]`, `tests/agent_helpers.previous_schema` updated.
Rejected: a `gate` column in `attachments` with copies of the note's rows (a second source
of truth); finding the note by time or order (fragile, as `gates_closed_events` had to be
backfilled once).

### D8. The feed draws the files with the existing components

`ImagePreviews` and `Attachments` (`Attachments.tsx`) as the human's message uses them:
in `Question.tsx`'s `Given` (the answer message's attachments; a skip too), in `Chat.tsx`'s
`Answer` (a row for a reply not in the window; a skip's quiet line its chips), under the
run's move in `RunEvents` after the comment (`gate.answer_attachments`), and in `GateLine`'s
opened card after the comment (chips only). `LateReply` adds `· <n> file(s)`. The chips
show names as the chat shows a session's artifacts (the session scope has no prefix:
`FullName`); the mockup's leading "/" was only its drawing.

### D9. Limits and API

The composer's limits (`GET /api/limits`: `max_files` 10, `max_size` 25 MB) for every
field; `models.Reply.artifacts: list[str] = []`, `models.GateAnswer.artifacts: list[str]
= []`, `models.GateInfo.answer_attachments: list[AttachmentInfo]`; `make web-types`
regenerates `web/openapi.json` and `web/src/api.gen.ts`; `api.ts`'s `answerGate` and
`Reply` take the names.

### D10. Version

An API change and a schema migration: a minor. CHANGELOG's open heading
`## 0.40.1 (unreleased)` becomes `## 0.41.0 (unreleased)`, with this change's line.
