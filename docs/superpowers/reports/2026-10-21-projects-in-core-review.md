# LAD-123 projects-in-core: review report

Pull request #131 `feature/lad-123-projects-in-core` → `main`. Scale: full, reviewed wide
first with the lenses spec, tests, silent failures, comments, types, general and the
architecture against AGENTS.md. Head reviewed last: `acbe045` (= the remote head). In
`runtime.py` `outside_repos` became `outside_workspace`, and the container no longer has a
"no workspace" branch, so it now warns of any folder outside the workspace;
`providers/`, `hooks.py`, `mcp_server.py`, `agent_env.py` and `tests/live/` did not
change.

## Rounds

- **Round 1, local** (wide, `origin/main...06d056a`): F1 (important), F2–F5 (minor). The
  developer's deviations checked there (`MIGRATIONS[31]` keyed by the step's source
  version; the living spec's Purpose edited directly) became no findings.
- **Round 2, local** (precision over `06d056a..acbe045`): F1 and F4 resolved, no new
  findings.
- **Round 1, external** (Claude Code GitHub Action, request 19:46:41Z, answer 19:47:55Z):
  read only commit `acbe045` and the spec check; confirmed F1 and F4, new minor E1, E2.
- **Round 2, external** (request 19:49:01Z for the whole diff, answer 19:49:54Z, comment
  6325115414): partial by its own words, it read `projects.py`, `cmd_project` and
  `creating_project` whole, and not `doctor.py`, `clone.py`, `scratch.py`, `runtime.py`,
  `server/`, `Launch.tsx`, the spec deltas or the tests. New: E3 (minor), E4 and E5
  (refuted). It is of the same model family, so its "nothing more" weighs less.

External rounds used: 2 of 2.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (spec, comments) | the `session-clone` living spec after the archive still names `~/lado` the default clone folder (scenario "The clone is there already", requirement "A clone of another repository suggests a free folder"), against AC-10 | confirmed | important | fixed in `acbe045`: three requirements MODIFIED in the delta; the trial archive and `--specs --strict` give 44 passed |
| F2 | 1 | local (tests, silent failures) | `delete`'s unpushed check misses a repository at the root of the project folder itself, commits on a detached HEAD and stashes | confirmed | minor | declined: the code meets the spec ("repositories directly in it", branches), and `--yes` is always needed; widening it is the human's or S3/S4's |
| F3 | 1 | local (general) | a worktree right in the project folder is listed twice | confirmed | minor | declined: cosmetic |
| F4 | 1 | architecture ("Only what is used") | `state.add_project` was called by tests only | confirmed | minor | fixed in `acbe045`: removed, the test uses `creating_project`, `modules.md` corrected |
| F5 | 1 | local (comments) | for a linked folder `delete` shows work in the link's target and says "with everything in it", yet removes the link only | confirmed | minor | declined: errs on the safe side; `docs/cli.md` says only the link goes |
| E1 | ext 1 | external | odd line breaks of the "lado start refuses…" paragraph in the `session-clone` delta | confirmed | minor | declined: copied from the living spec as it is |
| E2 | ext 1 | external | `docs/design/modules.md:316` wider than its neighbours | confirmed | minor | declined: cosmetic |
| E3 | ext 2 | external | `unpushed()` calls `iterdir()` outside `try`: an unreadable project folder gives an `OSError` traceback instead of `lado: …` | confirmed | minor | declined: a rare error path, raised before anything is deleted |
| E4 | ext 2 | external | branches diverged from upstream (ahead and behind) | refuted: `"ahead" in track` covers `[ahead N, behind M]` | — | dropped |
| E5 | ext 2 | external | a worktree outside the project folder keeps stale metadata | refuted: its repository goes with the folder, its uncommitted work is shown before | — | dropped |

Metrics: 2 local rounds, 2 external, 0 substitutes. Local confirmed 5 (F1–F5), refuted
0; external confirmed 3 (E1–E3), refuted 2 (E4, E5). Findings in code changed by the
developer's cleanup: 0.

## Checks

- `make lint` and `make test` (3685 passed) on `06d056a`; the integration file
  `test_projects_process` (7 passed); `test_state` and `test_projects_core` (215 passed)
  and `make lint` on `acbe045`.
- `openspec validate --specs --strict`: 44 of 44 after the archive.
- CI 23 of 23 on `acbe045`, `ci-ok` green.

## Not checked

- Both external rounds read the diff in part: `doctor.py`, `clone.py`, `scratch.py`,
  `runtime.py`, `server/`, `web/src/Launch.tsx` and the tests had only the local wide
  round.
- The reviewer did not run the UI e2e test (`tests/ui/test_launch.py`), `make web`, the
  smoke or container tests locally (CI ran them, green), and did not compare the Where
  screenshots with the mockup `mockup-workspace-where.html`.
- The manual check of the pull request's description was not run, but for the model of
  its step 13 (`worktree remove`).
- Live tests after the `runtime.py` change: the human's decision.
- F2 and E3 stay open as accepted.

Found on the way: nothing.
