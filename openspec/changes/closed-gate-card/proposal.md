Task: LAD-85

## Why

After the human answers a gate in the chat, their comment shows twice (the task's
screenshot: gate #387 of `task/lad-83`, rejected with a long comment): once under the
closed gate's line ("Gate #387 · task/lad-83 · merge_ok: reject by human") and once under
the run's move "You merge_ok → build rejected".

Root cause: two parts of the chat each draw the same `GateInfo.comment`.
`GateCard.tsx`'s `GateLine` puts it under the closed gate's line (`.gate-comment`, since
the gates-in-the-chat task), and `Chat.tsx`'s `RunEvents` puts it under the human's move
(`.run-comment`, `gateOf`, since feature/chat-message-text, 2026-10-07, which made the
move the answer's one line but left the gate line's copy). The gate's line stands where
the gate opened, the move where it was answered; when nothing came between, the two
copies stand one under the other. A gate closed by `lado flow-set` or by a run's cancel
repeats its reason the same way: the event's line says it already.

When the human opens the closed gate's line, what it shows (the question, the note that
led to the gate up to 20 lines at once, the recommendation's line) is one grey flow with
no parts to find by eye, and a long note fills the screen (the human, at design).

Options weighed (mockup `task/lad-85/mockup-gate-comment.html`):

1. **Chosen (the human: A): the comment only under the move**; the gate's line is its
   title alone, and its opened view shows the answer with the comment. Cost: none
   lasting; the answer stays where it was given, the history keeps it a click away.
2. Only on the gate's line: the move at the bottom, where the human just answered, would
   lose the comment; the gate's line is often far above.
3. Hide one copy only when both stand next to each other: depends on the window and
   scrolling of the feed; fragile, and the copies still repeat with anything between.

The opened view (mockup `task/lad-85/mockup-gate-expanded.html`, the human: option 2):
a card that shows the question and the answer, and folds the note and the
recommendation into a line each.

## What Changes

- A closed gate's line in the chat shows its title and time, no comment; the human's
  move keeps the answer's comment under it as today.
- A click on the line opens a card: the question; the answer as a plaque in the "waits
  for you" colours (who answered, the answer, where the run went and when, the comment
  in full); then two folded lines: **Note** (the note's summary and how many artifacts it
  carries) and **Supervisor** (what the supervisor recommended and whether the answer
  agreed). A folded line opens on a click; the note opened shows 6 lines with Show more,
  and its artifacts.
- The server names, for each closed gate, the run's event its closing wrote
  (`GateInfo.closed_by_event`); the chat links the comment and the card's "→ <state>" to
  the move by that id instead of guessing by time and state (risk of D3, the human: B).
- Docs: `docs/design/ui.md` (Flow gates: a closed gate), CHANGELOG.md.
- A patch-level fix (one field of the UI server's API; no CLI, MCP or schema change); its CHANGELOG line goes
  under the open heading `## 0.40.0 (unreleased)`.

## Scope

- `src/lado/state.py` (the closing's event of a gate, read with the gate),
  `src/lado/server/models.py` (`GateInfo.closed_by_event`), `web/openapi.json` and
  `web/src/api.gen.ts` (`make web-types`).
- `web/src/GateCard.tsx` (`GateLine`, its note and recommendation lines),
  `web/src/Chat.tsx` (`gateOf` and `moveOf` by id), `web/src/styles.css`.
- Tests: Python unit (state, the server's gates); vitest `web/src/feedRows.test.ts`,
  `web/src/Chat.test.tsx`; UI e2e `tests/ui/test_gates.py`.

## Out of scope

- **The open gate's card and its tab in the waiting card**: the task is about answered
  gates; the open card already has its parts (question, note, reads, recommendation,
  comment field).
- **The closed question's card** (`Question.tsx`) and its recommendation line: not a
  gate; it keeps `RecommendationLine` as it is.
- **The run's page in Flows**: it shows gates by `gateTitle` and its notes, not
  `GateLine`; nothing repeats there.
- **The artifacts the gate read**: not kept as they were when it was answered (as
  today, docs/design/ui.md).
- **A stored column for the closing's event** (`gates.closed_event`): exact too, but a
  schema migration and a backfill for what one transaction already orders (design D3).
- **Remembering which closed gates are opened** across reloads: not asked; the line
  opens closed, as today.

## Impact

- The UI's closed gate line and its opened view; one new field of `GateInfo` in the UI
  server's API (`GET /api/sessions/{name}/gates`, the live feed's gate items, the
  waiting items); no CLI, MCP, schema or provider change.
