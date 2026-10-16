# LAD-81 slow-shell-test-flake: review report

Pull request #80 `hotfix/lad-81-slow-shell-test-flake` → `main`. Scale: hotfix, reviewed
for precision (not widened: only `tests/test_agent_env.py` and the openspec change
changed, no product code). Head reviewed: `0aa25eb` (= the remote head). No change to
`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or `tests/live/`:
no live tests needed.

## Rounds

- **Round 1, local** (precision and the spec over `origin/main...0aa25eb`): F1. The
  wrapper checked against `agent_env.from_shell` and `_read_until`: the deadline counts
  from `Popen`, the wrapper waits for the marker and calls the original with the same
  `deadline`; a passed deadline gives `None` at once, the group is killed and the stderr
  file read after the kill, so `stuck` is always in the error. `tests/test_agent_env.py`
  52 passed, `make lint` 0, `openspec validate --specs --strict` 31 passed.
- **Round 1, external** (Claude Code GitHub Action, request 07:25:39Z, "Claude finished"
  07:26:40Z): F2, F3, and agreement with declining F1. CI on `0aa25eb`: every job passed,
  `ci-ok` included (smoke on Linux and macOS for all four providers).

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (tests) | When the marker never comes within 30 s, `pytest.fail` leaves `from_shell` before `_kill`, so the fake shell (`sleep 30 & wait`) stays alive | confirmed | minor | declined: only in a test that failed already, and `sleep 30` ends by itself |
| F2 | ext 1 | external | The marker path is put into the rc unquoted; a `tmp_path` with a space would break it | confirmed | minor | declined: pytest's `tmp_path` has no spaces on macOS or Linux; last round |
| F3 | ext 1 | external | The 30 s constant could have a name or a comment | confirmed | minor | declined: readability, "already clear enough" by the reviewer itself |

Blockers: 0. Important: 0. Refuted: 0.

## Checked

- The test can fail: in a copy outside the tree, `sleep 1;` before `echo stuck` makes the
  test of `main` fail on `assert 'stuck' in ...` (1 failed) and the test of the pull
  request pass (1 passed).
- AC-1 to AC-4 met; every task of `tasks.md` checked; nothing in `src/`, no CHANGELOG line
  or version bump, as designed. The pull request's title and description match its diff.

## Not checked (residual risk)

- The full `make test` was not run by the reviewer (the developer: 3357 passed; CI's unit
  jobs green); integration, UI and smoke tests only in CI, all green.
- The 20 runs in a row alone were the developer's, not repeated. Stability under real
  `-n auto` load is shown by the mechanism and the `sleep 1` probe, not by statistics.

Found on the way: nothing new. The neighbouring
`test_a_background_program_of_the_rc_files_does_not_hold_it_up` (a 2 s bound) is of the
same kind but out of scope; BACKLOG.md's P1 entry on timeouts under load holds it.
