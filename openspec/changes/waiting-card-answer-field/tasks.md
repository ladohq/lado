## 1. One height rule for text fields (D1, D2)

- [x] 1.1 Take the composer's `grow` out of `Composer.tsx` into a module of its own,
  with the least and the most lines as arguments, and a hook that applies it on each
  change of the text; the composer uses it with 1 and 8 lines and behaves as before.
  Check: vitest of the rule (a stubbed `scrollHeight`: least, between, most and scroll),
  `cd web && npx vitest run Composer` unchanged.
- [x] 1.2 Keep in view (D3): when the field has the focus and grew, bring its lower edge
  into view. Check: vitest that `scrollIntoView` is called with `block: "nearest"` only
  for a focused field that grew.

## 2. The card's fields (D4)

- [x] 2.1 `WaitingCard.tsx`'s own answer and Skip comment, and `GateCard.tsx`'s comment
  for the next step: 3 to 8 lines by the rule; `styles.css`: `.waiting-field` and
  `.answer textarea` `resize: none` and `line-height: 1.5`. Check: `cd web && npx vitest
  run WaitingCard`, `make web`.

## 3. UI e2e (the requirement's scenarios)

- [x] 3.1 `tests/ui/test_chat.py`: Other… with one line is 3 lines high; 12 lines make it
  8 lines high, scrolling inside, its bounding box within the card's list and the
  viewport; the same in the expanded card, its box above the Send row. Screenshots of
  both (the `shot` fixture) as run artifacts. Check: `uv run pytest -m ui
  tests/ui/test_chat.py -k answer_field`.
- [x] 3.2 `tests/ui/test_gates.py`: a 12-line comment on a gate's tab is 8 lines high,
  above the Send row and within the viewport; screenshot. Check: `uv run pytest -m ui
  tests/ui/test_gates.py -k comment`.

## 4. Docs

- [x] 4.1 `docs/design/ui.md` (The waiting card: the fields' height, decided 2026-10-15,
  LAD-70, mockup `task/lad-70/mockup-answer-field.html`, option A), CHANGELOG.md (a line
  under 0.40.0 (unreleased)).

## 5. Regression

- [x] 5.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_chat.py
  tests/ui/test_gates.py`, `openspec validate waiting-card-answer-field --strict`,
  `openspec validate --specs --strict`.
