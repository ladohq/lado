# LAD-139 project-delete: review report

Pull request #159 `feature/lad-139-project-delete` → `main`. Scale: full, reviewed
breadth first. Head reviewed last: `9e5af5ff` (= the remote head). `providers/`,
`hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` unchanged,
so no live tests are needed. Schema migration: no.

## Rounds

- **Round 1** (`origin/main..c894b6e2`, the whole pull request): a local breadth pass
  (spec, tests, silent failures, comments, types, general, the architecture against
  AGENTS.md; screenshots against `docs/design/ui.md` and the mockup) and **external 1**
  (Claude Code GitHub Action, request comment 6374749377, triage 6374792125): E1-E5.
- **Round 2** (`c894b6e2..9e5af5ff`): a local precision pass over the delta (the fix of
  E1, the removal of L1, a search for other `:(exclude)` pathspecs: only
  `fingerprint.py`, a constant without globs) and **external 2** (request comment
  6375004545, triage 6375030418): E6, E7; no new blocker or important.

External rounds used: 2 of 2. The external reviewer is of the same model family, so its
"nothing more" weighs less.

## Coverage of the risky code (#949)

External round 2 read whole: `projects.py` (`set_variable`, `set_secret`, `_own_root`,
`_not_pushed`, `unpushed`, `_detached`, `_stashes`, `_checkout_lines`, `Deletion`,
`deletion`, `delete`), `project_secrets.py`, `app.py` (`project_core` and both deletion
routes), `ProjectDelete.tsx`, `cloneJob.ts` and the canary.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| L1 | 1 | local | `web/tsconfig.tsbuildinfo`, a build artefact, committed by accident | confirmed | minor | fixed in `9e5af5ff`: the file removed |
| L2 | 1 | local | a `set_secret` that writes its file between `remove_all` and `delete_project` in `delete` answers success while the data folder stays | confirmed | minor | declined: a window between two adjacent statements; the result is loud (`create` refuses "is left from a project"), no secret is inherited; only a lock could close it |
| E1 | 1 | external 1 | the pathspec excludes of `_checkout_lines` are globs: a repository folder named `x*` hides the root's changes | confirmed | important | fixed in `9e5af5ff`: `:(exclude,literal)<name>`; test `test_a_repository_named_like_a_glob_hides_none_of_the_roots_changes[x*,x?,[x]y]`, seen red with the old exclude (3 failed) |
| E2 | 1 | external 1 | `delete` always builds the full preview, the CLI twice | confirmed | minor | declined: decision D1, the refusal comes from one preview; git has `GIT_TIMEOUT` |
| E3 | 1 | external 1 | `DELETE` is not bound to the preview shown | confirmed | minor | declined: running sessions refuse at the moment of deletion; a preview token is new, out of the step |
| E4 | 1 | external 1 | a ref read in the cleanup of `useCloneJob` | refuted | — | no ESLint in the project, `make web` green; the cleanup reads the current job on purpose |
| E5 | 1 | external 1 | delete and a new create in the `set_secret` window inherit the secret | refuted | — | `create` refuses while the data folder is left (`projects.py:285`); external 2 agreed |
| E6 | 2 | external 2 | a link entry inside the project folder shows up in the preview as unpushed work | confirmed | minor | declined: older than the change (the same filter on main); nothing is deleted through the link, only a false alarm; found on the way, for BACKLOG.md |
| E7 | 2 | external 2 | `onDeleted` may refetch the deleted project | refuted | — | `onDeleted` reloads the project list from the outlet context; `navigate("/projects")` leaves the page |

## Checks

Round 1 (on `c894b6e2`): lint green; unit 4232 passed, 2 skipped; `make web` vitest 1104
passed; UI (`-m ui`, 4 files) 54 passed; integration, the canary, 2 passed; openspec
valid.

Round 2 (on `9e5af5ff`): `make lint` green; `make test` 4235 passed, 2 skipped; the new
test 3 passed, and 3 failed under a probe with the old exclude; `openspec validate
project-delete --strict` valid; `openspec validate --specs --strict` green; CI 23/23
pass, `ci-ok` included. UI and the canary not rerun locally on `9e5af5ff` (the delta
touches only the root's `git status`); CI ran them on that head.

## Found on the way

- E6: `projects.unpushed` takes link entries of the project folder (`entry.is_dir()` and
  `lexists(entry / ".git")` follow the link). Fix: `not entry.is_symlink()` in the filter
  and a test after `test_the_removal_of_a_link`. P3, size S.

## Residual risk

- `make test-integration` as a whole, smoke and live not run locally: CI ran
  integration and smoke (green); live not needed.
- The test of an unreadable folder is skipped under root.
- The manual check on temporary `LADO_HOME`/`LADO_REPOS`/`LADO_TMUX_SOCKET` with
  `LADO_TELEMETRY=0` was left to the epic lead; the reviewer did not do it.
- The L2 race stays.
