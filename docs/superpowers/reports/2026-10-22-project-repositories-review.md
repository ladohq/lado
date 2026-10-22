# LAD-128 project-repositories: review report

Pull request #141 `feature/lad-128-project-repositories` → `main`. Scale: full, reviewed
breadth first. Head reviewed last: `a1830c9` (= the remote head). `providers/`,
`hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` unchanged, so
no live tests were needed. No schema migration.

## Rounds

- **Round 1** (`853ba87..72b80c1`, the whole pull request): a local breadth pass (spec,
  tests, silent failures, comments, types, general, architecture against AGENTS.md) and
  **external 1** (Claude Code GitHub Action, comment 6347479399): X1-X7, N1, M1.
- **Round 2** (`72b80c1..a1830c9`): a local precision pass over the delta, X1's probe
  run again, and **external 2** (comment 6348001799): Y1-Y3, L1, L2; no new blocker or
  important finding.

External rounds used: 2 of 2. The external reviewer is of the same model family, so its
"nothing more" weighs less.

## Who read which area

| Area | Local rounds | External rounds |
|---|---|---|
| core/CLI (`projects.py`, `clone.py`, `scratch.py`, `cli.py`) | 1, 2 | 1, 2 (delta) |
| server (`app.py`, `clones.py`, `launch.py`, `models.py`) | 1, 2 | 1, 2 (`clones.py`, delta) |
| OpenAPI and types (`web/openapi.json`, `api.gen.ts`) | 1, 2 (stale check empty) | none |
| specs (`openspec/changes/project-repositories/`) | 1, 2 | none (asked by name in 2) |
| docs (`docs/cli.md`, `projects.md`, `modules.md`, `ui.md`) | 1, 2 | none (CHANGELOG only) |
| tests | 1, 2 | none (asked by name in 2) |

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| X1 | 1 | external 1 | `repo remove` removed a repository of another project when the project's folder was a link to a neighbour project's folder | confirmed | important | fixed in `a1830c9`: `projects._own_folder`, asked by `new_repo_folder`, `adds_to`, `removal`; tests in `test_project_repos.py`, seen red first |
| M1 | 1 | local | `--name ""` and `name: ""` silently took the name from the URL | confirmed | minor | fixed in `a1830c9` (`is not None`); tests in `test_cli.py`, `test_project_repos.py`, `test_server_projects.py` |
| N1 | 1 | external 1 | `ADD_HINT` declared below `_hint` | confirmed | minor | fixed in `a1830c9` |
| X2 | 1 | external 1 | the CLI computes the preview and the removal with two calls of `removal` | confirmed | minor | declined: a race of milliseconds inside one command, busy checked again; accepted in design.md (Risks), as `project delete` |
| X3 | 1 | external 1 | stopped sessions without a project in the folder are not forgotten or named; worktrees outside the folder stay | confirmed | minor | declined: D6 and Risks (as D9 of S3), in `docs/cli.md`; visibility goes to S7 with S3's G1 |
| X4 | 1 | external 1 | a failed `rmtree` may leave a half-removed folder | confirmed | minor | declined: same behaviour and text as `project delete` |
| X5 | 1 | external 1 | two concurrent `--new` with one name | confirmed | minor | declined: a property of `scratch.make`, older than the change |
| X6 | 1 | external 1 | `--name ""` | — | — | merged into M1 |
| X7 | 1 | external 1 | is `done()` idempotent; is usage tested | refuted: `_CloneProgress.done` clears `self.last`; `test_cli.py::test_project_repo_add_usage` | — | dropped |
| Y1 | 2 | external 2 | the old check in `remove_repo` is now unreachable | confirmed | minor | declined: a second guard before `rmtree`; no test or doc relies on its text |
| Y2 | 2 | external 2 | a race between `_own_folder` and `rmtree` | refuted: `remove_repo` recomputes real paths right before `rmtree` | — | dropped |
| Y3 | 2 | external 2 | the refusal text when `projects/` itself is a link | refuted: both sides go through `realpath(projects_folder())` | — | dropped |
| L1 | 2 | local | long unwrapped lines in `docs/cli.md` and `modules.md` | confirmed | minor | declined: Markdown, the render is the same |
| L2 | 2 | local | a double space in the refusal for an empty name | confirmed | minor | declined: cosmetic; texts pinned by tests |

Metrics: 2 local rounds, 2 external, 0 substitutes. Local confirmed 3 (M1, L1, L2),
refuted 0; external confirmed 7 (X1-X5, N1, Y1), refuted 3 (X7, Y2, Y3); X6 merged into
M1. Findings in code changed by the developer's cleanup: 0 as far as seen (no separate
cleanup commit).

## Checks

- `a1830c9`: `make lint` green; `make test` 3869 passed, 2 skipped; `-m integration` on
  `test_project_repositories.py`, `test_project_sessions.py`, `test_projects_process.py`,
  `test_clone_start.py`, `test_scratch_start.py`: 26 passed.
- `openspec validate project-repositories --strict` valid; `openspec validate --specs
  --strict` 45 of 45; a trial archive in a scratch copy, then the same validation: 45 of
  45.
- OpenAPI and `api.gen.ts` matched the generation in round 1; round 2 changed no API
  model.
- CI on `a1830c9`: 23 of 23, container and smoke included.
- At archive: `openspec validate --specs --strict` 45 of 45.

## Found on the way

- Nothing outside the scope.

## Not checked

- No external round read the specs, docs, tests or OpenAPI; all were read locally only.
- Full `make web`, `make test-integration`, `make check` and the UI e2e tests ran only
  in CI; live tests are not in CI.
- The PR's manual check was run in part by probes (add by clone and `--new`, show,
  remove with and without `--yes`, a link, a project folder that is a link); in full,
  with `lado start --project` and a worker, it is the human's.
- The accepted race between the busy check and `rmtree` (Risks).
