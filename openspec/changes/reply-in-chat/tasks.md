## 1. The rule and the hint

- [ ] 1.1 `runtime.py`: the rule as one constant, first in `SUPERVISOR_INSTRUCTIONS` after its
  name and first in `WORKER_INPUT`; the sentence "answer text typed straight into your window in
  this window" gone (design D1). Check: unit tests of the supervisor's and both workers'
  instructions in `tests/test_runtime.py`.
- [ ] 1.2 `runtime.format_message`: `HUMAN_REPLY_HINT` on the human's lines that are not
  answers (D2). Check: unit tests of the three scenarios of "The human's message says how to
  answer it"; the exact-line expectations in `test_runtime.py`, `test_attachments.py`,
  `test_tmux.py`, `test_codex.py` updated; `make test`.
- [ ] 1.3 The fake agent parses its commands with the hint at the line's end; the exact-line
  expectations of the integration tests updated. Check: `uv run pytest -m integration -n auto`
  on the changed files under `tests/integration/`.

## 2. The reminder and the verdict

- [ ] 2.1 `state.py`: `REMINDED`; `check_replies` decides NULL and `reminded` messages as in
  design D3-D4 and returns the ids that became `reminded`. Check: unit tests of each transition,
  of `reminded` kept while the reminder waits, and of no id returned twice.
- [ ] 2.2 `hooks.py`: at a clean `TURN_END`, one `lado` message per returned id with the text of
  D6, before the queue is handed over. Check: a unit test of the hook.
- [ ] 2.3 `server/models.py`: `reminded` given as `None` (D5). Check: a unit test; `make web`
  shows no stale types.
- [ ] 2.4 Integration with the fake agent (`tests/integration/test_human_messages.py`): answer
  only in the terminal → one reminder, then `missing`, no loop; answer after the reminder →
  `replied`; a turn with an error decides nothing. Check: `uv run pytest -m integration -n auto
  tests/integration/test_human_messages.py`.

## 3. Live, docs, CHANGELOG

- [ ] 3.1 `tests/live/test_live.py`: the human writes "hello" with no instruction how to answer;
  the reply reaches the chat (`replied`). Written, not run (paid, by hand).
- [ ] 3.2 Docs true to the code: `docs/design/agents.md` (the rule, the hint, the reminder and
  the verdict), `docs/design/ui.md` ("A forgotten reply is caught" and "Where the human
  asked"), `docs/design/modules.md` (`state.check_replies`, `hooks`).
- [ ] 3.3 CHANGELOG.md, Fixed, under `## 0.46.2 (unreleased)` (added on top; the change merges
  after 0.46.1's final): weak models answer the human in the chat, and an answer left in the
  terminal gets one reminder.

## 4. Checks

- [ ] 4.1 `make lint`, `make test`, the integration files of 1.3 and 2.4 with `-m integration`,
  `openspec validate reply-in-chat --strict`, `openspec validate --specs --strict` and the trial
  archive of the settings' Checks.
