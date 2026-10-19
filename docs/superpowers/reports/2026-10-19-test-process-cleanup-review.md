# LAD-55 test-process-cleanup: review report

Pull request #109 `hotfix/lad-55-test-leftovers` → `main`. Scale: hotfix, reviewed for
precision (only `tests/`, documents and openspec change; no business logic or user data).
The whole diff was read by hand in round 1. Head reviewed last: `3f0b627` (= the remote
head). `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and
`tests/live/` did not change, so no live tests are needed before the merge.

## Rounds

- **Round 1, local** (precision over `origin/main...20b61f5`, checked against the spec,
  plus the supervisor's points): F1-F5, F3 refuted.
- **Round 2, local** (precision over the delta `20b61f5..3f0b627`): nothing new; F1, F2,
  F4, F5 closed.
- **Round 1, external** (Claude Code GitHub Action; request at 12:29:55Z, "Claude
  finished" at 12:31:19Z): no blockers, five optional notes; E1-E3 refuted, the rest
  confirmations without a finding.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (tests) | `leftovers._kill` reaped its own children with `os.waitpid(pid, WNOHANG)`, so `Popen.wait()` got `ChildProcessError` and returned 0, and the new integration tests' `wait() == -SIGKILL` checks flaked (2 red runs of 5 under `-n auto`) | confirmed | important | fixed in `3f0b627`: no `waitpid`; `_kill` waits for the (pid, environ) pair to vanish; 8 of 8 runs green |
| F2 | 1 | local (comments) | `proposal.md` (Impact) named a stale test file | confirmed | minor | fixed in `3f0b627` |
| F3 | 1 | local (general) | suspicion: an xdist worker checks its mark before the session fixtures' teardown | refuted | — | pytest tears all fixtures down at the last test (`nextitem=None`), before `sessionfinish`; a `-n 2` probe exits 0 |
| F4 | 1 | supervisor | no test that xdist workers (carrying the controller's mark) are not taken for leftovers | confirmed | minor | fixed in `3f0b627`: `test_a_run_with_workers_does_not_take_them_for_its_leftovers`, seen red by the developer with the controller's check moved before `yield` |
| F5 | 1 | supervisor | `docs/testing.md` did not say `LADO_TEST_PID` is a mark of the tests only | confirmed | minor | fixed in `3f0b627` |
| E1 | ext 1 | external | a crashed worker's leftovers live until the next run's start; docs should say so | refuted | — | `docs/testing.md` already says it (D5) |
| E2 | ext 1 | external | a reused pid or `PermissionError` in `_alive` makes a dead run look alive | refuted | — | the deliberate choice of D5: reaping waits rather than errs, as `reap_dead_runs`' docstring says |
| E3 | ext 1 | external | on macOS a value with a space would not match | refuted | — | `Process.has` matches the whole `NAME=value` followed by a separator or the line's end; only `get` cuts at a space, and it reads `LADO_TEST_PID` (digits) |

## Found on the way

Nothing.

## Checks

- `make lint`: exit 0.
- `openspec validate test-process-cleanup --strict` and `openspec validate --specs
  --strict`: valid.
- `make test`: 3607 passed, 1 skipped.
- `uv run pytest -m integration -n auto tests/integration/test_leftover_processes.py
  tests/integration/test_agent_liveness.py`: 8 runs in a row, 16 passed each.
- CI on `3f0b627`: 23/23 success, `ci-ok` and the four macOS smoke cells included.

## Metrics

- Rounds: 2 local, 1 external, 0 substitutes.
- Confirmed: 2 local (F1 important, F2 minor), 2 from the supervisor (F4, F5 minor).
  Refuted: 1 local (F3), 3 external (E1-E3).
- Declined: none. Not done on purpose: checking dead `lado-test-*` sockets at a run's
  end; the next run's start removes them (D5).
- Findings in code after the developer's cleanup: 0.

## Residual risk

- UI and smoke layers ran only in CI (no Chromium or real CLIs in the container); the
  macOS reader is checked only by the macOS smoke in CI.
- The load runs of LAD-96's test (5 runs, every CPU busy) and the killed-run scenario
  were the developer's; the reviewer did not repeat them. The reviewer's own `-n auto`
  runs on a shared machine: LAD-96's test green in 13 of 13.
- A dead socket `lado-test-e461ec38` was left in `/tmp/tmux-1000/` after round 1; it
  could not be tied to this change (other sessions run on the machine); the next run's
  start removes it.
- The external reviewer is of the same model family as the kit's agents.
