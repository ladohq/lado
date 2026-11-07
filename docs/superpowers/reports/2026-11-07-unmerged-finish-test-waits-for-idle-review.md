# LAD-233 unmerged-finish-test-waits-for-idle: review report

Pull request #248 `fix/lad-233-unmerged-finish-test-wait` → `main`. Scale: tweak, review depth:
precision. Head reviewed: `0979dc1d`. `test_unmerged_worker_is_finished_only_with_discard` waits
for w1 to be idle instead of reading its status once, and BACKLOG.md's entry on this flake goes.
Tests only: no `src/`, `web/`, schema or API change, no CHANGELOG.md line, no delta.

## Rounds

1. Local, precision, `3f7222ff..0979dc1d`: nothing wider was needed for a one-line test change.
   External 1, Claude Code GitHub Action: no blocking findings, two minors, all five files of the
   diff read, no tests run.

External rounds used: 1 of 1. Stand-ins: 0.

## The human's decisions

- **Gate `merge_ok`, approved** with no comment: F1 and F2 stay declined, and no live tests were
  asked for.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | external: had the refused finish ended w1, the test would fail with `AttributeError`, not a clear timeout | declined: `assert windows() == ["supervisor", "w1"]` on the line before catches that case with a clear output |
| F2 | minor | external: "The check is now line 745" in `proposal.md` will go stale | declined: the document records a moment and goes to the archive |
| F3 | — | local: the old line failing with `'busy' == 'idle'` under the probe (AC-2) was not reproduced by the reviewer | not verifiable by a read-only role: results taken from the build report (old line `1 failed`, new line `1 passed`), and `wait_for` polls until the status matches |

Also from the external reviewer, with no action asked: the wait outlasts the race with the retyped
task and does not close it. The proposal says so; the product question stays in BACKLOG.md.

## Checked against the code

- AC-1: `tests/integration/test_agents.py:745` has `wait_status("w1", state.IDLE)`; the rest of the
  test is unchanged.
- A second copy of the task starting a turn after the wait does not break the test:
  `finish_worker` has no status check, and `--discard` goes on with w1 busy.
- The other one-time status reads of the file follow a synchronous hook call, a `holding` barrier
  or the session start: no race there.
- AC-4: only the flake's entry left BACKLOG.md, and nothing else referred to it; the entries "A
  message typed again…" and "Integration tests take a new worker's first idle…" stay.

## Checks

| Check | Result |
|---|---|
| `make lint` | exit 0, 1238 files |
| The changed test, `-m integration -n0` | 5 of 5 passed |
| `uv run pytest -m integration -n auto tests/integration/test_agents.py` | 32 passed in 10.43 s, load average about 27 |
| `openspec validate unmerged-finish-test-waits-for-idle --strict` | valid |
| `openspec validate --specs --strict` | 67 passed, 0 failed |
| Trial archive in a copy with `--skip-specs`, then validation | 67 passed, 0 failed |
| CI on `0979dc1d` | 23 of 23 passed, `ci-ok` green |

## Metrics

Rounds: local 1, external 1, stand-ins 0. Confirmed: local 0, external 2 (both minor). Refuted: 0.
Not verifiable: 1. Findings in code changed by the developer's clean-up: 0.

## Found on the way

Nothing new. The red file runs under load in the build report (11 different tests, the target not
among them) fit BACKLOG.md's "`make check` fails on timeouts when the machine is under heavy load":
each passed alone. Their cause stays unproved.

## Not verified (residual risk)

- F3: the AC-2 probe was not repeated by the reviewer.
- AC-3's repeats (20 and 3 runs) were not repeated in full: the reviewer ran the test 5 times and
  the file once.
- `make test`, `make check`, `make test-integration` and `make test-smoke` were not run locally: CI
  runs them, and its unit, integration and smoke jobs are green on this head. `make test-live` was
  not run: at release only.
- The race with the retyped task is derived from the code and was not seen live.

No change in `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
`tests/live/`.
