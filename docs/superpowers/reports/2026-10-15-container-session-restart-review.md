# LAD-74 container-session-restart: review report

Pull request #65 `feature/lad-74-container-session-restart` → `main`. Scale: full,
reviewed for breadth first, at most two external rounds. Head reviewed last: `304c0c8`
(= the remote head); the archive commit follows it. `src/lado/runtime.py` changed
(`stop_for_container`, `resume_at_start`), so the human may want live tests before the
merge; `providers/`, `hooks.py`, `mcp_server.py`, `agent_env.py` and `tests/live/` did
not change.

## Rounds

- **Round 1, local** (breadth over `origin/main...50a55ca`: tests, errors, data,
  concurrency, the architecture against AGENTS.md, the spec): F1 (important), F2–F4
  (minor). No external round requested.
- **Round 2, local** (precision over `50a55ca..7a769f2`: the fixes of F1–F3; `712a0da`,
  the resume thread no longer opens a lado.db that is not there, after a red CI container
  amd64; `7a769f2`, BACKLOG): no new defect.
- **Round 1, external** (Claude Code GitHub Action, `@claude review`, answer in comment
  6197512430): no defect; F5 (declined), F6 (refuted).
- **Round 3, local** (a return from `merge_ok` after release 0.39.0; precision over
  `7a769f2..304c0c8`): `97f5dd2` merges origin/main (only `CHANGELOG.md`,
  `pyproject.toml`, `uv.lock`, `tests/ui/test_system_panel.py`; main at schema 28, the
  change 29); `304c0c8` moves the CHANGELOG line under `## 0.40.0 (unreleased)` with
  `Upgrade: schema 29` in the form of the earlier schema bumps. No new defect.
- **Round 2, external** (request 18:38:14Z, comment 6199532456; `Claude finished` in
  comment 6199537265, 18:39:19Z): no new problem, the CHANGELOG move is right, the triage
  of F1–F6 accepted. The external reviewer is of the same model family, so its "nothing
  found" weighs less.

External rounds used: 2 of 2.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (architecture, "No silent drops") | the resume at the container's start dropped `Started.warnings` and `Started.problems`, which `lado start` prints and the UI returns | confirmed | important | fixed in `3778833`, test `tests/test_runtime.py::test_a_resumes_problems_and_warnings_are_reported` |
| F2 | 1 | local (tests) | debug `print`s in an integration test | confirmed | minor | fixed in `29e6f9e` |
| F3 | 1 | local (errors) | `close_viewers` outside the `try` of `runtime.stop_for_container`: a `TmuxError` cut the stop of the other sessions and printed a false "could not stop the sessions" | confirmed | minor | fixed in `4dcf1fd`, test `test_viewers_that_cannot_be_closed_do_not_keep_the_containers_stop_from_the_rest` |
| F4 | 1 | local (data) | `state.stop_for_container` writes no `session_gone` for a session whose tmux was gone before the container's stop; its `ran_seconds` stretch to the stop | confirmed | minor | declined: rare, the session is resumed anyway (D5), a tmux check before the transaction would slow the stop (D1/D3); the external reviewer agreed |
| F5 | ext. 1 | external | the docstring of `resume_at_start` is vague | confirmed | minor | declined: comment wording only |
| F6 | ext. 1 | external | use a `state` helper for lado.db's path | refuted | — | dropped: no such helper (`state.home_path` only); the same literal is used in four places |

## Checks

- On `304c0c8`: `make lint` 0; `uv run pytest -n auto tests/test_state.py
  tests/test_runtime.py tests/test_server_container.py tests/test_release_notes.py` 621
  passed; CI of PR #65 23/23 green, `ci-ok`, container amd64/arm64 and the smoke included.
- The developer on `304c0c8`: `make test` 3241 passed, 1 failed
  (`tests/test_server_clones.py::test_a_window_that_went_away`, a timing flake unrelated
  to the change: 20 passed alone, green in CI); integration 139 passed, 1 skipped; `make
  test-container` 27 passed; openspec valid.

## Not checked (residual risk)

- `make test`, `make test-integration` and `make test-container` as a whole were not run
  by the reviewer; CI and the developer ran them, green.
- `make test-live` was not run; `runtime.py` changed.
- The manual check on a Mac from the pull request's description is the human's.
- A narrow window: when the server makes lado.db on a fresh volume at the moment the
  resume thread sees it, the thread may print one stray error line (a fresh volume has no
  sessions); the root is the BACKLOG item below.
- The race of D8 (a session the thread takes while the container stops) is by design: its
  tmux dies with the container.

## Found on the way

- `state.connect`'s first making of lado.db is not atomic: two first opens at once can
  leave it at version 0. Added to BACKLOG.md in `7a769f2`; out of the task's scope.
