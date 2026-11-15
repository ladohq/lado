# LAD-105 scratch-checks-first: review report

Pull request #311 `hotfix/lad-105-scratch-checks-first` → `main`. Scale: hotfix, depth
precision, widened by the reviewer to breadth in round 1. Head reviewed: `4b05db67`. A new
session (New empty folder, Set up, `lado start --new`, `lado start <git-url>`) is now checked
whole by `runtime.check_new_session` before its folder, repository or clone is made; a fresh
start refused late removes the folder it made when nothing touched it.

## Rounds

1. Local, breadth (`origin/main...a33e0205`): the head of the shared `runtime.start_session`
   changed, and the human asked for a wider look. Lenses: spec, tests (with mutations), silent
   failures, comments, general. Found F1, F2 (important), F3 (minor).
2. Local, precision on the delta `a33e0205..4b05db67`: F1–F3 fixed correctly, nothing new.
   External 1, Claude Code GitHub Action (request
   https://github.com/ladohq/lado/pull/311#issuecomment-6883739841, answer 20:29 UTC, reply
   https://github.com/ladohq/lado/pull/311#issuecomment-6883847720). It read only the diffs of
   four source files ("Risky code not fully read"), not the tests, docs or specs; those were
   read in the local rounds.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | `--new` or a clone into the gone folder of a stopped session was refused with SessionExists ("resume it", a dead end); main resumed it | fixed in 559f24b7 (`cli._check_new` skips the session of the same folder); `test_cli.py::test_new_in_the_gone_folder_of_a_stopped_session_resumes_it`, `::test_a_clone_into_the_gone_folder_of_a_stopped_session_resumes_it` |
| F2 | important | Set up inside `projects/` through the API made `.git` before the `in_project` refusal: `check_new_session` lacked `projects.refusal` | fixed in 559f24b7; `test_server_launch.py::test_a_setup_in_a_project_is_refused_before_its_repository` |
| F3 | minor | `scratch.remove_unused` returned True when `rmtree` failed, and the CLI said "removed" | fixed in 559f24b7; `test_scratch.py::test_a_removal_that_fails_says_so` |
| E1 | minor | external: the new session's checks run twice (before the folder and inside `start_session`) | declined: the second run is `start_session`'s own check (D2, one source of truth); a refusal there takes the tested late-removal path |
| E2 | minor | external: `check_title` now runs after the "name held by another folder's session" check | declined: only which refusal wins when two apply changes |
| E3 | minor | external: `NewSession.warnings` is called `checked` at the call site | declined: `checked` is the name the rest of `start_session` uses |
| E4 | minor | external: the checks and `rmtree` in `remove_unused` are not atomic | declined: a millisecond window right after a refusal, on a folder LADO made a moment before |
| E5 | minor | external: Ctrl-C after the repository is made removes nothing and the CLI says nothing | declined: an interruption leaves the folder, as on main |
| E6 | — | external: no test that a session on the folder keeps it | refuted: `test_scratch.py::test_a_fresh_repository_that_changed_stays[_with_a_session]` exists and fails under the mutation without the `last_session` check |

## Checks

- `make lint` clean; `make test` 6182 passed, 7 skipped; `openspec validate
  scratch-checks-first --strict` valid.
- CI on `4b05db67`: 27 checks green, `ci-ok`, the smoke on four providers (Linux and macOS),
  integration, container and UI included; integration, UI and container were not run locally.
- Every condition of the folder's removal is pinned by a test that a mutation of it turns red.

## Residual risk

- Live tests (`make test-live`) were not run: paid, and need the human's yes; `runtime.py`
  (the shared `start_session`) changed. The smoke with real CLIs is green in CI.
- The external reviewer read no file whole and no test; the local rounds covered them, not
  independently.
- The checks run twice (E1): an environment that changes between them sends the second refusal
  to the late removal.

Found on the way: nothing.
