## 1. The failing tests

- [x] 1.1 vitest by the plan's table: `WaitingCard.test.tsx`, `Recommendation.test.tsx`,
  `Chat.test.tsx`, `Composer.test.tsx`, `fieldHeight.test.tsx`. Run: `make web`.
- [x] 1.2 UI e2e by the plan's table: `tests/ui/test_gates.py`, `test_chat.py`, `test_phone.py`,
  `test_needs_you.py`, the tests of the old list replaced. Run: `uv run pytest -m ui <files>`.

## 2. The parts

- [x] 2.1 `waitingParts.tsx`: `CardTop`, `CardContext`, `CardFoot`; `GatePanel` and `AgentPanel`
  use them, `.waiting-context` and `.waiting-foot` in `styles.css` (D1, D5, D6). Check: the
  long-note tests.
- [x] 2.2 The 40 % limit and the order of giving way (D2, D4). Check: heights, the 420 px chat,
  Needs you.
- [x] 2.3 The human's height on the top (D3). Check: the edge's tests.

## 3. The footer

- [x] 3.1 `RecommendationBar`, `oneLine`, opened and expanded (D7). Check:
  `Recommendation.test.tsx`, the disagreeing gate.
- [x] 3.2 The card's fields 1 to 4, 8 expanded; Flows as it was (D8). Check: field tests.
- [x] 3.3 Choices in the foot, their area, ✓, radius; several questions in the context (D13).
  Check: 4 and 6 rows, three questions.
- [x] 3.4 Skip question (spec "Skip question opens its comment and Send sends it"). Check: the
  renamed tests.
- [x] 3.5 Send's tooltip and the stopped note (D12). Check: the tooltip test.

## 4. The composer

- [x] 4.1 The fold: `onFold`, `ComposerFold`, `folded`, closing and the quote (D9). Check:
  `Chat.test.tsx`, the quote's UI test.
- [x] 4.2 Drafts (D10). Check: Other… and back.

## 5. The phone

- [x] 5.1 `typing` in place of LAD-126's expansion (D11). Check: `test_phone.py` at 440 px.
- [x] 5.2 The flaky test: reproduce or say why not, replace it, BACKLOG.md's entry out (D15).
  Check: the new test 5 times in a parallel run.
- [x] 5.3 44 px targets, the choices' 148 px (D14). Check: the measuring test.

## 6. Documents and the round

- [x] 6.1 `docs/design/ui.md` (The waiting card, Flow gates, Phone layout), the card's header
  comments, CHANGELOG.md. Check: read against the code.
- [x] 6.2 The regression run of the plan, whole `make test-ui`, screenshots in both themes as run
  artifacts; the real iOS keyboard named "not verified" in the build report.
- [x] 6.3 ui-review C1–C4 (#3551, D16): the footer in a 768 window, placeholders, a phone's tabs,
  the opened recommendation's fade. Check: `test_a_window_768_wide…`, `test_a_placeholder…`,
  `test_a_gates_and_a_questions_tabs…`, `test_an_opened_recommendation…`.
- [x] 6.4 The human's iPhone check: Needs you is a whole card, no Expand (D17, #3637). Check:
  `test_a_long_note_on_needs_you_is_whole…`, `test_on_needs_you_a_field_in_focus_is_seen…`.
