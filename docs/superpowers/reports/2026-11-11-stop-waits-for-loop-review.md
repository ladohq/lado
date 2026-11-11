# LAD-153 stop-waits-for-loop: review report

Pull request #286 `hotfix/lad-153-stop-waits-for-loop` → `main`. Scale: hotfix, depth
precision (widened in round 1: the diff touches `runtime.py`'s stop and the session loop).
Head reviewed: `e68cbaa2`. `lado doctor`'s "Agent config folders" counts only folders whose
name does not start with `.`; `lado stop`, `lado stop --all` and the UI's Stop return only
after the session's loop has ended (exit 1 when it has not within three intervals); the loop,
and an agent's hook, write nothing into a LADO home that is gone. Capabilities: `doctor` one
requirement added; `session-stop` new, two requirements.

## Rounds

1. Local, over the whole diff `7579568f^..4a21980c`. Lenses: spec, tests, silent failures,
   comments, general, architecture against AGENTS.md. Findings F1, F2 (important), F3
   (minor) → changes.
2. Local, precision, delta `4a21980c..e68cbaa2`: F1–F3 resolved in `61268057`, each with a
   test. No new findings.
3. External 1, Claude Code GitHub Action: read every `src/` file of the diff (`hooks.py`,
   `loop.py`, `runtime.py`, `self_update.py`, `state.py`, `uninstall.py`); not the tests,
   docs or openspec files, which the local rounds read. No blockers; three minor remarks
   E1–E3.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | the session-end hook of a dying agent could make a deleted LADO_HOME again after `lado stop` returned (`hooks.main` → `connect()` makes `lado.db`; `_log` makes the home); docs and CHANGELOG promised more than the code did | fixed in `61268057`: `hooks.main` exits 0 before connecting when `lado.db` is gone; `test_a_hook_writes_nothing_into_a_deleted_home`; texts narrowed |
| F2 | important | `test_a_home_deleted_under_a_running_loop_is_not_made_again` flaky (4 of 23): the pass running at the deletion made `lado.db`, `loop.log`, `errors.jsonl` again | fixed in `61268057`: `state.home_not_made` (no mkdir of the home, sqlite `mode=rw`), silent exit after a failed pass; unit test `test_a_pass_that_meets_its_home_deleted_makes_nothing_again[read,fail]`; the file 6/6 green, 4/4 under double load (3 failures of 10 before) |
| F3 | minor | `stop_all` caught only `LadoError` around the loop's wait; any other error cut it short without `logins.end_windows()` and the summary | fixed in `61268057`: `except Exception`; `test_a_wait_that_fails_does_not_cut_stop_all_short` |
| E1 | minor | external: a `report` that fails after a stop leaves the session out of `stopped`, its loop not waited for | declined: the order was so on main; `report` is the CLI's print |
| E2 | minor | external: a loop that ends for a deleted home writes no "loop ended" line | refuted: the spec requires writing nothing (any line would make the home again) |
| E3 | minor | external: no comment that `_not_made` acts on the whole process | declined: `home_not_made`'s docstring says so |

## Found on the way

- `tests/integration/test_session_loop.py::test_a_queue_waits_for_a_late_session_start_and_goes_in_once`
  (an old test) fails only under heavy load (`attempts == 2`); not reproduced at equal load
  (main 0/16, head 0/10). Recorded in BACKLOG.md under P1 "`make check` fails on timeouts"
  (`e68cbaa2`), by the supervisor's decision; no tracker task.
- `test_the_loop_types_a_swallowed_message_again` flaky; already in BACKLOG.md.

## Checks

On `e68cbaa2`:
- `make lint` green; unit `test_doctor`, `test_error_journal`, `test_loop`, `test_runtime`,
  `test_state`, `test_telemetry`, `test_uninstall`, `test_update` with `-n auto`: 1305 passed.
- `uv run pytest -m integration -n auto tests/integration/test_session_loop.py`: 6 of 6 runs
  green (16 passed each); with `test_session_start.py` under double load 4 of 4 (20 passed).
- `openspec validate stop-waits-for-loop --strict` valid; `openspec validate --specs
  --strict` 82 passed; a trial archive in a copy 83 passed.
- CI: 27/27 green, `ci-ok` pass.

## Residual risk

- Live tests (the real session-end hooks of Claude, OpenCode, Kilo) not run: F1 is covered by
  a unit test calling `hooks.main`, not by a real CLI.
- Full integration, UI, smoke and container suites not run locally; CI ran them green.
- A pass's `mkdir(parents=True)` under a deleted home would make it again; no such pass in
  the covered case (design D3).
- The queue test above is flaky under heavy load.
- `runtime.py` and `hooks.py` changed: the human may want live tests before the merge.
