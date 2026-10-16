## 1. The comment once (D1)

- [ ] 1.1 `web/src/GateCard.tsx`: `GateLine` without `.gate-comment`; `web/src/styles.css`:
  the `.gate-comment` rule removed. Check: vitest of 3.1 (the line without the comment;
  the move keeps it).

## 2. The opened card (D2, D3)

- [ ] 2.1 `web/src/Chat.tsx`: `moveOf(gate, events)` next to `gateOf` (the first `flow`
  event whose `gateOf` is the gate); `Rows` passes the gate's move and the run's flow
  states to `GateLine`. Check: vitest in `web/src/feedRows.test.ts` (a move found; none
  for an override or a cancel; another run's move not taken).
- [ ] 2.2 `web/src/GateCard.tsx`: the opened card `.gate-closed-card` in D2's order: the
  question; the answer plaque `.gate-answer` (mini avatar, who, `OutcomeChip` and "→
  <state>" with a move, else the answer word; time; the comment as `Body breaks`); the
  folded **Note** line (`<details>`, summary + "· N artifacts", body as `Preview` of
  `CLOSED_NOTE_LINES = 6`, `Attachments short`); the folded **Supervisor** line
  ("recommended <option>", "· you agreed" / "· you answered otherwise", the lead's
  disagreement in orange; its text opened). The card stays a quote area of its session
  (`quoteArea`, selection-actions). `web/src/styles.css`: `.gate-closed-card`,
  `.gate-answer`, the folded lines' rules, after the mockup
  `task/lad-85/mockup-gate-expanded.html`, light and dark by the tokens. Check: vitest
  of 3.1; `make web`.

## 3. Tests

- [ ] 3.1 `web/src/Chat.test.tsx`: replace "a closed gate is a line with its answer and
  comment…" and "a closed gate opened shows the recommendation as one quiet line…" with
  tests of the delta's scenarios: The human rejects with a comment (one copy, under the
  move); A gate closed otherwise (no reason under the line; on the cancel's line); A long
  note (30 lines, 2 artifacts: folded, then 6 lines, Show more, 2 chips); The
  recommendation folded; The answer agreed; Nothing to fold; Closed by an agent; the
  card still has no textbox, no option buttons and no reads. Check: `make web`.
- [ ] 3.2 `tests/ui/test_gates.py`: in the reject test the line no longer contains "split
  the form first", the move does; opening the line shows the question and the plaque
  with the comment, the Note line folded, then opened (`shot` of the line, the card, the
  opened note). Check: `uv run pytest -m ui tests/ui/test_gates.py`.
- [ ] 3.3 The tests catch the bug: 3.1's one-copy test fails on main's `GateCard.tsx`
  (a temporary checkout of that file, restored after); name the run in the build report.

## 4. Docs

- [ ] 4.1 `docs/design/ui.md` (Flow gates: "A closed gate is a quiet line…": the title and
  time without the comment; the opened card of D2; LAD-85, mockups
  `task/lad-85/mockup-gate-comment.html`, `task/lad-85/mockup-gate-expanded.html`);
  CHANGELOG.md, a line under `## 0.40.0 (unreleased)`.

## 5. Regression

- [ ] 5.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_gates.py
  tests/ui/test_chat.py`, `openspec validate closed-gate-card --strict`,
  `openspec validate --specs --strict`.
