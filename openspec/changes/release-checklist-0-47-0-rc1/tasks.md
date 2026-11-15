## 1. docs/releases/0.47.0.md

- [ ] 1.1 The file as the proposal's text: the heading, the paragraph, `## 0.47.0rc1` with its
  paragraph, Before you start, the items of "Your own LADO after the upgrade (4.2)", "The New
  session window on a phone", "The New session window's focus", "A refused new session leaves
  no folder", "Claude Code's login check", "The reminder to read a message" and "Going back
  (4.4)", and "What covers the CHANGELOG's items" with its 7 items. Each top-level item's first
  line names its check alone.
- [ ] 1.2 Every exact line the file quotes is checked against the code (`src/lado/runtime.py`'s
  upgrade line, `scripts/rc_check.py`'s `Kept a copy`, `src/lado/hooks.py`'s `UNREAD_REMINDER`,
  `src/lado/providers/claude.py`'s refusals and choice titles, `src/lado/kits.py`'s expected
  skill, `src/lado/self_update.py`'s warning, `Sessions not in that copy` and `Restored
  lado.db`), and every test file it names exists and covers its item; a line that differs takes
  the code's words, a test file that is missing or does not cover it is dropped from the list.
  Check: `grep` of each quoted text.

## 2. CHANGELOG.md

- [ ] 2.1 `### Upgrade` after `### Fixed` in `## 0.47.0 (unreleased)`, with the one item of the
  proposal; the `### Fixed` items unchanged. Check: `python3 scripts/release_notes.py
  v0.47.0rc1` prints the section with the group.

## 3. The test

- [ ] 3.1 `tests/test_rc_check.py`: the real-file test also runs `0.47.0rc1` on
  `docs/releases/0.47.0.md`, with the same asserts. Unit;
  `make test PYTEST_ARGS="-n0 tests/test_rc_check.py"` passes.
- [ ] 3.2 `python3 scripts/rc_check.py` is not run (it installs from PyPI); the test of 3.1 is
  the check that its list prints without a warning.

## 4. The checks

- [ ] 4.1 `make lint`, `make test`, `openspec validate release-checklist-0-47-0-rc1 --strict`,
  and the trial archive with `--skip-specs` in a copy of `openspec/` followed by `openspec
  validate --specs --strict`; all green.
