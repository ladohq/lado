## 1. The wait

- [x] 1.1 `src/lado/tmux.py`: `pane_pids(session)`, the `#{pane_pid}` of each pane of the
  session, none when the session or the server is gone (D1).
- [x] 1.2 `src/lado/uninstall.py`: `_stop` takes the pids of every session it stops before
  `runtime.stop_all`, and after the loops' wait waits up to `AGENTS_TIMEOUT` (10 s, one
  deadline for all) for them to end, a zombie counting as ended (D2, D3); a process left
  raises `runtime.LadoError` naming the session, the pids and `kill <pids>` (D4). The
  docstring of `_stop` names the step.
- [x] 1.3 `tests/test_uninstall.py` (unit): the pids are taken before the stop; a zombie
  counts as ended; a process that does not end stops the uninstall with exit 1, the pid
  and the `kill` command in the output, the repository's worktrees and `LADO_HOME`
  untouched (D6). Check: `uv run pytest -n0 tests/test_uninstall.py`.

## 2. End to end

- [x] 2.1 `tests/integration/test_uninstall_process.py` (marker `integration`): keep
  `test_uninstall_leaves_nothing` as it is; add a test with `FAKE_AGENT_HANGUP_HOOK=1`
  (agents run their session-end hook on SIGHUP): after `lado uninstall --yes` no pane
  process is alive and `LADO_HOME` does not exist. Check: `uv run pytest -m integration
  -n auto tests/integration/test_uninstall_process.py`; with 1.2 reverted, the new test
  fails.
- [x] 2.2 The flake gone: the file run 20 times in a row (`for i in $(seq 20); do uv run
  pytest -m integration -n0 -p no:cacheprovider
  tests/integration/test_uninstall_process.py || break; done`), all green; the count in
  the build report.

## 3. Docs

- [x] 3.1 `docs/cli.md` (`lado uninstall`): it waits for the agents' processes and stops
  when one does not end; `docs/design/modules.md` too if its `uninstall.py` line lists the
  stop's steps.
- [x] 3.2 CHANGELOG.md, `## 0.42.1 (unreleased)`, Fixed: `lado uninstall` waits for the
  agents to end, so `~/.lado` is not made again by an agent that ends after it.

## 4. Regression

- [x] 4.1 `make lint`; `make test` (numbers in the build report).
- [x] 4.2 `uv run pytest -m integration -n auto tests/integration/test_uninstall_process.py
  tests/integration/test_agent_terminal.py`.
- [x] 4.3 `openspec validate uninstall-waits-for-agents --strict`.
