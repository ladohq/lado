Task: LAD-54

## Why

While a gate (or a question) waits for the human, a session's chat shows the waiting card
between the feed and the composer, at most half the chat's height, and always open: the
human cannot make it smaller, only expand it over the whole chat
(`web/src/styles.css`, `.waiting-card { max-height: 50% }`; `WaitingCard.tsx`). The human
often holds a gate open on purpose to talk it over with the supervisor first (the task's
screenshot: a merge gate of run task/lad-52, the human asking the supervisor about the
report): each reply of the supervisor is then read in what is left of the feed, about
300 px of an 800 px window, while the gate's question, note and buttons, which the human
already read, keep the other half.

The root cause is the card's size, not the flow: a run at a gate already stands still
until the human answers, so pausing the run would free no room on the screen.

## What Changes

- **Minimize the card** (approved mockup `mockup-gate-card.html`, screens 2 and 2a: the
  pair of icons). In a session's chat the card's head gets a second icon button left of
  the expand icon, in the same style: "Minimize the card" (a line, —). Minimized, the
  card is its tabs and one line under them on the "waits for you" ground: the shown tab's
  first item's question (a gate's question, or the agent's first open question), muted,
  cut with an ellipsis, with no answer buttons and no comment field; the icon turns into
  "Restore the card" (a window, ▭). A click on that icon, on the line or on any tab
  restores the card (a tab also shows itself). The expand icon stays and works from the
  minimized card too.
- **Something new restores it.** The card stays minimized while what waits is the same
  or less; when a new tab comes (a new gate, or an agent with no tab before asks), it
  restores itself. A question added to a tab that is there already does not restore it:
  the tab's count says so.
- **Remembered in the browser** per session, across reloads, until something new comes
  or the human restores it.
- **Resize the card** (mockup screen D). In a session's chat, the edge between the feed
  and the card is a splitter, the UI's shared one (`Splitter.tsx`) learning a horizontal
  edge: drag it up or down (cursor ↕, the blue line on hover and focus, a small grip in
  its middle), ↑ / ↓ on the focused edge by steps, a double click back to the default
  height (half the chat, as now). The height the human chose is remembered in this
  browser, one value for every session, as the columns' widths are; a chat too short for
  it shows the card lower, keeping the feed's least height (160 px), without forgetting
  the chosen height. Dragging the edge down to the card's least height and past it
  minimizes the card.
- Needs you, the expanded card, the counts and notifications are as they are now.
- docs/design/ui.md (The waiting card) and CHANGELOG.md say so.

## Scope

The waiting card in a session's Activity chat in the web UI: two new controls (minimize
and the edge), their memory in the browser, and the shared splitter's horizontal edge.

## Out of scope

- Pausing a flow run (the task's second idea): a run at a gate already waits for the
  human, so a pause frees no room; stopping everything is the session's Stop. A pause of
  a run whose agent works is a new state of the core (schema, MCP, CLI, UI): a task of its
  own if wanted.
- The card beside the feed on a wide window (option C): it shares the width with the
  terminal panel and the artifact panel, and the narrow window would still need this
  change; the human chose a small change.
- Minimizing by a click on the shown tab (option 1): the human chose the pair of icons.
- Minimizing on its own when the human sends a message (option B): a card that goes away
  by itself surprises; one click does it.
- "Snooze the gate" in the core (option E): out of Needs you and notifications until a
  time; another need (not being reminded), and a schema change.
- Minimizing or resizing on Needs you: there the card is the page's content.
- Answer buttons on the minimized line: the human answers after reading the gate again.
- The edge on a narrow window (900 px or less): the page scrolls there and has no
  splitters (as the columns'); minimizing works there.

## Acceptance criteria

- AC-1: In a session's chat with a gate open, the card's head has "Minimize the card"
  left of "Expand the card"; after a click the card is its tabs and one line with the
  gate's question, no Approve / Reject and no comment field, and the feed takes the
  room; the icon is now "Restore the card".
- AC-2: A click on "Restore the card", on the line or on a tab brings the whole card back
  at the height it had; a tab clicked is the one shown.
- AC-3: A minimized card stays minimized after a reload of the page; when a new gate
  opens or an agent without a tab asks the human, it restores itself with its tabs as
  before (the shown tab the human's choice).
- AC-4: A minimized card can be expanded with the expand icon; folding the expanded card
  brings it back minimized.
- AC-5: Dragging the edge above the card changes its height between its least height and
  the chat's height less the feed's 160 px; ↑ / ↓ on the focused edge change it by steps;
  a double click gives half the chat; the height stays after a reload and in another
  session's chat.
- AC-6: Dragging the edge down past the card's least height minimizes the card.
- AC-7: In a window of 900 px or less there is no edge; minimizing works.
- AC-8: Needs you shows its cards as before: no minimize icon and no edge there.
- AC-9: docs/design/ui.md and CHANGELOG.md say so; the new vitest and UI e2e tests pass,
  and the existing tests of the card, the splitters and the chat pass.

## Impact

- `web/src/WaitingCard.tsx`, `web/src/Splitter.tsx`, `web/src/prefs.ts`,
  `web/src/icons.tsx`, `web/src/Chat.tsx` (the edge's place), `web/src/styles.css`;
  their vitest files; `tests/ui/test_chat.py`; `docs/design/ui.md`; CHANGELOG.md.
- No API, schema, MCP or CLI change: a UI change of the patch kind, listed under the
  unreleased `0.39.0`.

## Decisions for the record

- Scale tweak: two controls of a known shape on one card, UI only; review as a tweak.
- The minimized state is kept as the set of tab keys that were there when the human
  minimized (`lado.waitingMinimized.<session>` in localStorage through `prefs.ts`): the
  card is minimized while every tab it shows is in that set, so a new tab restores it
  with no event to watch, and a restore drops the key. One source: the tabs themselves.
- The height is one value for every session (`lado.waitingHeight`, pixels), as the
  columns' widths are: the window, not the session, decides what fits. No stored value
  means today's default, half the chat.
- The shared `Splitter` gets `edge: "top"` (horizontal: `aria-orientation="horizontal"`,
  `row-resize`, ↑ / ↓, the pointer's y) rather than a second component: one splitter for
  every resizable edge (its own comment's rule).
- The card's least height while resizing is its head, the Send row and two lines of its
  list (about 150 px; the developer measures it once and names it in `prefs.ts`); below
  it a drag minimizes, so there is no unusable height between the two.
- The minimized line shows the shown tab's first item: what the human was looking at.
- Tests: vitest for the state rules (minimize, restore by icon, line and tab, a new tab
  restores, a question added to a tab does not, stored and read back; Splitter's top
  edge by keys and pointer; the height's bounds), and the UI e2e layer for what needs a
  layout (the drag in Chromium, the reload, the narrow window, Needs you, screenshots).
  No integration test: nothing crosses a process.
