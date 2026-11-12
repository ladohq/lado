## 1. docs/releases/0.46.2.md

- [ ] 1.1 The file as the proposal's text: the heading, the paragraph, `## 0.46.2rc1` with its
  paragraph, Before you start, the items of "Answers in the chat" and "Going back (4.4)", and
  "What covers the CHANGELOG's items" with its one item. Each top-level item's first line names
  its check alone.
- [ ] 1.2 Every exact line the file quotes is checked against the code (`src/lado/runtime.py`'s
  `HUMAN_REPLY_HINT` and `format_message`, `src/lado/hooks.py`'s `REPLY_REMINDER`,
  `web/src/Chat.tsx`'s `replied only in its terminal`), and every test file it names exists; a
  line that differs takes the code's words, a missing test file is dropped from the list. Check:
  `grep` of each quoted text.

## 2. The test

- [ ] 2.1 `tests/test_rc_check.py`: the real-file test also runs `0.46.2rc1` on
  `docs/releases/0.46.2.md`, with the same asserts. Unit;
  `make test PYTEST_ARGS="-n0 tests/test_rc_check.py"` passes.
- [ ] 2.2 `python3 scripts/rc_check.py` is not run (it installs from PyPI); the test of 2.1 is
  the check that its list prints without a warning.

## 3. The checks

- [ ] 3.1 `make lint`, `make test`, `openspec validate release-checklist-0-46-2-rc1 --strict`,
  and the trial archive with `--skip-specs` in a copy of `openspec/` followed by `openspec
  validate --specs --strict`; all green.
