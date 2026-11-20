# LAD-288 rollback-wording-container-leftovers: review report

Pull request #350 `hotfix/lad-288-release-checks-cleanup` → `main`. Scale: hotfix. Head
reviewed: `b4c2e2a9`. Three fixes in the release's and the tests' own tooling: docs/release.md
4.4 and 4.7 name the line of `rollback`'s plan for the sessions not started again; the
container tests treat SIGTERM and SIGHUP as Ctrl-C, hold a lock of their prefix, reap what
dead runs left (containers, volumes, networks, tags), warn about leftovers of no known run,
and fail at their end when anything of their prefix is left; seven tests that took "the
last message" to an agent pick it by sender and summary.

## Rounds

1. Local, precision over `98ef4bb7..b4c2e2a9`: `tests/container/container_runs.py`,
   `conftest.py`, `test_cleanup.py` and `cleanup_target.py` read line by line for races
   and error paths; the step-picking tests, the rc_check test, docs/release.md and
   docs/testing.md compared with `scripts/rc_check.py` `print_plan` and `self_update.py`.
   Found L1, L2.
2. External 1, Claude Code GitHub Action (request 2026-11-20T08:07:05Z): read the three
   files of the container cleanup only; not the documents nor the integration and UI test
   changes, which the local round covered. Found E1, E2, E3, E4.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| L1 | minor | `tests/test_rc_check.py:848-849` repeats one assert line | declined: does not change the check |
| L2 | minor | docs/testing.md does not say the lock file stays when a removal fails | declined: the warning names the failed removal; incomplete, not false |
| E1 | minor | `trap_signals` replaces a SIGHUP that `nohup` set to ignored, so closing the terminal ends such a run | declined: the run still ends cleanly through the finalizers |
| E2 | minor | two reapings starting at once over one dead prefix can give a false "could not remove" or "no lock file" warning | declined: only a spurious warning; nothing live is removed |
| E3 | minor | a signal during a finalizer leaves that test's objects | declined: covered: the end's check fails the run, the next run reaps them |
| E4 | — | `signal.signal` raises `ValueError` outside the main thread under xdist | refuted: container tests always run with `-n0` |

## Metrics

- Rounds: 1 local, 1 external, 0 stand-ins.
- Confirmed: local 2 (minor), external 3 (minor).
- Refuted: external 1.
- Findings in code changed by the developer's cleanup: 0.

## Checks

- At `b4c2e2a9`: `make lint` clean; `tests/test_container_runs.py`, `tests/test_rc_check.py`
  93 passed; the four changed files of `tests/integration/` 29 passed;
  `openspec validate rollback-wording-container-leftovers --strict` valid.
- CI of PR #350 at `b4c2e2a9`: 27/27, `ci-ok` green, the container cells on amd64 and
  arm64 included.

## Found on the way

- Nothing.

## Residual risk

- The container tests were not run against a real Docker locally (LADO's container has
  none); their result is CI's.
- Two container runs at once on one machine are not covered by a test, only read in the
  code (E2: the worst is a spurious warning).
- `tests/ui/test_gates.py` ran in CI only.
