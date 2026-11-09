# LAD-256 rc-check-no-side-files: review report

Pull request #268 `fix/lad-256-rc-check-no-side-files` → `main`. Scale: tweak, depth precision.
Head reviewed: `f7c74646`. `scripts/rc_check.py` reads a database without a `-wal`, or with an
empty one, as immutable (`mode=ro&immutable=1`), so no `-wal` or `-shm` is created or left beside
it on any platform; a database with a non-empty `-wal` (a running LADO) is read as before, its WAL
included. Delta: a change to `release-candidates`.

## Rounds

1. Local, precision, `8ad4ee8b..f7c74646`: the whole diff against the spec, a trial archive. Every
   scenario of the delta has its code and test (1.1-1.4); every task checked. No finding.
2. External 1, Claude Code GitHub Action: E1 and E2. It read `scripts/rc_check.py` and
   `tests/test_rc_check.py`, not the openspec files (read locally).

External rounds used: 1 of 1. Stand-ins: 0.

## Checks

- `make lint` green; `tests/test_rc_check.py` 78 passed; `make test` run by the developer and CI.
- Red before the fix: the new tests run against `origin/main`'s `rc_check.py` in a copy outside the
  tree; 1.1 and 1.2 failed, 1.3 and 1.4 passed as intended. 1.3 fails if the read is always
  immutable (its row is only in the WAL).
- `openspec validate rc-check-no-side-files --strict` and the trial archive: 82 passed.
- CI on `f7c74646`: `ci-ok` and all 27 checks green, macOS smoke included; no reruns.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| E1 | minor | external: `plan` opens the live database twice (`_schema(live)` and the sessions' read); LADO may write its first WAL pages between them, so the two reads may go different ways | declined: both reads give consistent snapshots; the double open predates the change; outside a tweak |
| E2 | — | external: test 1.3 does not cover an empty `-wal` with a live `-shm` | disproved: an empty `-wal` means every page is in the main file; `immutable=1` reads no `-shm`; covered by test 1.2 |

## Residual risk

- Not run on a real Mac: tests 1.1 and 1.2 stand for the Mac's case on Linux. At the manual check
  of 0.45.0rc2 on the Mac, check that `~/.lado-rc` holds one file after `rollback`.
- The race between the `-wal` size check and the immutable read while LADO runs is accepted in the
  design: at worst the plan misses a session started in that instant.

## Found on the way

Nothing.
