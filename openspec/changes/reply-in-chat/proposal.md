Task: LAD-274

## Why

A supervisor on a weak model (Kilo or OpenCode with Qwen3-Coder-Next, GLM-5.3-flash,
Nemotron and the like) answers the human's message as text in its own terminal, not with
`send_message(to="human")` or `ask_human`. The human gets no answer in the chat; the feed only
says "supervisor replied only in its terminal".

Cause, checked against the code at 02767b42:

- LADO's rule on answering the human is one sentence in the middle of
  `runtime.SUPERVISOR_INSTRUCTIONS`, and an ambiguous one: "answer text typed straight into your
  window in this window", while the human's message does arrive typed into the window.
- The base prompts of OpenCode and Kilo tell the model that all its text outside a tool call is
  shown to the user; a weak model follows them.
- The line `[from human] …` (`runtime.format_message`) says nothing about how to answer.
- The check at a turn's end (`state.check_replies`) only marks the message `missing` for the
  UI; the agent never learns of it.
- Workers get no rule on the human at all (`WORKER_INPUT`), though the human may write to any
  agent.

The experiment of 2026-11-11 (session research, artifacts `/reply-experiment-report.md` and
`/reply-fix-acb.diff`, attached to the task; free OpenCode models, 15 messages a run, blind
grading) measured three fixes:

- Today: weak models delivered 7% of the answers (6 of 91); minimax and beam 100%.
- C (the rule first in the LADO block, unambiguous, "no answer needed for thanks"): 6% on the
  weakest models alone.
- A (a hint on the human's line): 80% with content, but 8 of 64 messages empty notes ("Greeting
  back to human") with the answer left in the terminal, and a reply to every "thanks".
- A+C: 88%, no empty notes. A+C+B (one reminder from `lado` per `missing`): 98% (63 of 64),
  2 needless polite lines and one false "already answered" in 13 reminders. Quality of the
  answers the same for A+C and A+C+B, about 4.1 of 5.

Options with their long-term cost:

- **A+C+B (taken, the human's decision in the task and #6042).** Three small pieces in
  provider-neutral code (`runtime`, `state`, `hooks`); about 15 tokens per human message and one
  short extra turn per message the agent did not answer in the chat (thanks included). No
  schema change, no new tool. Works the same for every provider.
- A+C without B: 88%; the misses stay silent, as today. Rejected by the human: the reminder is
  cheap and caught 6 of 7 misses.
- A per-provider fix (a rule in each CLI's own system prompt, only for OpenCode and Kilo):
  breaks the neutral core (AGENTS.md, Design principles), and the same weak model under another
  CLI would fail again. Rejected.
- A alone: rejected by the human; it fills the chat with empty notes.

## What Changes

- **C, the rule.** The supervisor's instructions start with it: the human follows the session
  in LADO's UI and does not see the terminal; text outside a tool call reaches nobody; answer
  each `[from human] …` that needs an answer with `send_message(to="human")` or `ask_human`; a
  message that needs no answer (thanks, "not now") needs no reply; only text typed into the
  window without `[from human]` is answered in the window. The ambiguous sentence goes. Workers
  get the same rule in `WORKER_INPUT`, shared by both kinds of worker instructions.
- **A, the hint.** The line of each message from the human that is not an answer or dismissal
  of a question (`reply_to`) ends with ` (reply with send_message(to="human") or ask_human)`,
  for every agent and provider.
- **B, the reminder.** When a turn's end marks a human message unanswered in the chat, LADO
  queues the agent one message from `lado`: `your answer to the human's message #<id> went only
  to your terminal, which the human does not see. If it needs an answer, use
  send_message(to="human") or ask_human; else do nothing.` One per human message, never again.
- **The verdict waits for the reminder.** The message is `reminded` until the end of the first
  clean turn after the reminder was handed over: `replied` if the agent wrote to the human by
  then, else `missing`, and only then the chat shows "replied only in its terminal". The API
  shows `reminded` as no reply state yet.
- Docs: `docs/design/agents.md` and `docs/design/ui.md` (the forgotten-reply check),
  `docs/design/modules.md` (`state.check_replies`, `hooks`), CHANGELOG under Fixed.
- Version: a patch (no MCP tool, CLI or schema change). Main is frozen until 0.46.1's final;
  the merge waits for it (the human at `merge_ok`), the CHANGELOG item goes under
  `## 0.46.2 (unreleased)`.

## Scope

`src/lado/runtime.py` (instructions, `format_message`), `src/lado/state.py`
(`check_replies`, the state `reminded`), `src/lado/hooks.py` (the reminder at `TURN_END`),
`src/lado/server/models.py` (`reminded` shown as none), the fake agent and tests at the unit,
integration and live layers, the docs above, CHANGELOG.

## Out of scope

- The chat language: weak models often answer in English though the chat is Russian. A matter
  of the kit's or the language rule, not of delivery; its own task (the task says so).
- Relaying workers' reports to the human: the experiment barely ran workers; the existing rule
  ("Do not relay worker or reviewer reports") stays as it is, unchanged by this change.
- A live cell on a weak model: nondeterministic (98% means random reds in a weekly and RC run),
  and paid; the experiment is the evidence for weak models (the human's decision #6042).
- The hint only on the first line of a batch of human messages: saves a few tokens, but each
  line is confirmed by its own `format_message` text (`state.confirm_sent`) and the experiment
  ran with a hint per line.
- A new text for the note under a message the agent rightly left unanswered ("thanks"): it shows
  "replied only in its terminal" as today.
- A per-provider switch of A or B: neutral core; strong models delivered 100% with the same line.

## Impact

- Weak models answer the human in the chat (98% in the experiment instead of 7%).
- Every agent's prompt grows by the rule; each human message by about 15 tokens.
- An unanswered human message costs one short extra turn.
- Tests that match the exact `[from human] …` line or the old instruction sentence change.
