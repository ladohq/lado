## 1. Shared helpers

- [x] 1.1 `runtime.work_of` and `runtime.keeps_work` factored out of `_work_state` and
  `_refusal`, finish calling them (D4). Unit tests: merged and clean, unmerged, dirty,
  branch gone with commits in the worktree, both gone; existing finish tests unchanged.
- [x] 1.2 `runtime.include_worktrees` beside `exclude_worktrees` (D5). Unit tests: the
  line dropped, others kept, from a linked worktree, no file, round trip.
- [x] 1.3 `update.remover` and `LADO_UNINSTALL_REMOVER` (D8). Unit tests: uv receipt
  (index and git source), pipx with a suffix, none, the test override.

## 2. Core: `lado.uninstall`

- [x] 2.1 `plan()` and `print_plan` (D1, D3, D4, D6, D7, D10). Unit tests
  (`tests/test_uninstall.py`): "Dry run" (nothing changes), the plan's parts, "A newer
  database", an older one read-only with the migration line, no `lado.db`,
  default-home detection, "LADO_HOME is the home folder" and the other guarded folders.
- [x] 2.2 `run()` (D2, D4–D9). Unit tests: stop order and the tmux server ("A running
  session and the UI server" recorded, "Another LADO_HOME on the same socket"), a loop
  that does not end, "An update runs", "Merged and unmerged workers", "The project's own
  files stay", "A kept worktree keeps the exclude line", "A repository that is gone",
  "The default home", an undeletable file, "A uv tool install" (remover last), "Another
  LADO_HOME", "A working copy", a failing remover, no import after the remover,
  `--keep-data`, exit codes and the closing block.

## 3. CLI

- [x] 3.1 `lado uninstall [--dry-run] [--keep-data] [--yes]`, no `migrate_if_safe`
  before it (D1). Unit tests (`tests/test_cli.py`): help, "Inside an agent", dry run
  without asking, "Not confirmed", "No terminal", `--yes`, a newer database's error.

## 4. End to end

- [x] 4.1 `tests/integration/test_uninstall_process.py::test_uninstall_leaves_nothing`
  (fake agent, merged and unmerged workers, UI server, a viewer; spec "A running session
  and the UI server", "Merged and unmerged workers", "Another LADO_HOME"); run with
  `-m integration`. (Named `_process`, as `test_update_process.py`: two test files of one
  name clash under pytest.)
- [x] 4.2 `test_uninstall_keep_data_resumes` (spec "Reinstall and resume").

## 5. Docs

- [x] 5.1 `docs/install.md` Uninstall section with the steps by hand and the release
  test of an upgrade; README.md pointer; AGENTS.md (Layout, CLI, `update.py`);
  CHANGELOG.md line under 0.37.0.

## 6. Regression

- [x] 6.1 `make lint`, `make test`, the integration file with `-m integration`,
  `openspec validate --specs --strict`. Not done here: "A clean machine" by hand at
  release (uv tool install, `lado uninstall --yes`, install an older release, `lado
  update`): it removes the machine's LADO, so it is the human's release step.
