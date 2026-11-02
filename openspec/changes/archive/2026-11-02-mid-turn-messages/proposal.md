Task: LAD-172

## Why

Symptom (manual check of 0.44.0rc1, 2026-11-02, Codex CLI and Claude Code): a worker's
report reaches LADO while the supervisor is in its turn, and the supervisor, unaware of it,
asks the worker to send it again or tells the human it is still waiting:

- Codex, session shop-codex: worker board-url-check's report at 11:13:24, the supervisor's
  "send your report" at 11:13:42; the worker sends it again.
- Codex in the container: three reports of a worker in 40 seconds, two reminders of the
  supervisor between them.
- Claude Code, shop-app: a report at 11:16:14, the supervisor writes "no answer from the
  worker yet" at 11:16:25.

`lado log` shows each of those reports as `[read]`, which looked as if the supervisor had
the report and ignored it.

Cause, read in the code (`runtime.hand_over`, `state.take_pending`, `state.read_messages`,
`log.format_entry`):

- A message to a busy agent waits in its queue (`pending`) until the agent's hook makes it
  idle: at its turn's end the queue is handed over (`hook_output` or `typed`). Nothing
  reaches an agent in the middle of a turn. A supervisor that waits for a worker inside its
  turn (a shell `sleep`, polling `list_agents`, a model that takes "wait" literally, as in
  LAD-167) never sees the report until that turn ends, and reminds the worker meanwhile.
- `read_messages` returns only messages already handed over (`sent`, `delivered`), never a
  `pending` one, so the agent cannot fetch a waiting report mid-turn either.
- `[read]` is true: a message becomes `read` only when `read_messages` returned its body to
  the agent. But `lado log` prints a message's state as it is now beside the time it was
  created, so "11:13:24 [read]" means "came at 11:13:24, read some time later": in these
  sessions most likely at the end of the turn that sent the reminder. LADO keeps no time of
  reading (only `sent_at`, when it was handed over).

Why it is built so: delivery at a turn's end was the one way that works for every CLI
(typing into a busy TUI is lost or mixed into its work; BACKLOG.md "No way to reach a busy
agent urgently"). The one channel every provider shares mid-turn, the result of a call to
LADO's own MCP tools, was never used to carry the queue.

Options weighed:

- A: instructions only ("do not wait for a worker inside a turn; end the turn, the report
  comes as new input"). Cheap, but it rests on the model, and an agent that does check
  mid-turn still has no tool that shows a waiting message.
- B (taken): the queue reaches a busy agent through LADO's tools. The result of any call of
  a `lado` MCP tool carries the caller's queued messages as their lines, and they count as
  delivered, so the turn's end does not hand them over again; a `send_message` to an agent
  whose own message waits unreceived for the caller is refused with that message's line,
  so the "send your report / here it is" round cannot happen; the instructions tell the
  agent where mid-turn messages come from and to end its turn rather than wait in it.
  Long-term cost: one path in `mcp_server`, built on the same `take_pending` as every
  hand-over; one more channel value (`tool_result`).
- C: inject the queue mid-turn through the CLIs' own hooks (Claude Code's `PostToolUse`
  `additionalContext`). Only some providers can (Kilo and OpenCode have no such way), a
  second delivery path per CLI, against the neutral core. Not taken.

Held against the design principles: neutral core (every provider runs LADO's MCP server,
so B works for all four: Claude Code, Codex, Kilo, OpenCode); one source of truth (the
queue and `take_pending` stay the one hand-over; the tool result is a third channel, not a
second queue); no silent drop (a refused reminder says why and what waits); only what is
used (no new tool, no new field of a tool; one channel value).

## What Changes

- Every call of a `lado` MCP tool by an agent takes that agent's pending queue
  (`state.take_pending`, channel `tool_result`, state `delivered`, `sent_at` now) and adds
  the messages' lines, as they are typed today (`runtime.format_messages`), to the tool's
  result after its own content, under one line saying they came during the turn. A tool
  that fails carries them in its error text. With an empty queue the result is unchanged.
- `read_messages` takes the caller's pending queue first in the same way, so a waiting
  message with a body is returned at once (and `read`), one without a body is in the
  result's lines.
- `send_message(to=X)` from agent A is refused, with nothing sent, while a message from X
  to A waits that A has not received: `pending`, or handed over with a body and not read.
  The error names it (`X's message #N waits for you`), carries the queue's lines as above,
  and says to read it with `read_messages` and send again if it still needs saying. Once A
  received it, the same call goes through. Messages to `human` are never refused so.
- LADO's messaging instructions (`runtime.MESSAGING`, every agent) say that a message that
  comes during a turn arrives with the result of the next `lado` tool call; the
  supervisor's (`runtime.SUPERVISOR_INSTRUCTIONS`) say not to wait for a worker inside a
  turn but to end it, and to call `read_messages` before reminding an agent or telling the
  human it waits for one.
- `lado log` stays as it is; docs/cli.md says that a message's state is the state it has
  now, not at the time shown.
- Docs: `docs/design/agents.md` (messages, the hand-over's channels), `docs/cli.md`
  (`lado log`), `docs/design/modules.md` (`mcp_server.py`).
- CHANGELOG.md: the heading `## 0.44.1 (unreleased)` becomes `## 0.45.0 (unreleased)` (an
  MCP tool's behaviour changes: a minor; the human named 0.45.0 as the next version, an
  epic runs in parallel), `### Fixed`: a line on the supervisor that asked again for a
  report it already had.

## Scope

- All agents of every provider, the supervisor and workers alike: a worker gets the
  supervisor's message with its next `lado` tool call too.
- The pending queue of the calling agent only; the channels `typed` and `hook_output` and
  the sweep's rule stay as they are.
- Tests: unit (state, mcp_server, runtime), integration with the fake agent (the report
  that comes during the supervisor's turn, the refused reminder, no second delivery at the
  turn's end).

## Out of scope

- A time of reading in `lado log` or the UI (`read_at`): a schema migration for a
  diagnosis aid; the human chose to document the current meaning instead.
- Mid-turn injection through CLI hooks (option C): not neutral; only if a later task shows
  agents that call no `lado` tool for long stretches still miss messages.
- An "urgent" message typed into a busy agent's window (BACKLOG.md "No way to reach a busy
  agent urgently"): a different channel with its own confirmation; this change already
  gets a message to any agent that calls a `lado` tool.
- Refusing a reminder to a flow run's worker after its `flow_advance`: that report comes
  from `lado` as a step's notice, not as a message from the worker; the general delivery
  in tool results covers it, a refusal would need run bookkeeping no case asks for.
- Holding back the supervisor's "I am waiting" to the human: messages to `human` are never
  refused; the instruction and the delivery in the preceding tool call cover it.

## Decisions for the record

- D1. Delivery rides on the MCP result, in `mcp_server._Server.call_tool`, around every
  tool: one place, every tool, every provider. The lines go in a text content block after
  the tool's own; where a tool also returns structured content, the developer checks in
  each CLI's source which part reaches the model and, if one shows only the structured
  part, adds the lines there too (a key `lado_messages`), saying which in the docs.
- D2. Taken messages are `delivered` at once (channel `tool_result`, `sent_at` set): the
  agent has them in the tool's result as it has `read_messages`' result, so no
  confirmation is waited for and the sweep never retypes them. `sent_at` keeps the
  turn-end check of replies to the human and the lead's `missing` recommendations working
  (the spec of lead-recommendation already counts "a tool's result of that turn").
- D3. The queue is taken whole and in order, so its order is kept; a message without a
  body is received by its line, one with a body still needs `read_messages`.
- D4. The take happens after the tool ran, so a message the tool's own effect queued for
  the caller (none today) would be in it, and the refusal of D5 is checked before the
  send.
- D5. The refusal compares sender and recipient only (a message from X waits for A), not
  content: any message of X answers "where is X's report". After A received it (by this
  very error's lines for one without a body, by `read_messages` for one with a body), the
  same send goes through, so A is never blocked.
- D6. No new MCP tool or argument and no schema migration: `messages.channel` is free text.
- D7. Test layers: the take, the refusal and the formatting are unit tests
  (`tests/test_state.py`, `tests/test_mcp_server.py`, `tests/test_runtime.py`); the
  crossing of processes (a worker's `lado mcp` queues, the busy supervisor's `lado mcp`
  call returns it, its turn-end hook hands over nothing twice) is an integration test with
  the fake agent.

## Impact

- Code: `src/lado/mcp_server.py` (`_Server.call_tool`, `read_messages`),
  `src/lado/runtime.py` (`send_message`'s refusal, `MESSAGING`,
  `SUPERVISOR_INSTRUCTIONS`, a helper that takes and formats the caller's queue),
  `src/lado/state.py` (`TOOL_RESULT` channel; a query for a waiting message from a sender).
- Tests: `tests/test_state.py`, `tests/test_mcp_server.py`, `tests/test_runtime.py`,
  `tests/integration/test_agents.py` (or a new `tests/integration/test_mid_turn_messages.py`).
- Docs: `docs/design/agents.md`, `docs/design/modules.md`, `docs/cli.md`, CHANGELOG.md.
- Specs: a new capability `mid-turn-messages`.
- Version: minor (0.45.0).
