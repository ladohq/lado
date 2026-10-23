Task: LAD-136

## Why

Symptom: in the session's chat the times do not stand on one vertical line. A message's
time stands 32 px left of the time of a run's event lines, whether the pointer is over the
message or not; the time of the human's own move in a run's group stands 8 px left of
them, and a closed gate's time about 37 px left. The human also sees the copy button only
on some rows (mostly the supervisor's messages) and asked which rows should have it, and
why it is there at all.

Cause (read in the code, measured in the mockups on the UI's own styles):
- `FeedRow` (`web/src/FeedRow.tsx`) puts Copy message in the head **after** the time.
  The button is hidden with `opacity: 0` until hover, so it keeps its 24 px and the head's
  8 px gap on every message: every message's time is pushed 32 px left. On a touch screen
  it is always shown, an icon beside every message's time.
- `.run-event.mine` (`web/src/styles.css`) puts the human's line on its ground with
  `margin-left: -8px` and 8 px padding: the ground grows left only, so its time moves 8 px
  in from the right.
- The closed gate's head (`GateLine`, `.gate-head`) has the chevron after the time, inside
  its frame's 8 px padding and 1 px border.
- Copy message is on every row drawn by `Message` (an agent's message to the human, the
  agents' messages to each other, the human's message) and on no other row. The
  supervisor simply writes to the human most often.

Why Copy message at all (LAD-67, kept): messengers (Slack, Discord, Teams, Telegram) copy
by selection or a message menu; chat applications with a model (ChatGPT, Claude.ai) put a
copy button on each answer, as an answer is a result to carry elsewhere. LADO's agents'
messages are such results (reports, designs), and the selection cannot replace the button:
it copies the rendered text without the Markdown (lists, code fences, links), and cannot
reach the part of a long message folded under Show more. A question is short and never
folded, and the human's answer is their own text: neither gets the button.

Options weighed (mockups `mockup-chat-times.html` and `mockup-gate-phone.html` of the
run):
- A (taken, the human's choice): one edge. Every time on the right of a row ends on the
  right edge of the text column. Copy message stands right before the time, close to it,
  and keeps no room after it; the closed gate's chevron moves to the head's start, as the
  chevron of an agents' folded message stands; the gate's frame and the human's ground
  reach past the edge by their own padding, so their times end on it too. Only CSS and a
  reorder in two components; nothing reserved on rows with no action.
- B: a column of 32 px for actions at the right of every row; every time ends on its left
  side. Nothing moves, but every line loses 32 px, the times leave the edge, and the column
  stays empty on most rows; each new row kind must remember to reserve it.

## What Changes

- Every time on the right of a chat row ends on one vertical line; showing or hiding Copy
  message moves no time.
- Copy message stands right before the head's time, with a 6 px gap between the icon and
  the digits (its 24 px hit area unchanged), shown on hover as today; a continued row keeps
  it at its top right.
- On a touch screen Copy message is not shown (the selection copies there); Copy code
  stays always shown.
- The closed gate's chevron stands at the head's start, before the flag; the frame reaches
  past the edge so its time ends on it.
- The human's own lines of a run's group stand on a ground that reaches 8 px past the line
  on both sides (was: the left only).
- `docs/design/ui.md`, the living specs `selection-actions` and `closed-gate-card`, and a
  new capability `chat-feed-times`.
- CHANGELOG.md under `## 0.43.0 (unreleased)`.

## Scope

`web/src/FeedRow.tsx`, `web/src/GateCard.tsx` (`GateLine`), `web/src/styles.css`, their
unit tests, `tests/ui/test_chat.py`, `tests/ui/test_selection.py`, `tests/ui/test_gates.py`,
`docs/design/ui.md`, CHANGELOG.md.

## Out of scope

- Copy message on a closed question and on the human's answer: a question is short and
  never folded, an answer is the human's own text; the selection covers both (the human's
  choice, round 2).
- Copy message on lines of runs, gates, open questions and late replies, and on a
  dismissal's line: LADO's one-line records, not a text someone wrote to carry elsewhere.
- Removing Copy message: the selection loses the Markdown and the folded part of a long
  message.
- Times inside a card (the reply block of a question's card, an opened gate's answer, a
  recommendation's line): they end on their card's own padding, not on the feed's edge;
  aligning them would need the cards to change their frames.
- A continued row's time, which stands in the avatar's column on the left: it has no
  neighbour on the right to line up with.
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
- AC-4: On a touch screen (390 px, touch) no message shows Copy message, every code block
  shows Copy code, and the messages' times stand on the edge of AC-1 (UI test).
- AC-5: Closed questions, the human's answers, run lines, gates, open lines, late replies'
  lines and a dismissal's line have no Copy message, as today.
- AC-6: The closed gate's card shows the chevron before the flag, turning as before; its
  accessible name and keyboard behaviour stay.
- AC-7: `make lint`, `make test`, `make web`, `uv run pytest -m ui` of the changed UI
  test files pass; `openspec validate chat-time-edge --strict` passes; CI green.

## Impact

- Web UI only: no API, schema, MCP or CLI change. Patch level (a layout fix); it ships in
  `0.43.0 (unreleased)`, no version bump here.
- Living specs: `selection-actions` ("Messages have a Copy message button" and "Code
  blocks and messages have copy buttons shown on hover" modified), `closed-gate-card` ("A
  closed gate is a folded card that says it opens" modified), a new capability
  `chat-feed-times`.
