## 1. One edge for the times

- [ ] 1.1 `web/src/FeedRow.tsx`: the head draws Copy message before the time; the head
  comment says so. `web/src/styles.css`: `.feed-head > .copy-icon-button` takes
  `margin-left: auto` and `margin-right: -6px` (6 px between its icon and the time), the
  time after it no auto margin; a head without the button keeps the time's auto margin.
- [ ] 1.2 `web/src/styles.css`: `.run-event.mine` reaches 8 px past the line on both
  sides (`margin: 2px -8px`), so its time ends on the edge; its comment and ui.md's
  "8 px left of the line" follow.
- [ ] 1.3 `web/src/GateCard.tsx` (`GateLine`): the chevron first in the head, before the
  flag; `web/src/styles.css`: `.chat-gate.closed` right padding `var(--row-pad)` less the
  head's padding and border (9 px), so the gate's time ends on the edge. The rest of the
  head and the opened card unchanged.
- [ ] 1.4 `web/src/Chat.test.tsx`: the head's order (Copy message before the time), the
  gate head's order (chevron first), at the unit layer (vitest, jsdom has no layout).

## 2. Copy message on questions and answers

- [ ] 2.1 `web/src/Chat.tsx`: the closed question's `FeedRow` gets `copy` = summary, a
  blank line and the body (only the summary without one), one function beside
  `messageText`; `Answer` gets `copy` = the reply's text and comment joined by a blank line,
  none when both are empty.
- [ ] 2.2 `web/src/Question.tsx` (`Given`): the reply block's `answer-top` has
  `CopyIconButton` "Copy message" right before its time, with the same text rule, none
  when empty; `web/src/styles.css`: shown on hover of the reply block (`.question-answer`)
  or with the focus, always on a touch screen, as the other copy buttons.
- [ ] 2.3 `web/src/Chat.test.tsx`: the text each copies (a question with and without a
  body; an answer by choice with a comment, by own words, of files only, a skip with and
  without a comment) and that run lines, gates, open lines, late replies and a dismissal
  have none (AC-4, AC-5). Run `make web`.

## 3. UI tests

- [ ] 3.1 `tests/ui/test_chat.py`: a session with every row kind of AC-1; at 1200 px and
  at 390 px the times' right edges (`boundingBox`) are equal within 1 px; hovering the
  message leaves its time's box unchanged and shows Copy message left of it, the gap 6 px
  ± 1, the button 24 × 24 (AC-1, AC-2, AC-3). Screenshots of both widths as run artifacts.
- [ ] 3.2 `tests/ui/test_selection.py`: the copy tests count and find the new buttons
  (the touch-screen count), and copying a question copies its text (AC-4).
- [ ] 3.3 `tests/ui/test_gates.py`: the folded card's chevron before the flag (AC-6).

## 4. Documents

- [ ] 4.1 `docs/design/ui.md`: Copy code and Copy message (the rows that have it, before
  the time), the closed gate (chevron first), Flow events (the human's ground both sides),
  Quiet lines (every time on the right ends on one edge, nothing after it).
- [ ] 4.2 CHANGELOG.md under `## 0.43.0 (unreleased)`, `### Fixed`: the chat's times
  stand on one line; Copy message sits by the time and is also on questions and answers.

## 5. Checks

- [ ] 5.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui
  tests/ui/test_chat.py tests/ui/test_selection.py tests/ui/test_gates.py` pass;
  `openspec validate chat-time-edge --strict` passes; CI green (AC-7).
