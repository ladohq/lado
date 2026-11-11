## 1. doctor

- [x] 1.1 Unit (`tests/test_doctor.py`, beside `test_config_folders_of_agents_that_do_not_run_warn`),
  failing first: the two scenarios of "Only folders count as agent config folders" (a
  `.DS_Store` file at the root and in a running session's folder, a hidden folder, a plain
  file, a stray folder beside them). Then `runtime.stray_config_dirs` skips entries that are
  not folders or whose name starts with `.`, at both levels (D1).

## 2. The stop waits for the loop

- [x] 2.1 Unit (`tests/test_loop.py`), failing first: `loop.run` with LADO_HOME holding no
  `lado.db` returns 0 and leaves no `lado.db`, `loop.log` or LADO_HOME behind (a deleted
  `tmp_path` home). Then the check before each pass (D3).
- [x] 2.2 Unit (`tests/test_runtime.py`), failing first: `stop_session` raises the LadoError of
  D2 after marking the session stopped when `loop.wait_stopped` returns False (faked), and
  waits for it after the kill; `stop_all` waits for every loop after stopping them all and
  names the session whose loop did not end among its failures. Then the code (D2).
- [x] 2.3 Integration (`tests/integration/test_session_loop.py`, marker `integration`, fake
  agent): a running session; `lado stop` returns with no loop running (`loop.running` False);
  LADO_HOME deleted at once; after several `LADO_LOOP_INTERVAL`s no LADO_HOME exists.
- [x] 2.4 Integration, same file: `lado stop s` then `lado start s` at once; exactly one loop
  runs and `loop.log` has the first loop's `loop ended` before the second `loop started`.
- [x] 2.5 Integration, same file: LADO_HOME deleted under a running loop (the session not
  stopped); the loop ends within a few intervals (its process gone) and LADO_HOME is not made
  again.

## 3. Documents and regression

- [x] 3.1 `docs/cli.md` (`lado stop`: it returns after the loop ended, the failure of D2),
  `docs/design/agents.md` (the session loop: the stop waits for it; it ends without writing
  when `lado.db` is gone), the docstrings of `stop_session`, `stop_all` and `loop.run`.
- [x] 3.2 CHANGELOG.md, `## 0.46.1 (unreleased)`, Fixed: `lado stop` returns once the session's
  loop has ended, so a home deleted after it stays deleted and `lado stop s && lado start s`
  leaves one loop; `lado doctor` no longer takes `.DS_Store` for an agent's folder (LAD-153).
- [ ] 3.3 Regression: `make lint`, `make test`, `uv run pytest -m integration -n auto
  tests/integration/test_session_loop.py` and the integration files that stop sessions
  (`grep -l "lado stop\|stop_session\|stop_all" tests/integration/*.py`);
  `openspec validate stop-waits-for-loop --strict` and the trial archive of the settings'
  Checks.
