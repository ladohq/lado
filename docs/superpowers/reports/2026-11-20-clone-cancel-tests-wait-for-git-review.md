# LAD-307 clone-cancel-tests-wait-for-git: review report

Pull request #352 `fix/lad-307-clone-cancel-tests-wait` → `main`. Scale: tweak, review depth:
precision. Head reviewed: `19c06b7b`. A new helper `ended(pid, timeout=10)` in
`tests/agent_helpers.py` waits for `gone(pid)`, and the 12 instant checks
`gone(call["pid"]) and gone(call["child"])` of the clone-cancel tests use it, so a child of the
fake git that SIGKILL has not yet taken off a loaded runner no longer fails the test. Tests
only: no `src/`, `web/`, schema or API change, no CHANGELOG.md line, no delta.

## Rounds

1. Local, precision and a check against the design, `30254c54..19c06b7b`. External 1, Claude
   Code GitHub Action (request
   https://github.com/ladohq/lado/pull/352#issuecomment-7036699167): no findings.

External rounds used: 1 of 1. Stand-ins: 0.

## The human's decisions

- **Gate `design_ok`**: option A, the tests wait; the cancel of the clone in `src/lado/clone.py`
  stays as it is (#7752).
- **Gate `merge_ok`, approved** with no comment.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | local: AC-2's grep `gone(call\["pid"\])` still finds `tests/ui/test_launch.py:951` | declined: that call stands inside its own `wait_for(..., timeout=15)`, which the design's Out of scope names; only the wording of AC-2 and Out of scope differ |
| F2 | minor | external: the original race was not reproduced locally; 30 runs under load show only no regression | declined: the CI log shows the cause (`gone(3440)=True`, `gone(3441)=False`), and the wait follows from it |

## Checked against the code

- `ended` (`tests/agent_helpers.py:745`) polls `gone` up to a `time.monotonic()` deadline and
  adds no delay on success; a process that never ends still fails the test after 10 s.
- Its unit tests: a killed `sleep` stays a zombie until `wait()`, and `gone` counts `Z` as
  ended, so True is right; the second test shows the check can fail (False on timeout).
- All 12 places replaced, imports cleaned; no other instant check of that shape.
- Every task of `tasks.md` checked; `src/` untouched, `gone` still instant.

## Checks

| Check | Result |
|---|---|
| `make lint` | exit 0 |
| `make test` | 6087 passed, 14 skipped |
| `uv run pytest -m integration -n auto` on the two changed integration files | 10 passed |
| unit files of the diff | 194 passed |
| `openspec validate clone-cancel-tests-wait-for-git --strict` | valid |
| `openspec validate --specs --strict` after a trial archive | 89 passed |
| CI of PR #352 on `19c06b7b` | every job green, smoke and `ci-ok` among them |

## Metrics

Rounds: local 1, external 1, stand-ins 0. Confirmed: local 1, external 1, both minor.
Refuted: 0. Findings in code changed by the developer's clean-up: 0.

## Not verified (residual risk)

- The original race was reproduced neither by the analyst nor by the developer; that the fix
  closes it follows from the mechanism, not from a run red before and green after.
- `make check`, `make test-integration` and the smoke were not run locally in full; CI ran them
  on this commit. Live tests were not run (weekly and by hand).

No change in `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
`tests/live/`.
