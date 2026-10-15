## 1. The splitter's horizontal edge

- [x] 1.1 `web/src/Splitter.tsx`: `edge: "top"` beside `"left" | "right"`: a horizontal
  separator above its block (`aria-orientation="horizontal"`, `row-resize`, the pointer's
  y; moving it up makes the block taller), ↑ / ↓ by `STEP`, the double click to
  `bounds.initial`, the grip laid out in a row; its value is the block's height. The
  columns' splitters unchanged. `web/src/styles.css`: `.splitter-top` (8 px high, the
  2 px line on hover and focus, the grip's dots in a row), hidden at 900 px or less with
  the other splitters. Check: `Splitter.test.tsx` cases for the top edge (keys, double
  click, a pointer drag by y, bounds) next to the left and right ones; `make web`.

## 2. Remembered in the browser

- [x] 2.1 `web/src/prefs.ts`: the card's height (`lado.waitingHeight`, one value, pixels;
  none stored means the default, half the chat) with its least height named
  (`WAITING_MIN`, measured once: the head, two lines of the list and the Send row, about
  150 px), and the minimized tabs per session (`lado.waitingMinimized.<session>`, a JSON
  list of tab keys; read, store, drop), both through the existing `read` / `write`
  guards. Check: `prefs.test.ts` cases (stored and read back, a broken or missing value
  gives the default, storage that throws changes nothing).

## 3. The card

- [x] 3.1 `web/src/icons.tsx`: `MinimizeIcon` (a line) and `RestoreIcon` (a window), in
  the icons' stroke style. `web/src/WaitingCard.tsx`: a prop that says the card is in a
  session's chat (Needs you passes none); there, "Minimize the card" / "Restore the
  card" (Tooltip, `aria-pressed` or `aria-expanded` as the expand button does) left of
  the expand icon. Minimized: the tabs, no tab marked shown, and one button-line with
  the shown tab's first item's question (`.waiting-line`, muted, one line, ellipsis) in
  place of the panel; a click on the line, the icon or a tab restores (a tab shows
  itself). The minimized state is "every tab key is in the stored set" (design decision
  in proposal.md); minimize stores the current keys, restore drops them; a new tab
  restores with no extra event. Expand from minimized shows the whole card; folding the
  expanded card brings it back minimized. Focus: after minimize on "Restore the card",
  after restore on "Minimize the card". Check: `WaitingCard.test.tsx` cases: minimize
  and restore by the icon, the line and a tab; no answer buttons while minimized; a new
  gate restores and keeps the shown tab; a question added to a tab does not restore; the
  stored keys survive a remount; expand and fold from minimized; no icon on Needs you
  (`NeedsYou.test.tsx`).
- [x] 3.2 The edge: in the chat (`Chat.tsx` or the card, whichever owns the room) a
  `Splitter edge="top"` right above the card, its height from `prefs.ts`, bounded by
  `WAITING_MIN` and the chat's height less the feed's 160 px (measured with `useWidth`'s
  kind of observer for height, or a new `useHeight` in `Splitter.tsx`); the card's
  `max-height: 50%` stays only for the default. A drag below `WAITING_MIN` minimizes and
  keeps the stored height. A chat too short shows the card lower (`fitWidth`'s rule for
  heights), the stored height kept. No edge while minimized or expanded, on Needs you,
  or at 900 px or less. Check: `WaitingCard.test.tsx` / `Chat.test.tsx` cases for the
  bounds and the minimize-on-drag; then the e2e tests (4.1).

## 4. Tests in the browser

- [x] 4.1 `tests/ui/test_chat.py`: a gate in a session's chat at 1400×900: minimize (the
  line holds the gate's question, no Approve / Reject, the feed's box is taller), reload
  (still minimized), restore by the line; a second gate opening restores it (AC-1 to
  AC-3); expand from minimized and Esc (AC-4); drag the edge to 230 px (the card's box
  height ± 2 px), reload, then another session's chat (AC-5); double click (half the
  chat ± 2 px); drag to the bottom (minimized, AC-6); at 800×900 no separator and
  minimize works (AC-7); Needs you has no minimize icon nor separator (AC-8). A
  screenshot of minimized, resized and the narrow window, light and dark. Check: `uv run
  pytest -m ui tests/ui/test_chat.py`.

## 5. Docs

- [x] 5.1 `docs/design/ui.md`, The waiting card: Height (the edge, its bounds and memory,
  one value for every session; none on a narrow window or Needs you), Minimize (the icon
  pair, the line, what restores it, the stored tab keys), decided 2026-10-14, LAD-54,
  mockup `task/lad-54/mockup-gate-card.html` (screens 2, 2a, D); and in Structure or
  Look the splitter's horizontal edge. Check: read through against the code.
- [x] 5.2 `CHANGELOG.md` under `## 0.39.0 (unreleased)`: a line: in a session's chat the
  waiting card can be minimized to one line (it comes back by itself when something new
  waits) and resized by dragging its top edge, both remembered in the browser.

## 6. Regression

- [x] 6.1 `make web` (vitest, tsc, build; no API change, so no stale types), `make lint`,
  `uv run pytest -m ui tests/ui/test_chat.py tests/ui/test_needs_you.py
  tests/ui/test_gates.py tests/ui/test_terminal_panel.py tests/ui/test_artifacts_tab.py
  tests/ui/test_session_list.py` (the card, Needs you, gates and the other splitters),
  `openspec validate waiting-card-minimize-resize --strict` (AC-9).
