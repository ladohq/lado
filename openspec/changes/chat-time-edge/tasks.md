## 1. One edge for the times

- [x] 1.1 `web/src/FeedRow.tsx`: the head draws Copy message before the time; the module
  comment says so. `web/src/styles.css`: `.feed-head > .copy-icon-button` takes
  `margin-left: auto` and `margin-right: -6px` (6 px between its icon and the time), the
  time right after it no auto margin; a head without the button keeps the time's auto
  margin.
- [x] 1.2 `web/src/styles.css`: under `@media (hover: none)` Copy message is not shown
  (`.feed-row .copy-icon-button`, `.agent-messages .copy-icon-button`: `display: none`)
  and the head's time takes its auto margin back; Copy code stays always shown. The
  comment over the copy buttons' rules says so.
- [x] 1.3 `web/src/styles.css`: `.run-event.mine` reaches 8 px past the line on both
  sides (`margin: 2px -8px`), so its time ends on the edge; its comment follows.
- [x] 1.4 `web/src/GateCard.tsx` (`GateLine`): the chevron first in the head, before the
  flag; `web/src/styles.css`: `.chat-gate.closed` right padding `var(--row-pad)` less the
  head's padding and border (9 px), so the gate's time ends on the edge. The rest of the
  head and the opened card unchanged.
- [x] 1.5 `web/src/Chat.test.tsx`: the head's order (Copy message before the time) and
  the gate head's order (chevron first), at the unit layer (vitest; jsdom has no layout,
  so no positions here). Run `make web`.

## 2. UI tests

- [ ] 2.1 `tests/ui/test_chat.py`: a session with every row kind of AC-1; at 1200 px and
  at 390 px the times' right edges (`bounding_box`) are equal within 1 px; hovering the
  message leaves its time's box unchanged and shows Copy message left of it, the gap 6 px
  ± 1, the button 24 × 24 (AC-1, AC-2, AC-3, AC-5). Screenshots of both widths as run
  artifacts.
- [ ] 2.2 `tests/ui/test_selection.py`: `test_copy_buttons_always_show_on_a_touch_screen`
  becomes the touch rule of AC-4 (Copy code shown, no Copy message, the time on the edge);
  the hover test keeps passing with the new order.
- [ ] 2.3 `tests/ui/test_gates.py`: the folded card's chevron before the flag, its turn on
  open (AC-6).

## 3. Documents

- [ ] 3.1 `docs/design/ui.md`: Copy code and Copy message (before the time; not on a touch
  screen, and why the button is there: Markdown and folded text), the closed gate (chevron
  first), Flow events (the human's ground 8 px past the line on both sides), Quiet lines
  (every time on the right ends on one edge, nothing after it).
- [ ] 3.2 CHANGELOG.md under `## 0.43.0 (unreleased)`, `### Fixed`: the chat's times
  stand on one line; Copy message sits by the time and is not shown on a touch screen.

## 4. Checks

- [ ] 4.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui
  tests/ui/test_chat.py tests/ui/test_selection.py tests/ui/test_gates.py` pass;
  `openspec validate chat-time-edge --strict` passes; CI green (AC-7).
