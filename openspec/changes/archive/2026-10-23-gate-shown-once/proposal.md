Task: LAD-135

## Why

When a flow run reaches a gate, the chat shows the gate twice, one row under the other
(the task's screenshot: gate #96 of `epic/epic-projects` at `step_ok`). The run's group
ends with the line "L lado · waits for you · #96 approval at step_ok: <question>", and
right under it stands the gate's own row: "Gate #96 … waits: <question> ↓" while it is
open, and the folded card "Gate #96 · approve by you" once it is answered. The line's
text is long, so on the chat's width it wraps under the line and takes its time with it.
Once the gate is answered, the line is also wrong: it still says "waits for you".

Root cause: `web/src/Chat.tsx` draws the run's `gate_open` event as a line of its run
(`RUN_EVENT_LINES.gate_open = "waits for you"`, since feature/chat-message-text,
2026-10-07, before the gate got a row of its own in the feed), and the gate's row
(`OpenLine` while open, `GateLine` once closed) shows the same gate from `GateInfo`.
Nothing else reads the line: the Flows page, the waiting card and Needs you show gates
from `GateInfo`.

Options weighed (mockup `task/lad-135/mockup-gate-line.html`):

1. **Chosen (the human: option 1): the gate's opening is no line of the chat**; the
   gate shows only in its own row, open or closed. Cost: none lasting; one entry of the
   UI's list goes, no core or API change.
2. Hide the line only once the gate is answered: the open gate still shows twice, and
   the UI would have to tie the event to its gate by parsing its detail (the UI parses
   no detail) or by a new API field.
3. Keep the line and say "waited" once answered: the repetition stays.

## What Changes

- The chat shows no line for a run's `gate_open` event. The run's group ends with the
  move that led to the gate, and the gate's row stands right under it, as today.
- The `.run-gate_open` chip's colour rule goes from `web/src/styles.css`.
- Docs: `docs/design/ui.md` (Flow events), CHANGELOG.md (Fixed, under the open
  `## 0.43.0 (unreleased)`).
- A fix (patch): no CLI, MCP, API or schema change.

## Scope

- `web/src/Chat.tsx` (`RUN_EVENT_LINES` and its comment), `web/src/styles.css`.
- Tests: vitest `web/src/Chat.test.tsx`; UI e2e `tests/ui/test_chat.py`,
  `tests/ui/test_gates.py`.

## Out of scope

- **The core's `gate_open` event**: it stays as it is. `lado log`, usage statistics and
  the gate's time in the history (`gate-history-order`) read it.
- **The gate's rows** (`OpenLine`, `GateLine`) and the waiting card: they already show
  the gate's question; they stay unchanged.
- **The Flows page**: it shows no event lines of the chat.
- **The other run lines** (started, ended, cancelled, set by you): the task is about the
  gate's line; each of those is the only row of its fact.

## Impact

- The chat's run groups lose one line per gate. No CLI, MCP, API, provider or schema
  change.
- The living spec `gate-history-order` names the `gate_open` event's line in the chat;
  its requirement is modified so the shared time keeps the gate's row after the move
  that led to it, and a requirement is added that the gate's opening is no line.
