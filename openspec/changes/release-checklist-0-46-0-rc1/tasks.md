## 1. docs/releases/0.46.0.md

- [ ] 1.1 The file as the proposal's text: the heading, the paragraph, `## 0.46.0rc1` with its
  paragraph, Before you start and the items of each group, and "What covers the CHANGELOG's
  items" with the 8 items. Each top-level item's first line names its check alone.
- [ ] 1.2 Every exact line the file quotes is checked against the code (`web/src/Launch.tsx`,
  `web/src/LaunchWhere.tsx`, `web/src/LaunchTeam.tsx`, `src/lado/doctor.py`,
  `src/lado/state.py`'s `CLI_CHANGED`, `src/lado/runtime.py`'s `project_session_name`, docs/cli.md
  for `--name lado-lado`), and every test file it names exists; a line that differs takes the
  code's words, a missing test file is dropped from the list. Check: `grep` of each quoted text.

## 2. The test

- [ ] 2.1 `tests/test_rc_check.py`: the real-file test also runs `0.46.0rc1` on
  `docs/releases/0.46.0.md` (the file taken from the version), with the same asserts. Unit;
  `make test PYTEST_ARGS="-n0 tests/test_rc_check.py"` passes.
- [ ] 2.2 `python3 scripts/rc_check.py` is not run (it installs from PyPI); the test of 2.1 is
  the check that its list prints without a warning.

## 3. The checks

- [ ] 3.1 `make lint`, `make test`, `openspec validate release-checklist-0-46-0-rc1 --strict`,
  and the trial archive with `--skip-specs` in a copy of `openspec/` followed by `openspec
  validate --specs --strict`; all green.
