# LAD-232 uninstall-agents-test-race: review report

Pull request #250 `hotfix/lad-232-uninstall-agents-test-race` → `main`. Scale: hotfix, review depth:
precision, as the design says; breadth was not needed, as the diff is one test. Head reviewed:
`2725a827`. `test_the_agents_processes_are_taken_before_the_stop_and_waited_for` no longer races
its own thread: it asks the agent's process (`agent.poll() is not None`), and the flag `ended` and
the thread's `agent.wait()` are gone. No change to `src/`, no delta, no CHANGELOG.md line.

## Rounds

1. Local, precision, `origin/main..2725a827`: the change against the proposal and `tasks.md`, AC-1
   to AC-4, the reasoning on the race, false greens. No findings. External 1, Claude Code GitHub
   Action: no blocking findings, two optional notes (F1, F2).

External rounds used: 1 of 1. Stand-ins: 0.

## The human's decisions

- **Gate `merge_ok`, approved** with no comment: F1 stays declined, and no live tests were asked
  for.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | external: the comment on `hangup` could add that a zombie counts as ended, which is why the test needs no `wait()` | declined: the comment is true as it stands, and the rule is in `_ended`'s docstring and the proposal |
| F2 | — | external: the test keeps a fixed `time.sleep(1)`, about 1 s per run | refuted: the check needs it, the agent must live while the product has to wait for it; without it a product that does not wait could pass |

## The mechanism

No race is left in the new check. `_ended` is true only for a zombie or a process gone, so the
`waitpid(WNOHANG)` of `poll()` gives the exit code at once. `Popen.terminate()` calls `poll()`
before `os.kill`, so by the process's death the thread has let go of `_waitpid_lock`, and the
hook's `poll()` does not get `None` from a held lock. The sources of `_internal_poll` and
`send_signal` say so on Python 3.13, and `subprocess.py` of 3.10 does the same.

## Checks

| Check | Head | Result |
|---|---|---|
| CI of the pull request, required `ci-ok` | `2725a827` | green: run 42404516738, 23 of 23, unit on 3.10 and 3.13, smoke included |
| A product that does not wait: `_wait_for_agents` a no-op, by a pytest plugin outside the repository | `2725a827` | fails, `assert [False] == [True]`, `tests/test_uninstall.py:446` |
| A wrong `_ended`: always true, the same way | `2725a827` | fails at the same line |
| The test alone, `-n0` | `2725a827` | 8 of 8 |
| One CPU (`taskset -c 3`), 24 busy loops | `2725a827` | 20 of 20 |
| `tests/test_uninstall.py` whole, `-n0` | `2725a827` | 37 passed |
| `make lint` | `2725a827` | clean, 1238 files |
| `make test` | `2725a827` | 4845 passed, 7 skipped |
| `openspec validate uninstall-agents-test-race --strict` | `2725a827` | valid |
| `openspec validate --specs --strict`; trial archive with `--skip-specs` | `2725a827` | 67 and 67 passed |

`make check`, `make test-integration`, the UI, smoke and live tests were not run locally: no file
of those layers changed; integration, UI and smoke passed in CI, and live runs only at a release.
Python 3.10 was not run locally: CI's `unit (3.10)` covers it. The load runs do not prove the flake
gone on their own, as the old test failed about 1 run in 40 unaided: the conclusion rests on the
mechanism above, and they only agree with it. The external reviewer did not read `proposal.md` and
ran no tests; it read `tests/test_uninstall.py`, and it is of the same model family, so its
"nothing found" weighs little. `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
`agent_env.py` and `tests/live/` did not change.

## Metrics

Rounds: 1 local, 1 external, 0 stand-in. Confirmed: 0 local, 1 external (F1). Refuted: 0 local, 1
external (F2). Findings in code changed by the developer's cleanup: 0.

## Found on the way

Nothing.
