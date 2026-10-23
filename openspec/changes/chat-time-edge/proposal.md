Task: LAD-136

## Why

Symptom: in the session's chat the times do not stand on one vertical line. A message's
time stands 32 px left of the time of a run's event lines, whether the pointer is over the
message or not; the time of the human's own move in a run's group stands 8 px left of
them, and a closed gate's time about 37 px left. The human also sees the copy button only
on some rows (mostly the supervisor's messages) and asked which rows should have it.

Cause (read in the code, measured in the mockup on the UI's own styles):
- `FeedRow` (`web/src/FeedRow.tsx`) puts Copy message in the head **after** the time.
  The button is hidden with `opacity: 0` until hover, so it keeps its 24 px and the head's
  8 px gap on every message: every message's time is pushed 32 px left.
- `.run-event.mine` (`web/src/styles.css`) puts the human's line on its ground with
  `margin-left: -8px` and 8 px padding: the ground grows left only, so its time moves 8 px
  in from the right.
- The closed gate's head (`GateLine`, `.gate-head`) has the chevron after the time, inside
  its frame's 8 px padding and 1 px border.
- Copy message is on every row drawn by `Message` (an agent's message to the human, the
  agents' messages to each other, the human's message) and on no other row: not on a
  closed question's row, nor on the human's answer to a question. The supervisor simply
  writes to the human most often.

Options weighed (mockup `mockup-chat-times.html` of the run):
- A (taken, the human's choice): one edge. Every time on the right of a row ends on the
  right edge of the text column. Copy message stands right before the time, close to it,
  and keeps no room after it; the closed gate's chevron moves to the head's start, as the
  chevron of an agents' folded message stands; the gate's frame and the human's ground
  reach past the edge by their own padding, so their times end on it too. Only CSS and a
  reorder in two components; nothing reserved on rows with no action.
- B: a column of 32 px for actions at the right of every row; every time ends on its left
  side. Nothing moves, but every line loses 32 px, the times leave the edge, and the column
  stays empty on most rows; each new row kind must remember to reserve it.

Copy message, by the human's choice: on every row with a text someone wrote: the messages
as today, a closed question (its summary and body), the human's answer to a question (its
text and its comment). Lines of runs, gates, open questions' and late replies' lines and a
dismissal's line keep none: they are LADO's own one-line records.

## What Changes

- Every time on the right of a chat row ends on one vertical line; showing or hiding Copy
  message moves no time.
- Copy message stands right before the head's time, with a 6 px gap between the icon and
  the digits (its 24 px hit area unchanged), shown on hover as today; a continued row keeps
  it at its top right.
- The closed gate's chevron stands at the head's start, before the flag; the frame reaches
  past the edge so its time ends on it.
- The human's own lines of a run's group stand on a ground that reaches 8 px past the line
  on both sides (was: the left only).
- Copy message also on a closed question's row and on the human's answer to a question
  (its own row, and the reply block in the question's card).
- `docs/design/ui.md`, the living specs `selection-actions` and `closed-gate-card`, and a
  new capability `chat-feed-times`.
- CHANGELOG.md under `## 0.43.0 (unreleased)`.

## Scope

`web/src/FeedRow.tsx`, `web/src/Chat.tsx` (`Message`, `Answer`, the closed question's
row), `web/src/Question.tsx` (the reply block), `web/src/GateCard.tsx` (`GateLine`),
`web/src/styles.css`, their unit tests, `tests/ui/test_chat.py`, `tests/ui/test_selection.py`,
`tests/ui/test_gates.py`, `docs/design/ui.md`, CHANGELOG.md.

## Out of scope

- Times inside a card (the reply block of a question's card, an opened gate's answer, a
  recommendation's line): they end on their card's own padding, not on the feed's edge;
  aligning them would need the cards to change their frames.
- A continued row's time, which stands in the avatar's column on the left: it has no
  neighbour on the right to line up with.
- Copy message on lines of runs, gates, open questions and late replies, and on a
  dismissal's line: LADO's one-line records, not a text someone wrote to copy.
- Copy message on an agent's page (Agents): it already has it on every message; its list
  has no times to line up in one column with other rows.
- Option B (a reserved column): see Why.

## Acceptance criteria

- AC-1: In a chat of 1200 px and of 390 px with a message, a message continuing it, a
  closed question, the human's answer row, a run's group with an agent's line and the
  human's own line, a closed gate, an open gate's line and a late reply's line, the right
  edges of the times on the right of each row are equal within 1 px (UI test).
- AC-2: Moving the pointer over a message shows Copy message and moves no time (the time's
  box is the same before and during the hover; UI test).
- AC-3: Copy message stands left of the head's time, the gap between the button's icon
  and the time 6 px ± 1; its button stays 24 × 24 px.
- AC-4: A closed question's row has Copy message, which copies the summary, a blank line
  and the body (only the summary without a body); the human's answer row and the reply
  block in a question's card have it, copying the text, a blank line and the comment (only
  the one there is); an answer of files only and a skip without a comment have none.
- AC-5: Run lines, gates, open lines, late replies' lines and a dismissal's line have no
  Copy message.
- AC-6: The closed gate's card shows the chevron before the flag, turning as before; its
  accessible name and keyboard behaviour stay.
- AC-7: `make lint`, `make test`, `make web`, `uv run pytest -m ui` of the changed UI
  test files pass; `openspec validate chat-time-edge --strict` passes; CI green.

## Impact

- Web UI only: no API, schema, MCP or CLI change. On its own patch level (a layout fix
  with a small addition); it ships in `0.43.0 (unreleased)`, no version bump here.
- Living specs: `selection-actions` ("Messages have a Copy message button" modified),
  `closed-gate-card` ("A closed gate is a folded card that says it opens" modified), a new
  capability `chat-feed-times`.
