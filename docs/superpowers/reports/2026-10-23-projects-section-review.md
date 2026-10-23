# LAD-134 projects-section: review report

Pull request #151 `feature/lad-134-projects-section` → `main`. Scale: full, reviewed
breadth first. Head reviewed last: `e7be0653` (= the remote head). `providers/`,
`hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` unchanged:
no live tests needed before the merge.

## Rounds

- **Round 1** (`origin/main...1418d0d3`, 43 files): a local breadth pass (spec, tests,
  silent failures, comments, types, general, the architecture against AGENTS.md, the
  screenshots), with the points of gate #98: F1-F7.
- **Round 2** (`1418d0d3..a051099c`): a local precision pass, no new finding; **external
  1** (Claude Code GitHub Action, request 6364090011, answer 6364093723): E1-E3. Read in
  full: `ProjectVariables.tsx`, `Projects.tsx`, `project_secrets.py` and the canary;
  the project and secret routes of `app.py`, the diff of `launch.py`, `check_new`,
  `create`, `suggest_id`, `overrides`, `putSecret`.
- **Round 3** (`a051099c..e7be0653`): a local precision pass, no new finding; **external
  2** (request 6364319131, answer 6364323010): no defect, `Projects.tsx` read in full.
  Its "not a defect" note (`drop()` also drops a read caused by a session's start or
  stop during a change) was checked: the change's answer carries `running`
  (`launch.project_info`), the next event or focus mends the rest.

External rounds used: 2 of 2. The external reviewer is of the same model family, so its
"nothing more" weighs less.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | New project: the answer to `?title=` overwrote an id edited by hand; Create was enabled with the old id | confirmed | important | fixed in `9e38c859`, two vitest tests seen red |
| F2 | 1 | local | the docstring of `project_secrets` did not say the server does not read values | confirmed | minor | fixed in `d0fe442f` |
| F3 | 1 | local | `projects.md` counted the built variables page as S7 | confirmed | minor | fixed in `d0fe442f` |
| F4 | 1 | local | Enter sends a `PUT` while one is busy | confirmed | minor | declined: the `PUT` is idempotent; an empty secret value is refused by the core |
| F5 | 1 | local | "None" in the docstring of `names` that returns `[]` | refuted: the English word, not Python's `None` | — | dropped |
| F6 | 1 | gate #98 (AC-10) | the UI e2e test did not read the browser's console | confirmed | important | fixed in `a051099c`, the probe seen red |
| F7 | 1 | gate #98 (#1158) | the stub row with the project's id was not in the UI e2e test | confirmed | important | fixed in `a051099c` |
| E1 | 2 | external 1 | a page read begun before a change showed the state before it | confirmed | important | fixed in `e7be0653`: `useLatest` → `{read, drop}`, `changed` calls `drop()`; a vitest test with a slow `GET` red on the old code |
| E2 | 2 | external 1 | Create disabled without a reason when `suggest_id` gives an empty id | confirmed | minor | declined: only a title like "41 underscores and a letter"; nothing wrong is created |
| E3 | 2 | external 1 | a reread on every change of the session feed | refuted: the key is `SessionStatus` (`runtime.py`), changed only at a start, stop or loss of a session | — | dropped |

Metrics: 3 local rounds, 2 external, 0 substitutes. Local confirmed 6 (F1-F4, F6, F7),
refuted 1 (F5); external confirmed 2 (E1, E2), refuted 1 (E3). Findings in code changed
by the developer's cleanup: 0. Every important finding has a test seen red.

## Checks

- `1418d0d3`: `openspec validate --specs --strict` green; `-m integration` on
  `tests/integration/test_project_secrets_canary.py`: 2 passed.
- `a051099c`: `make test` 4154 passed, 2 skipped; `openspec validate projects-section
  --strict` valid.
- `e7be0653`: `make lint` green; `make web` green (vitest 1025 passed); `-m ui` on
  `tests/ui/test_projects_section.py`: 3 passed; CI 23 of 23, `ci-ok` green.
- At archive: `openspec validate --specs --strict` 46 of 46.

## Found on the way

- Nothing outside the scope.

## Not checked

- `make check` and `make test-integration` as a whole ran only in CI (green); smoke in
  CI, `make test-live` not run (at the release).
- The external rounds read `app.py`, `launch.py` and `projects.py` by their routes and
  diff, not whole; their parts outside the diff are unchanged by this pull request.
- The manual check of the pull request's description (temporary `LADO_HOME`,
  `LADO_REPOS`, `LADO_TMUX_SOCKET`) is the human's.
