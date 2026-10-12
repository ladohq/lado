## 1. Core

- [x] 1.1 `state.Reply`, `state.QuestionClosed`, `state.reply_to_questions` (one
  transaction; `reply_to_question` removed); `runtime.HumanReply`,
  `runtime.answer_questions` (checks first, one transaction, one `_deliver`);
  `answer_question` / `dismiss_question` as one-reply calls (D1–D4). Unit tests
  (`tests/test_runtime.py`): "Two answers reach an idle agent in one hand-over" (one
  `send_text` with both lines), "A skipped question is a dismissal", "One question closed
  meanwhile" (nothing changed), "Questions of two agents", the other refusals (empty, twice,
  skip with a choice, a choice the question lacks), a busy agent gets the batch at its
  turn's end in one hand-over; `tests/test_state.py`: all or nothing, `NotRunning`. Check:
  `make test` (the existing question tests pass unchanged).

## 2. API

- [x] 2.1 `POST /api/sessions/{name}/answers` (`models.Replies`, `models.Reply`); the two
  question endpoints, `Answer` and `Dismissal` removed; `api.ts` `answerQuestions`; `make
  web-types`, both generated files committed (D5). Tests (`tests/test_server_messages.py`):
  "The UI sends a tab", "An empty list", the old endpoints gone, the guard's cases on the new
  path. Integration (`tests/integration/test_human_messages.py`, `-m integration`): the
  existing answer test on the new path; two questions of the fake agent answered in one
  request reach it and are both answered. Check: `uv run pytest -m integration -n auto
  tests/integration/test_human_messages.py`, `make web`.

## 3. UI

- [ ] 3.1 `GateCard.tsx`: `GatePanel` shared, `Note` and `Reads` exported (D8). vitest
  (`GateCard.test.tsx`, `Flows.test.tsx`): the compact card answers; a gate's `problem`
  line; stopped. Check: `make web`.
- [ ] 3.2 `WaitingCard.tsx` with `waitingTabs`, tabs, colours, picks, Send, the gate's
  panel, the look (D6, D7, D9; mockup `task/lad-28/mockup-question-card-final.html`);
  `Question.tsx` closed card only, "skipped" (D12, D13); `api.ts` without
  `answerQuestion` / `dismissQuestion`; icons `ExpandIcon`, `CollapseIcon`. vitest
  (`WaitingCard.test.tsx`): "Three things wait", "Nothing waits", "Colours of an agent and a
  run", "A new question meanwhile", "Two questions, one answered", "All answered", "A
  question that takes no own answer", a refusal keeps the picks, typing keeps focus, `focus`
  selects and marks. Check: `make web`.
- [ ] 3.3 `Chat.tsx`: the card between the feed and the composer from `waiting` and the
  session's gates, `runs` watched; open items as lines with their arrow; links to open items
  select their tab; `GateHint` removed; "skipped" in the late line and the quiet line;
  expanded over the window with Esc (D10, D11). vitest (`Chat.test.tsx`,
  `WaitingCard.test.tsx`): "An open question in the feed", "After the answer", a gate's
  line, no hint, "Expanded and back", Esc not expanded does nothing, the dialog folds when
  empty, "A stopped session". Check: `make web`.
- [ ] 3.4 `NeedsYou.tsx`: a card per session, "In the chat", waiting agents as rows;
  `GateRow` removed (D14). vitest (`NeedsYou.test.tsx`): "Two sessions", answering posts to
  that session. Check: `make web`.

## 4. End to end

- [ ] 4.1 UI e2e (`tests/ui/test_chat.py`, `tests/ui/test_needs_you.py`, `-m ui`): two
  questions of the supervisor answered in one tab reach the agent; three tabs (a worker's
  question, a gate) switch and the gate's Approve moves the run; the expanded card and Esc;
  Needs you answers in place; the cards' buttons one height in light and dark. Screenshots
  of the card with three tabs, the expanded card (light, dark), the feed after the answers,
  Needs you, attached as run artifacts. Check: `uv run pytest -m ui tests/ui/test_chat.py
  tests/ui/test_needs_you.py`.

## 5. Docs and release notes

- [ ] 5.1 `docs/design/ui.md` (Flow gates; A question; the open question's card replaced by
  The waiting card, decided 2026-10-13, LAD-28, mockup
  `task/lad-28/mockup-question-card-final.html`; Answer in the question card, "skipped";
  Structure: Needs you; Look), AGENTS.md (Layout: `POST …/answers`; How agents talk: replies
  to one agent handed over together), CHANGELOG.md under `## 0.37.0 (unreleased)`.
- [ ] 5.2 Regression run: `openspec validate waiting-card --strict`, `make lint`, `make
  test`, `uv run pytest -m integration -n auto tests/integration/test_human_messages.py
  tests/integration/test_session_start.py`, `make web`, `uv run pytest -m ui
  tests/ui/test_chat.py tests/ui/test_needs_you.py`.
