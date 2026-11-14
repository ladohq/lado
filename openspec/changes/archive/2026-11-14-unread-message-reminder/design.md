## Context

LAD-274 added one reminder from `lado` at a clean turn's end for the human's messages the agent
did not answer in the chat (`state.check_replies`, `hooks.REPLY_REMINDER`, queued in
`hooks.handle` at `TURN_END` before `_idle` hands the queue over). This change adds a second
check of the same shape, for a text the agent got and never read, for messages from any sender.

## Decisions

**D1. A new column `messages.read_reminded`, schema 39 → 40.** `INTEGER NOT NULL DEFAULT 0`;
the migration adds it and sets it to 1 on every existing row (the requirement "Texts left unread
before the update are not reminded"). `SCHEMA_VERSION`, `MIGRATIONS[39]` (the step from 39), the table's `CREATE`
in `SCHEMA` and `tests/agent_helpers.previous_schema` follow AGENTS.md's rule. Why: the mark
"reminded once" must outlive the turn and the process; `reply_state` (LAD-274's column) means a
reply to the human and is shown by the API, and a human's message can need both marks at once.
Searching the `lado` messages for `#<id>` would be a second source of truth.

**D2. `state.check_unread(session, agent) -> list[Message]` in one transaction.** It selects
the agent's messages with `state = DELIVERED`, `TO_READ` and `read_reminded = 0`, ordered by id,
sets `read_reminded = 1` on them and returns them. `DELIVERED` alone: `read` is read, `sent` is
not yet confirmed (the requirement "A message is reminded at most once"), `pending` is not
handed over, `dropped` and `failed` are gone. Any sender, `lado` and `human` included: a flow
step's text comes from `lado` in a body; messages to `human` are never checked, as only agents
end turns.

**D3. `hooks.handle` at `TURN_END`, right after the reply check, only when `not event.error`.**
After `confirm_channel` / `output_not_taken` (so a turn that went on from the hook's output has
its batch `delivered` and checked) and before `_idle` (so this hook's own hand-over is not
checked: those messages are `sent`). One `state.queue_message(session, state.LADO, agent,
text)` for the whole list, the text from `hooks.UNREAD_REMINDER`, a constant next to
`REPLY_REMINDER`:

- one: `you have not read message #3 from supervisor: call read_messages to get its text; if it
  asks nothing of you, do nothing.`
- several: `you have not read messages #3 from w1, #5 from w2: call read_messages to get their
  text; if it asks nothing of you, do nothing.`
- too many for one line (`state.SUMMARY_LIMIT`, as LADO's other lines): as many as fit, then
  `… (<n> more)`; `read_messages` returns them all anyway (`hooks.unread_reminder`).

Why one message: one short turn, whatever the count. "If it asks nothing of you, do nothing"
follows LAD-274's measured "else do nothing", which kept needless replies rare. The reminder has
no body, so it can never be reminded itself.

**D4. Read-only agents, the supervisor and workers alike.** No exception: a passive or
read-only lead that leaves a report unread gets the reminder too; `read_messages` is allowed to
every role. The fingerprint of a read-only agent's turn is untouched (the reminder is a message,
as LAD-274's).

**D5. No UI or API change.** The reminder shows in the chat as any message from `lado` to an
agent does (LAD-274's reminder does so); `read_reminded` is not given by the API.

## Test layers

- Unit (`tests/test_state.py`, and `tests/test_runtime.py` beside LAD-274's hook tests): `check_unread` for each state, with and
  without a body or artifacts, once only; the migration from 39 sets existing rows reminded; the
  hook queues one reminder with the exact texts of D3, none on an error turn, and checks after
  the hook output's confirmation and before the hand-over.
- Integration with the fake agent (crosses tmux, hooks, `lado mcp`, SQLite): a worker that ends
  its turn without `read_messages` gets exactly one reminder, reads after it, and no reminder
  follows; a turn with an error reminds of nothing; a read message gets none.
- Live: no change (cells on a strong model, LAD-273). Regression: `make test` and the changed
  integration files; CI runs the rest.
