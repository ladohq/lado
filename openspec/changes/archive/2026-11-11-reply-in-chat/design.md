## Context

The experiment's patch (`/reply-fix-acb.diff`, against 2579d9e3, without tests, docs or
CHANGELOG) is the shape that was measured: the rule C in `SUPERVISOR_INSTRUCTIONS`, the hint A
in `runtime.format_message`, and B as `state.check_replies` returning the ids it marked
`missing` and `hooks.handle` queueing one `lado` message for each at `TURN_END`, before
`_idle` hands the queue over. This change builds on that shape and adds what the human decided
on #6042: the rule for workers too, and a verdict that waits for the reminder.

## Decisions

**D1. The rule is one text for the supervisor and the workers.** The sentence of C becomes a
constant (e.g. `HUMAN_REPLY_RULE`) that `SUPERVISOR_INSTRUCTIONS` takes right after its first
line and `WORKER_INPUT` takes as its first lines, so both kinds of worker instructions get it.
Why: one source of truth; a worker that gets the hint A without the rule C is the "A without C"
case the human ruled out. The supervisor's sentence on "[from lado] human wrote to <agent>"
stays where it is.

**D2. The hint is a constant appended in `format_message`.** `HUMAN_REPLY_HINT = ' (reply with
send_message(to="human") or ask_human)'`, added when `message.sender == state.HUMAN` and
`message.reply_to is None`, after the `(#<id>, …: call read_messages)` part. English, like
every LADO text to agents. Why: `state.confirm_sent` matches the typed line through the same
`format_message`, so delivery confirmation keeps working unchanged (the experiment confirmed
it); answers and dismissals need no reply (`check_replies` skips them already).

**D3. The state `reminded` in the existing column.** `messages.reply_state` is TEXT; it gets a
third value `reminded` (`state.REMINDED`). No schema change, no migration. Transitions, all in
`check_replies` and in one transaction: NULL → `replied` (wrote to the human after `sent_at`) or
→ `reminded` (did not); `reminded` → `replied` or `missing` once the reminder was handed over.
`check_replies` returns the ids that became `reminded`; `hooks.handle` queues the reminder for
each, as in the patch. Order inside `check_replies`: first decide the `reminded` messages, then
the NULL ones; the other order would decide a message reminded in this very call before its
reminder is even queued. Why: one place decides, one value says "asked once already", so no
second reminder is possible and the verdict of a message answered after the reminder is right.

**D4. "After the reminder was handed over" is read from the queue.** At a clean turn's end, the
agent's `reminded` messages are decided only when no message from `lado` to that agent is
`pending` or `sent` (not yet `delivered`); otherwise they stay `reminded` for the next clean
turn. Why: a turn that ended before the reminder reached the agent has not seen it and must not
decide; the check needs no new column (a link from the reminder to its message would need a
migration), and being conservative only delays the note by a turn. A reminder `dropped` (the
agent finished or the session stopped) leaves the message `reminded`, shown as none, until a
later clean turn of that agent decides it; a finished agent never does, which is the truth: no
verdict.

**D5. The API shows `reminded` as none.** `server/models.py` keeps `reply_state:
Literal["replied", "missing"] | None` and maps `reminded` to `None`; `web/openapi.json` and
`api.gen.ts` do not change, nor does the UI. Why: the human sees "not decided yet", which is
the truth; no API change, no web types to regenerate.

**D6. The reminder's text is the experiment's.** `your answer to the human's message #<id> went
only to your terminal, which the human does not see. If it needs an answer, use
send_message(to="human") or ask_human; else do nothing.` (179 characters, under
`SUMMARY_LIMIT`), a summary without a body. Why: measured; "else do nothing" kept the needless
replies to 2 of 13. It shows in the chat only under "All", like other `lado` messages.

**D7. All agents, all providers.** `check_replies` already runs for every agent at `TURN_END`;
the reminder follows it. No provider switch. Why: neutral core (AGENTS.md); strong models
already answer in the chat and so never get a reminder; the hint costs about 15 tokens.

**D8. Tests by layer.**

- Unit (`tests/test_runtime.py`): the rule in the supervisor's instructions after its name and
  in both worker instructions, the old sentence gone (replaces
  `test_the_supervisor_is_told_to_answer_the_human_where_they_asked`); `format_message` with
  and without a body, with the hint, and an answer without it. The exact `[from human] …`
  expectations of `test_runtime.py`, `test_attachments.py`, `test_tmux.py`, `test_codex.py`
  follow the new line.
- Unit (`tests/test_state.py` or where `check_replies` is tested): NULL → `replied`,
  NULL → `reminded` (returned), `reminded` → `replied` / `missing` after the hand-over,
  `reminded` kept while the reminder waits, no id returned twice, answers skipped.
- Unit (hooks, `tests/test_hooks.py` or the module that tests `hooks.handle`): `TURN_END`
  queues one `lado` message per returned id; none on a turn with an error.
- Unit (server): `reminded` reaches the API as `null`.
- Integration (`tests/integration/test_human_messages.py`, fake agent): an agent that answers
  only in its terminal gets exactly one reminder and the message ends `missing`; an agent that
  answers after the reminder (a fake-agent command for it) ends `replied`; the queue does not
  loop. The fake agent's commands read from the message text (`pause`, `sleep 0`, …) must parse
  with the hint at the end; the exact-line expectations of `test_agents.py`,
  `test_agent_liveness.py`, `test_session_start.py`, `test_mid_turn_messages.py` follow.
- UI e2e (`tests/ui/test_chat.py`): only if a `[from human]` expectation there changes.
- Live (`tests/live/test_live.py`): the human writes "hello" with no instruction how to answer;
  the reply reaches the chat (`replied`), on each provider's live model. Written, not run: live
  runs are paid and by hand (settings, Checks).

## Risks

- A weak model may answer a "thanks" after the reminder (2 of 5 in the experiment): accepted,
  one polite line.
- A model may claim it already answered (1 of 13): the message then ends `missing`, and the
  chat says so, as today.
