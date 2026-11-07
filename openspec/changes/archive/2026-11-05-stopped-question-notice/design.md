## Decisions

**D1. The reason is a question state, `stopped`** (`state.QUESTION_STOPPED`), written by
`_close_questions` when `_stop_session` calls it; `delete_agent` and `agent_ended` keep
`closed`. `question_state` is free text, so no migration. Rejected: telling the reason in
the UI from the session's stop time, a second source of truth that a resume blurs.

**D2. One place makes the notice: `runs.resume`,** after the open-runs message. Every way
back runs through it (`lado start`, the UI's Resume, the container's start, `lado update`, a
session whose tmux went away), and every way down through `_stop_session`, so no path needs
its own code. It is its own message with `before_start=True`, sent only when there is
something to list.

**D3. "Told" is stored in `answered_by`:** the notice's id goes into `answered_by` of each
question it lists, in the transaction that queues it. A resume lists the `stopped` questions
of the session whose `answered_by` is null or names a message in state `dropped`. So a
question is listed once, and a resume that failed, or a stop before the supervisor read the
notice, lists it again, as `_stop_session` drops the notice (the rule of "the next resume
writes them anew"). Rejected: a new column (a migration for one flag), and a time floor from
the last `session_resume` event, which a failed resume moves past the questions.
`answered_by` of a `stopped` question is not a reply: the UI reads it for `answered` and
`dismissed` only: the human's chat (`with=human`) holds no such row, and with agents' messages
shown, where `byId` finds the notice, the card of a `stopped` question takes no reply from
it; the field's comment in `models.py` says so.

**D4. The notice's text is English, agent-facing, provider-neutral.** Summary: `<n>
question(s) to the human closed unanswered by the stop`, cut as any summary; a CLI that takes
only lines on its command line (`notice_on_argv`) gets that line and reads the body with
`read_messages`. Body, per question: `#<id> from <asker>: <summary>`, its details, its
`Choices:` line as `ask_recommendation` writes it (one shared helper), then the closing
line: `No one answered these. Ask again with ask_human what is still needed; a run's new
worker may ask its own again in its step.` The questions' attachments go with the notice.

**D5. The count is read, not guessed.** `stop-preview` gains `questions: int`
(`state.open_questions`), and `runtime.Stopped` gains `questions`, counted by `_stop_session`
in its transaction, for `lado stop`'s line.

## Neutral core

Nothing here depends on a provider: state, `runs.resume` and the queue are above
`providers/`. All four providers get the notice as any message from LADO.
