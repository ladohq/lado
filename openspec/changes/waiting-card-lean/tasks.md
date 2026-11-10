## 1. The failing tests

- [ ] 1.1 vitest by the plan's table: `WaitingCard.test.tsx`, `Recommendation.test.tsx`,
  `Chat.test.tsx`, `Splitter.test.tsx`, `NeedsYou.test.tsx`, `Flows.test.tsx`, `tokens.test.ts`,
  `prefs.test.ts`; LAD-194's replaced tests rewritten. Run: `make web` (red).
- [ ] 1.2 UI e2e by the plan's table: `tests/ui/test_gates.py`, `test_chat.py`, `test_phone.py`,
  `test_needs_you.py`, `test_flows_tab.py`, `test_narrow_layout.py`. Run: `uv run pytest -m ui
  <files>` (red).

## 2. The server

- [ ] 2.1 `GateInfo.note_by` in `models.py` (D8), `tests/test_server_gates.py`, `make web-types`
  with `openapi.json` and `api.gen.ts` committed. Check: `uv run pytest tests/test_server_gates.py
  -n0`, `make web`.

## 3. Shared parts

- [ ] 3.1 `--human-head`, `--count-ink` in `tokens.css` (D15). Check: `tokens.test.ts`.
- [ ] 3.2 `Splitter`'s `hint` (D6); the card's edge passes `false`. Check: `Splitter.test.tsx`.

## 4. The card's layout

- [ ] 4.1 `CardHead`, the report `.waiting-scroll`, the footer's line; the meta and "↓ more" out
  (D1, D3). Check: the head and fade tests.
- [ ] 4.2 The card at most 50 % of the chat, only the report giving way to 56 px; the human's
  height with the head in `--waiting-rest` (D2). Check: the height tests.

## 5. The recommendation

- [ ] 5.1 One `Recommendation` block in every place, `asked` / `missing`, disagreement by frame,
  ⚠ and aria-label; `RecommendationBar` and `oneLine` out (D4). Check: `Recommendation.test.tsx`.
- [ ] 5.2 The recommendation's splitter and its stored height (D5). Check: drag, keys, reset,
  reload, absent cases.

## 6. Tabs, chips, note

- [ ] 6.1 A gate's tab: tooltip of step and author, width (D7). Check: the tab tests.
- [ ] 6.2 One row of titled chips, no "It reads", no size (D9); the note without its band (D10).
  Check: the chip tests, Needs you's chip.

## 7. Fields, questions, composer

- [ ] 7.1 Fields 1 to 8 lines, 40 / 44 px, the placeholders (D11). Check: the field tests.
- [ ] 7.2 Skip as a pill, a question without choices, lines between questions (D12). Check: the
  question tests.
- [ ] 7.3 The composer folds only on a phone (D13). Check: the fold tests.

## 8. Places

- [ ] 8.1 Needs you's whole card (D14). Check: `test_needs_you.py`.
- [ ] 8.2 Flows' run page: head with the kicker, note, chips, whole; no gate title (D14). Check:
  `test_flows_tab.py`, `Flows.test.tsx`.
- [ ] 8.3 The phone: 2-line box, 24 px splitter, hidden while typing, 44 px targets. Check:
  `test_phone.py`.

## 9. Docs and regression

- [ ] 9.1 `docs/design/ui.md` (the sections the plan's Task 12 names) and CHANGELOG.md
  (`0.46.0 (unreleased)`, one item under Improved). Check: read against the code.
- [ ] 9.2 The regression run of the plan and screenshots of each place at 1440, 768, 390, light and
  dark as run artifacts. Check: all green; `openspec validate waiting-card-lean --strict` and the
  trial archive pass.
