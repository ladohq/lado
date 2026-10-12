## 1. The card

- [x] 1.1 `web/src/Question.tsx`, `Given`: a reply with a `choice` shows only its comment
  (`Body` with `breaks`) under the head, no `.answer-choice`; own words and a dismissal
  unchanged; the file's and `Given`'s comments say so. Remove `.answer-choice` from
  `web/src/styles.css`. Check: `grep -rn answer-choice web/src` finds nothing.
- [x] 1.2 `web/src/Chat.test.tsx`: the test of a question answered with a choice asserts
  `.choices .chosen` is "✓ yes", the block's head "You · answered", and that the block
  holds no `.answer-choice` and no text but its head (AC-1); the test of an answer after
  other rows keeps its own-words and comment checks and asserts the chosen choice's card
  shows "later" once (AC-2, AC-3, the late line unchanged, AC-4). Check: `make web`.

## 2. The browser

- [x] 2.1 `tests/ui/test_chat.py`: `test_the_supervisor_asks_and_the_human_answers_in_a_card`
  and `test_the_chat_looks_as_a_feed_in_light_and_dark` assert the chosen choice in
  `.chosen` and no `.answer-choice` in the cards (AC-1, AC-2); their screenshots are the
  build's evidence. Check: `uv run pytest -m ui tests/ui/test_chat.py`.

## 3. Docs

- [x] 3.1 docs/design/ui.md, "A question" and "Answer in the question card": the reply
  block holds "You · answered", the time and a choice's comment (or the own words, a
  dismissal's comment); the choice is marked only in the list (decided 2026-10-12, LAD-25,
  mockup `mockup-closed-question.html`, option A).
- [x] 3.2 CHANGELOG.md under `## 0.37.0 (unreleased)`: a closed question card in the chat
  shows the chosen choice once, in its list.
- [x] 3.3 `openspec validate question-card-choice-once --strict`, `make lint` and `make
  test` pass.
