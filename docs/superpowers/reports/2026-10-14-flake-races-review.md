# LAD-44 flake-races: review report

Pull request #30 `feature/lad-44-flake-races` → `main`. Scale: full, patch (fixes only).
Head reviewed last: `828a613` (= the remote head); the archive commit follows it. No API,
MCP, CLI or schema change. `hooks.py` and `runtime.py` changed (the hand-over at a turn's
end), so the human may want live tests before the merge; they were not run.

## Rounds

- **Round 1** (`origin/main...828a613`, the whole pull request): local breadth pass
  (lenses spec, tests, silent failures, comments, types and invariants, general, and the
  architecture against AGENTS.md: no provider detail above `providers/`, no second source
  of truth, no silent drop, no unused field, new tests at the lowest layer). External round
  1 by the Claude Code Action (request comment 6157009684 at 23:00:26 UTC, "Claude
  finished" comment 6157013169 at 23:01:33 UTC): no blocker, three minor observations
  (L1, L3, L4). The external reviewer read the sources and the unit tests in focus, not the
  integration, UI, web or smoke changes; the local pass read those.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| L1 | 1 | local + external | `run._gone` takes a zombie it is not the parent of for alive; `stop()` then waits `STOP_TIMEOUT` and fails "did not end" | confirmed (mechanism) | minor | declined: on LADO's paths the server is orphaned and reaped by init/launchd, and test servers are reaped by `waitpid` in their own process; a container whose PID 1 reaps no zombies stays a residual risk |
| L2 | 1 | local | `lado server stop` still kicks the statistics sender | refuted | — | the requirement covers only the exit of `lado server` itself; `test_the_server_kicks_nothing_at_its_exit` checks both |
| L3 | 1 | local + external | two `INSERT` branches in `state._add_event` (one with `COALESCE` would do) | confirmed | minor | declined: style, behaviour correct |
| L4 | 1 | external | `_gone` reaps the child before the fixture's `Popen.wait` → ECHILD | refuted | — | `Popen.wait` handles `ChildProcessError`; the UI fixture is green locally and in CI |
| L5 | 1 | local | three edits made with `sed -i` or a script, not the edit tool | confirmed | minor | declined: disclosed in the build report, the result is correct |

| Source | Confirmed | Refuted |
|---|---|---|
| local | 3 (L1, L3, L5) | 1 (L2) |
| external, Claude Code Action | 2 (L1, L3, both also local) | 1 (L4) |

## Spec check

- `server-stop`: `run.stop` / `_gone`; `test_stop_waits_for_the_process_after_its_lock`,
  `test_stop_names_a_process_that_outlives_its_lock`, `test_gone_*`, integration
  `test_stop_returns_once_the_servers_process_has_ended`; the exit: `cli.py`,
  `test_the_server_kicks_nothing_at_its_exit`, `test_uninstall_leaves_nothing`.
- `turn-end-hand-over`: `hooks._idle` → `hand_over(become=)` → `take_pending(become=)` in
  one `BEGIN IMMEDIATE`; `test_a_sweep_during_a_turns_end_cannot_type_the_hooks_batch`
  (red on the old code), three `test_take_pending_*`.
- `gate-history-order`: `_open_gate` passes the gate's `created_at`;
  `test_a_gate_and_its_event_share_one_time` (red without the fix); UI `test_gates.py`.
- Test fixes 4–8 as the proposal's What Changes says. Every task of `tasks.md` checked.

## Checks

- Reviewer on `828a613`: `make lint` clean; `make test` 2812 passed; integration files
  (`test_agent_liveness`, `test_server_process`, `test_agents`, `test_uninstall_process`)
  50 passed; UI files (`test_chat`, `test_gates`) 20 passed; `make web` 703 passed;
  `openspec validate --specs --strict` passed.
- CI run 38480861427 on `828a613` green: check (3.10, 3.13), js, ui, smoke × 8.

## Found on the way

None new (the two entries found in the design are in BACKLOG.md in this pull request).

## Not checked

- Live tests were not run, though `hooks.py` and `runtime.py` changed.
- `make check` and `make test-integration` as a whole were not run locally; CI ran them.
- L1 in a container whose PID 1 reaps no zombies.
- The fake agent's race was reproduced by a signal mask, not by a delay.
- The external reviewer is the same model family and ran no tests.

## Result

Converged after round 1 (1 of 2 external rounds).
