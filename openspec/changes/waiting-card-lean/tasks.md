## 1. The failing tests

- [x] 1.1 vitest by the plan's table: `WaitingCard.test.tsx`, `Recommendation.test.tsx`,
  `Chat.test.tsx`, `Splitter.test.tsx`, `NeedsYou.test.tsx`, `Flows.test.tsx`, `tokens.test.ts`,
  `prefs.test.ts`; LAD-194's replaced tests rewritten. Run: `make web` (red). Built task by
  task, each new test seen red before its code (the server's, the tokens', the Splitter's, the
  prefs', the Recommendation's, the low chat's, the feed's room); the LAD-194 tests the code
  broke were rewritten after it, and the two written after their code (the tab's tooltip, the
  titled chips) were checked against a mutation of the code.
- [x] 1.2 UI e2e by the plan's table: `tests/ui/test_gates.py`, `test_chat.py`, `test_phone.py`,
  `test_needs_you.py`, `test_flows_tab.py`, `test_narrow_layout.py`. Run: `uv run pytest -m ui
  <files>` (red). Run red against the new card (62 failed), then rewritten to it;
  `test_narrow_layout.py` needed no change (its 601 to 900 px cases passed as they were, the
  splitter dragged up is in `test_gates.py`'s low windows), and `test_selection.py` and
  `test_connection.py` followed the card too.

## 2. The server

- [x] 2.1 `GateInfo.note_by` in `models.py` (D8), `tests/test_server_gates.py`, `make web-types`
  with `openapi.json` and `api.gen.ts` committed. Check: `uv run pytest tests/test_server_gates.py
  -n0`, `make web`.

## 3. Shared parts

- [x] 3.1 `--human-head`, `--count-ink` in `tokens.css` (D15). Check: `tokens.test.ts`.
- [x] 3.2 `Splitter`'s `hint` (D6); the card's edge passes `false`. Check: `Splitter.test.tsx`.

## 4. The card's layout

- [x] 4.1 `CardHead`, the report `.waiting-scroll`, the footer's line; the meta and "↓ more" out
  (D1, D3). Check: the head and fade tests.
- [x] 4.2 The card at most 50 % of the chat, only the report giving way to 56 px; the human's
  height with the head in `--waiting-rest` (D2). Check: the height tests. Built with the limit
  on the report (design.md, D2, Built).

## 5. The recommendation

- [x] 5.1 One `Recommendation` block in every place, `asked` / `missing`, disagreement by frame,
  ⚠ and aria-label; `RecommendationBar` and `oneLine` out (D4). Check: `Recommendation.test.tsx`.
- [x] 5.2 The recommendation's splitter and its stored height (D5). Check: drag, keys, reset,
  reload, absent cases.

## 6. Tabs, chips, note

- [x] 6.1 A gate's tab: tooltip of step and author, width (D7). Check: the tab tests.
- [x] 6.2 One row of titled chips, no "It reads", no size (D9); the note without its band (D10).
  Check: the chip tests, Needs you's chip.

## 7. Fields, questions, composer

- [x] 7.1 Fields 1 to 8 lines, 40 / 44 px, the placeholders (D11). Check: the field tests.
- [x] 7.2 Skip as a pill, a question without choices, lines between questions (D12). Check: the
  question tests.
- [x] 7.3 The composer folds only on a phone (D13). Check: the fold tests.

## 8. Places

- [x] 8.1 Needs you's whole card (D14). Check: `test_needs_you.py`.
- [x] 8.2 Flows' run page: head with the kicker, note, chips, whole; no gate title (D14). Check:
  `test_flows_tab.py`, `Flows.test.tsx`.
- [x] 8.3 The phone: 2-line box, 24 px splitter, hidden while typing, 44 px targets. Check:
  `test_phone.py`.

## 9. Docs and regression

- [x] 9.1 `docs/design/ui.md` (the sections the plan's Task 12 names) and CHANGELOG.md
  (`0.46.0 (unreleased)`, one item under Improved). Check: read against the code.
- [x] 9.2 The regression run of the plan and screenshots of each place at 1440, 768, 390, light and
  dark as run artifacts. Check: all green; `openspec validate waiting-card-lean --strict` and the
  trial archive pass. Screenshots: run artifact `screenshots.html` (24: the chat's gate and
  questions, Needs you, a run's page).
