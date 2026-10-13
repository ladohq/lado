# LAD-35 uninstall: review report

Pull request #14 `feature/lad-35-uninstall` → `main`. Scale: full change, review depth:
breadth. Head reviewed last: `d240946`; the archive commit follows it. A new command `lado
uninstall` (`uninstall.py`), finish's rule moved into `runtime.work_of` /
`runtime.keeps_work` and `runtime.include_worktrees`, `tmux.kill_server`,
`update.remover`, `self_update.take_lock`, `telemetry.sender_ended`, docs and the openspec
change; no provider, hook or MCP code, no schema migration.

## Rounds

- **Round 1** (`origin/main...320e44c`): local breadth pass with the lenses Spec, Tests,
  Silent failures, Comments, Types, General and the architecture against AGENTS.md. Found
  F1–F4; no external round requested.
- **Round 2** (`320e44c..d240946`: the merge of main and three fixes): local precision
  pass, clean, plus external round 1 by the Claude Code Action (request 09:49:45 UTC,
  "Claude finished" 09:51:30 UTC): no blockers, five minor observations (E1–E5).

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local: checks | The PR conflicted with `main` (`AGENTS.md`, `src/lado/cli.py`), so CI did not run | confirmed | blocker | fixed in `19bf428` (main merged) |
| F2 | 1 | local: general, after merging main | `telemetry.kick()` / `record()` in `cli.main` made the deleted `LADO_HOME` again; with `--keep-data` imports ran after the remover | confirmed | important | fixed in `463851a`: uninstall is left out of kick and record; `telemetry.sender_ended` waits for a running sender before the home goes; three tests |
| F3 | 1 | local: spec, silent failures | A worktree with a detached HEAD under `.lado/worktrees/<session>/` was neither judged nor listed | confirmed | important | fixed in `aaeb5e4`: every path under the session's folder is judged; tests `test_a_detached_worktree_is_judged_by_its_head`, `test_a_branch_not_of_lados_is_never_deleted` |
| F4 | 1 | local: spec, tests | `--dry-run` made a missing `LADO_HOME` | confirmed | minor | fixed in `d240946` (`state.home_path()` without mkdir); test `test_a_dry_run_makes_no_lado_home` |
| E1 | 2 | external | `sender_ended` releases `send.lock` before `rmtree`; a new sender could start in between | confirmed (theoretical) | minor | declined: nothing kicks by then (loops, server and agents stopped, uninstall does not kick); only another `lado` command the human runs at the same time |
| E2 | 2 | external | A broken `pipx_metadata.json` gives an unhandled `json.loads` error in `update.remover` | confirmed | minor | declined: `update.installer` does the same; pipx writes the file |
| E3 | 2 | external | An unexpected exception after the stop gives a traceback, not "run again" | confirmed | minor | declined: expected errors are caught; a traceback for an unexpected one is `cli.main`'s convention, and a second run is safe |
| E4 | 2 | external | `tmux.kill_server` reads tmux's errors by their text | confirmed | minor | declined: the pattern of `server_running` / `sessions_with` |
| E5 | 2 | external | A repository registered through a symlink would miss a detached worktree in `git worktree list` | refuted | — | `sessions.repo` is `git rev-parse --show-toplevel` (`runtime.check_repo`), the real path git lists |

## Checks (head `d240946`)

- `make lint`: exit 0.
- `make test`: exit 0, 2767 passed.
- `uv run pytest -m integration -n auto tests/integration/test_uninstall_process.py
  tests/integration/test_telemetry_processes.py`: exit 0, 5 passed.
- `openspec validate --specs --strict`: 11 passed; `openspec validate uninstall --strict`:
  valid.
- CI run 38377716882: 12/12 green (check 3.10/3.13, js, ui, smoke ×8). `ui` first failed
  on a chat recommendation test outside the diff, passed alone and on the job's rerun: a
  flake.

## Metrics

Two rounds: two local, one external, no replacement of the external reviewer. Local: 4
confirmed (1 blocker, 2 important, 1 minor), 0 refuted. External: 4 confirmed (all
minor), 1 refuted. Findings in code changed by the developer's cleanup: 0. F2, F3 and F4
have tests the developer reports red before the fix.

## Not checked (residual risk)

- The scenario "A clean machine" (uv tool install → `lado uninstall --yes` → install an
  older release → `lado update`): a manual step of the human at release, as it removes
  LADO from the machine.
- Live and smoke tests were not run locally; the smoke is green in CI.
- `src/lado/runtime.py` changed (finish's rule moved out, `include_worktrees` added); no
  provider, hook or MCP code changed, but the human may want live tests before a release.
- By D6 (the human's decision) a `LADO_HOME` that holds `lado.db` is deleted whole, with
  foreign files in it; the plan names the folder, but `--yes` asks nothing.
- Non-standard installs (pip, a working copy) and removing the program through a real uv
  or pipx are covered only by unit tests with a substituted remover.

## Found on the way

None.
