# LAD-40 version-neutral-tests: review report

Pull request #17 `fix/lad-40-version-neutral-tests` → `main`. Scale: tweak, review depth:
precision. Head reviewed last: `3dddf38`; the archive commit follows it. Tests only:
`tests/test_doctor.py` and `tests/ui/test_system_panel.py`; nothing in `src/` or `web/`,
no provider code, no schema migration, no MCP change.

## Rounds

- **Round 1** (`origin/main..3dddf38`): local precision pass (the diff, the change, a
  read by hand, a grep of `tests/` for other assumptions about the kind of version), then
  external round 1 by the Claude Code Action (request 11:33:41 UTC, "Claude finished"
  11:34:31 UTC): no blockers, two observations (E1, E2). External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| E1 | 1 | external (Action) | `as_final_release` rewrites only `current`, `prerelease` and `latest`; the other fields of `/api/update` (`can_update` and others) stay the server's own | refuted | — | with only `__version__` published the server answers `available=None`, `available_prerelease=False` anyway (`UpdateInfo`, `src/lado/server/models.py`); the other fields do not depend on the kind of version; the neighbour test does the same |
| E2 | 1 | external (Action) | The rule "a final release is not offered a release candidate" is no longer checked in the UI | refuted (no defect) | — | the design's decision; the rule is tested where the server decides it: `tests/test_server_system.py::test_update_says_which_versions_are_pre_releases` (`0.36.0` with `0.37.0rc1` published: nothing available) |
| C1 | 1 | checks: CI | `check (3.10)` red on the integration tests in three runs in a row, each time another timing test | unverifiable (cause outside the diff) | — | accepted by the human (variant A) as an open flake outside the task; CI's parallelism is a separate task before rc2 |

C1's evidence: run 38390791487, attempt 1
`test_agents.py::test_messages_in_the_turn_end_output_are_delivered_once_confirmed[fake]`,
attempt 2 the same `[fake-stop]`, attempt 3
`test_agent_liveness.py::test_stopping_a_session_tells_no_one_and_counts_what_it_dropped`
(timeout 30 s); 3.13 green. Locally on Python 3.10 the whole `-m integration -n auto`:
132 passed, 1 skipped; the failed test alone 3×2 passed.

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 0 | 0 | 1 (C1) |
| external, Claude Code Action | 0 | 2 (E1, E2) | — |

No blocker and no confirmed finding.

## Found on the way

- C1: the integration timing tests on 3.10 fail in CI in 3 of 3 runs after the RC commit
  of 0.37.0rc1 (on `2440f02` CI skipped the integration step). The entries "Flaky in WSL:
  a message of the turn-end output delivered `typed`" and "Flaky in CI: a slow turn's
  hook-output message was typed" of BACKLOG.md are to get run 38390791487 (three attempts,
  3.10).

## Checks

- Local on 0.37.0rc1: `uv run pytest -n0 tests/test_doctor.py` 64 passed; `uv run pytest
  -m ui tests/ui/test_system_panel.py` 4 passed (the test can fail: without the rewrite
  the server answers `prerelease: true` on rc1); `make lint` clean; integration on Python
  3.10 132 passed, 1 skipped.
- CI of PR #17 on `3dddf38`: green but `check (3.10)` (C1).
- AC-3 (the version set to 0.37.0 by hand): the developer's report only (doctor 64, UI 4,
  unit 2776); not repeated by the review.
- Not run: live tests (not needed: `providers/`, `hooks.py`, `mcp_server.py`,
  `runtime.py`, `agent_env.py`, `tests/live/` untouched); smoke locally (green in CI).

## Design decisions left as they are

- The doctor tests use `update.shown`, the one function that formats a version as shown.
- The UI test rewrites the server's answers as its neighbour does; the offer rule stays
  at the API layer.
