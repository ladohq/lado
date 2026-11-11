## 1. docs/releases/0.46.1.md

- [x] 1.1 The file as the proposal's text: the heading, the paragraph, `## 0.46.1rc1` with its
  paragraph, Before you start and the items of each group, and "What covers the CHANGELOG's
  items" with the 8 items. Each top-level item's first line names its check alone.
- [x] 1.2 Every exact line the file quotes is checked against the code (`src/lado/loop.py`'s
  `loop started` / `loop ended` lines and `STOPPED`, `src/lado/runtime.py`'s temporary folder's
  refusal and `stray_config_dirs`, `src/lado/providers/base.py`'s `UnsafeTempDir` texts,
  `src/lado/doctor.py`'s `Agent config folders`, `src/lado/cli.py`'s `lado ls` states,
  `web/src/LaunchModel.tsx`'s notes, `docker/install.sh`'s 2 minutes' line), and every test
  file it names exists; a line that differs takes the code's words, a missing test file is
  dropped from the list. Check: `grep` of each quoted text.

## 2. CHANGELOG.md

- [x] 2.1 `## 0.46.1 (unreleased)` as the proposal's text: no `(LAD-…)` left, the first and the
  seventh item written anew, the other six unchanged but for their key; each item at most three
  lines. Check: `grep -n 'LAD-' CHANGELOG.md` finds nothing in the section, and
  `python3 scripts/release_notes.py v0.46.1rc1` prints the 8 items.

## 3. The test

- [x] 3.1 `tests/test_rc_check.py`: the real-file test also runs `0.46.1rc1` on
  `docs/releases/0.46.1.md`, with the same asserts. Unit;
  `make test PYTEST_ARGS="-n0 tests/test_rc_check.py"` passes.
- [x] 3.2 `python3 scripts/rc_check.py` is not run (it installs from PyPI); the test of 3.1 is
  the check that its list prints without a warning.

## 4. The checks

- [x] 4.1 `make lint`, `make test`, `openspec validate release-checklist-0-46-1-rc1 --strict`,
  and the trial archive with `--skip-specs` in a copy of `openspec/` followed by `openspec
  validate --specs --strict`; all green.
