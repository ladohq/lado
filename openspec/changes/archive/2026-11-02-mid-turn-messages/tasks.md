## 1. The failing tests

- [x] 1.1 `tests/test_state.py`: taking a recipient's queue by the channel `tool_result`
  marks the messages `delivered`, sets `sent_at` and keeps their order; a message so taken
  is not taken by `take_pending` again and is out of `state.sweep`'s plan; a query for "a
  message from X waits unreceived for A" is true for a `pending` one and a `delivered`
  unread one with a body, false once read, false for a delivered one without a body. Run:
  `uv run pytest -n0 tests/test_state.py`.
- [x] 1.2 `tests/test_mcp_server.py`: requirement "A busy agent gets its queue with the
  result of a lado tool" (its three scenarios: `list_agents` with a queued report, nothing
  queued, `read_artifact` that fails), and "read_messages returns a waiting message at
  once". The lines are those of `runtime.format_messages`. Fails before 2.2.
- [x] 1.3 `tests/test_runtime.py`: requirement "A reminder to an agent whose message
  waits is refused", its four scenarios; and "The instructions say where mid-turn
  messages come from" (the lines are in `MESSAGING` and in the supervisor's instructions).
  Fails before 2.3 and 2.4.
- [x] 1.4 Integration, `tests/integration/test_mid_turn_messages.py` (marker
  `integration`, the fake agent): a session whose supervisor is busy (the fake agent's
  `pause`); a worker sends it a report with a body; the supervisor's fake agent calls
  `list_agents` through its `lado mcp`: the result carries the report's line and the
  message is `delivered` (`tool_result`); the supervisor calls `send_message` to the
  worker: refused, the worker's queue is unchanged; it calls `read_messages`: the body;
  it ends its turn: the turn-end hook hands nothing over (nothing typed, `hooks.log` and
  the window show no second line of the report). Fails before 2.2. Run:
  `uv run pytest -m integration -n0 tests/integration/test_mid_turn_messages.py`.

## 2. The fix

- [x] 2.1 `src/lado/state.py`: `TOOL_RESULT = "tool_result"` beside `TYPED` and
  `HOOK_OUTPUT` (their comment says it is confirmed by being in the tool's result);
  `take_pending` (or a sibling) takes the queue into `delivered` with that channel and
  `sent_at`; a query for a message from X that waits unreceived for A (`UNRECEIVED`'s
  states, `TO_READ` for a handed-over one). 1.1 passes.
- [x] 2.2 `src/lado/mcp_server.py`, `_Server.call_tool`: after the tool, take the caller's
  queue (2.1) and add its lines in a text block after the tool's content, under one line
  saying they came during the turn; on a `ToolError`, the lines go into its text (D1, D4).
  Check in each CLI's source (Claude Code, Codex, Kilo/OpenCode) whether the model sees
  `content` when a result has `structuredContent`; if one does not, add the lines there
  as `lado_messages` too, and write which in `docs/design/agents.md`. `read_messages`
  takes the queue before it reads (D3). 1.2 and 1.4 pass.
- [x] 2.3 `src/lado/runtime.py`, `send_message`: before queuing, refuse with `LadoError`
  while a message from the recipient waits unreceived for the sender (not for `human`),
  naming it and saying to read it and send again (D5); the queue's lines come from 2.2's
  path. 1.3 passes.
- [x] 2.4 `src/lado/runtime.py`: `MESSAGING` gets the sentence on mid-turn messages;
  `SUPERVISOR_INSTRUCTIONS` the one on not waiting for a worker inside a turn and calling
  `read_messages` before a reminder or a "waiting" to the human. 1.3 passes.

## 3. Docs

- [x] 3.1 `docs/design/agents.md`: the messages paragraph and the hand-over's channels
  get the third channel `tool_result` (taken by any `lado` tool call, `delivered` at once,
  never retyped), `read_messages` taking the queue, and the refused reminder.
- [x] 3.2 `docs/design/modules.md`, `mcp_server.py`: every tool's result carries the
  caller's queue.
- [x] 3.3 `docs/cli.md`, `lado log`: a message's `[state]` is its state now, not at the
  time shown (`read`: its body was returned by `read_messages`, at some time after).
- [x] 3.4 CHANGELOG.md: rename `## 0.44.1 (unreleased)` to `## 0.45.0 (unreleased)`;
  `### Fixed`: **The supervisor no longer asks again for a report it already got.** A
  message that comes while an agent works reaches it with its next LADO tool call, and a
  reminder to an agent whose message waits is refused.

## 4. Checks

- [x] 4.1 `make lint`, `make test`, the integration test of 1.4 with its marker,
  `openspec validate mid-turn-messages --strict`, `openspec validate --specs --strict`.
- [ ] 4.2 Manual on the RC by the human, Codex and Claude Code: a supervisor that gives a
  worker a short task and keeps working; the worker's report reaches it in the same turn,
  and no "send your report" follows. Not done in the build: it needs the release candidate
  and the real CLIs with the human.
