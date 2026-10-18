# LAD-98 start-from-scratch: review report

Pull request #99 `feature/lad-98-start-from-scratch` → `main`. Scale: full, reviewed
breadth first. Head reviewed last: `30bd1e7` (= the remote head). `runtime.py` changed
(`check_title`, `start_session(title=)`, `NOT_REPO_HINT`), so the human may want live
tests before the merge; `providers/`, `hooks.py`, `mcp_server.py`, `agent_env.py` and
`tests/live/` did not change.

## Rounds

- **Round 1, local** (breadth over `origin/main...9c1390b`): F1, F2, F3. No external
  round requested.
- **Round 2, local** (precision over the delta `9c1390b..30bd1e7`: `57e1c76` the fix of
  F2, `30bd1e7` the merge of main with the CHANGELOG conflict resolved keeping main's
  lines): nothing new.
- **Round 1, external** (Claude Code GitHub Action, request `issuecomment-6243693557`,
  answer at 00:25:46Z; the reply in `issuecomment-6243707409`): E1, E2, E3. By its own
  words it read only the Python part (not the web code, the tests or openspec) and ran
  no tests; it is of the same model family, so its "nothing more" weighs less.

External rounds used: 1 of 2.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (checks: CI) | the pull request conflicted with `main` (CHANGELOG.md), so CI never ran on it | confirmed | blocker | fixed in `30bd1e7` (origin/main merged); CI 23/23 pass, `ci-ok` pass |
| F2 | 1 | local (silent failures, spec) | `GET /api/scratch-target` without git answered 400 instead of 200 and lost the `xcode-select --install` hint; the same for a broken git config and an unreadable folder | confirmed | important | fixed in `57e1c76`: `FolderProblem` gives `state`/`text` null with the cause in `author`, other `LadoError`s go to `text`, `_author` catches any `LadoError`; 3 new tests in `tests/test_server_launch.py` (seen red), vitest in `web/src/Launch.test.tsx` |
| F3 | 1 | local (reading by hand) | the Create in field is empty while the request goes to the default folder `~/lado/<name>` | confirmed | minor | declined: the placeholder shows the default folder, the spec does not contradict it, a change needs a new test; the external reviewer agreed; left to the human at the merge gate |
| E1 | 1 | external | a start refused after `scratch.make` keeps the repository, and a retry in From scratch hits `inside_repo` | refuted | — | dropped: session-scratch requires keeping it and switching the window to Folder, which `createAndStart` does by itself; tests `web/src/Launch.test.tsx`, `tests/test_server_launch.py::test_a_fresh_start_refused_after_the_repository_keeps_it` |
| E2 | 1 | external | `author_problem` ignores `GIT_AUTHOR_*`/`EMAIL` from the environment | confirmed | minor | declined: the spec checks `git config` only; agents take their environment from the login shell, not from the server's, and a refusal with a hint is the safe side; left to the human at the merge gate |
| E3 | 1 | external | a title refused on resume is not tested | refuted | — | dropped: `tests/test_runtime.py::test_a_resume_with_a_title_is_refused`; `POST /api/sessions` always passes `resume=False` |

Metrics: 2 local rounds, 1 external, 0 substitutes. Local confirmed 3 (1 blocker, 1
important, 1 minor), refuted 0; external confirmed 1 (minor), refuted 2. Findings in code
changed by the developer's cleanup (`c94bb3f`): 0.

## Checks

- CI of PR #99 on `30bd1e7`: 23/23 pass with `ci-ok` (unit 3.10/3.13, integration ×6,
  ui ×2, js, container amd64/arm64, smoke macOS/Ubuntu × 4 providers).
- Round 2: `openspec validate --specs --strict` 35 passed, 0 failed; the change valid in
  strict mode.
- Round 1 on `9c1390b`: `make lint` clean, `make test` 3519 passed,
  `tests/integration/test_scratch_start.py` 2 passed.
- At the archive: the new capability's placeholder Purpose was written;
  `openspec validate --specs --strict` 36 passed.

## Not checked (residual risk)

- `make web` and the UI e2e tests were not run locally by the reviewer: CI (ui ×2, the
  web build) and the developer (904 vitest, 21 UI) ran them.
- `make check` as a whole was not run locally; CI covered its equivalent.
- Live tests were not run, though `runtime.py` changed.
- The external reviewer read only the Python part.

Found on the way: none.
