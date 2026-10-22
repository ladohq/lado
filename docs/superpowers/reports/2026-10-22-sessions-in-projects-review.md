# LAD-125 sessions-in-projects: review report

Pull request #138 `feature/lad-125-sessions-in-projects` → `main`. Scale: full, reviewed
breadth first. Head reviewed last: `3e3ddf4` (= the remote head). Sensitive modules
changed: `runtime.py` and `providers/base.py`; live tests were not run, by the human's
decision (#824).

## Rounds

- **Round 1, local** (breadth, `origin/main...60c4956`): F1.
- **Round 2, local** (precision over `60c4956..b85b133`) and **external 1** (Claude Code
  GitHub Action; triage in PR comment 6338250476): E1-E5. The review converged; the human
  declined merge_ok to fix E4 and F2 and have a second external round read the areas the
  first had not.
- **Round 3, local** (precision over `b85b133..91423bb`, `docs/design/ui.md` only, checked
  against the code) and **external 2** (triage in PR comment 6340198846): G1-G3, no
  blockers.
- **Round 4, local** (precision over `91423bb..3e3ddf4`), after the first archive attempt
  failed: `openspec validate --specs --strict` refused four MODIFIED requirements longer
  than 500 characters once merged into the living specs. The delta moved the new
  behaviour into ADDED requirements and kept the exact texts in scenarios; meaning
  unchanged, no findings. No external round: the cap was reached.

External rounds used: 2 of 2. The external reviewer is of the same model family, so its
"nothing more" weighs less.

## Who read which area

| Area | Local rounds | External rounds |
|---|---|---|
| core/CLI (`projects.py`, `state.py`, `runtime.py`, `clone.py`, `scratch.py`, `cli.py`, `providers/base.py`) | 1, 2 | 1, 2 |
| server (`app.py`, `launch.py`, `clones.py`, `models.py`) | 1 | 1, 2 |
| UI (`Launch.tsx`, `Sessions.tsx`, `SessionDetails.tsx`, `styles.css`) | 1 | 1, 2 |
| specs: `projects` delta | 1, 4 | 2 (in part, before `3e3ddf4`) |
| specs: `proposal.md`, `design.md`, `tasks.md`, the `repos-folder`, `session-clone`, `session-scratch` deltas | 1, 4 (`repos-folder`) | none |
| docs: `docs/design/ui.md` | 1, 3 | 2 |
| docs: `docs/cli.md`, `docs/design/projects.md`, `modules.md`, `agents.md`, CHANGELOG | 1, 2 | none |
| tests: `tests/integration/test_project_sessions.py`, `tests/ui/test_launch.py` | 1 | 2 |
| tests: `test_runtime_projects.py`, `test_projects_core.py` | 1 | 2 (in part) |
| tests: the other unit files, `tests/ui/test_session_head.py` | 1 | none |

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (architecture, cross-process) | an agent's `lado mcp` got `LADO_REPOS` only from its login shell, so `start_session` in a project missed the repository and the refusal inside `projects/` checked another folder | confirmed | important | fixed in `b85b133` (human's decision #824); test `tests/test_providers.py::test_lado_passes_its_workspace_on_to_each_agent` |
| E1 | 2 | external 1 | `project delete` does not forget a stopped pre-S3 session in the project's folder | refuted: by design (`docs/cli.md`, design Risks, #808) | — | dropped |
| E2 | 2 | external 1 | the folder is removed before the sessions are forgotten | refuted: by design (D9) | — | dropped |
| E3 | 2 | external 1 | the `--repo <name>` hint is offered for a folder that does not exist yet | confirmed | minor | declined: the spec asks for this text; adding repositories is S4 |
| E4 | 2 | external 1 | `ui.md` did not say the New session window also refuses a folder that already has a session | confirmed | minor | fixed in `91423bb` |
| E5 | 2 | external 1 | redundant work in `refusal` | refuted (`projects.py:162`) | — | dropped |
| F2 | 2 | local | the PR description named CI of an older head | confirmed | minor | fixed in the PR description |
| G1 | 3 | external 2 | when a project's folder is a symlink, sessions in its target block `delete` while `delete` only unlinks the link | confirmed | minor | declined: fails safe (refuses, removes nothing); an edge for S7 |
| G2 | 3 | external 2 | the project in the session head waits for `about` | refuted: by design (D12) | — | dropped |
| G3 | 3 | external 2 | test gaps (CLI exit codes, Clone into / Create in refusals, delete failures) | refuted: covered in `test_cli.py`, `Launch.test.tsx`, `test_runtime_projects.py`, `test_projects_core.py` | — | dropped |

Metrics: 4 local rounds, 2 external, 0 substitutes. Local confirmed 2 (F1, F2); external
confirmed 3 (E3, E4, G1), refuted 5 (E1, E2, E5, G2, G3); local candidates refuted 5.
Findings in code changed by the developer's cleanup: 0.

## Checks

- Round 1 (`60c4956`): `make lint` green; `make test` 3775 passed, 1 skipped;
  `tests/integration/test_project_sessions.py` 7 passed; `make web` green; UI 40 passed,
  1 flake; both `openspec validate` green.
- Round 2 (`b85b133`): F1's test and its neighbour, 2 passed.
- Round 4 (`3e3ddf4`): `openspec validate sessions-in-projects --strict` valid; a trial
  archive in a scratch copy, then `openspec validate --specs --strict`: 45 passed.
- CI on `3e3ddf4`: 23 of 23, container and smoke included.
- At archive: `openspec validate --specs --strict` 45 of 45.

## Found on the way

- A flake of the new UI test
  `tests/ui/test_launch.py::test_a_folder_in_a_project_is_refused_with_the_projects_command`
  (empty Where hints under load; passed twice alone with `-n0`).

## Not checked

- No external round read `proposal.md`, `design.md`, `tasks.md`, the three small deltas,
  the spec rework of `3e3ddf4`, `docs/cli.md`, `projects.md`, `modules.md`, `agents.md`,
  CHANGELOG, most unit tests and `tests/ui/test_session_head.py`; all were read locally.
- Live tests, though `providers/base.py` changed (#824).
- Full `make check` and `make test-integration` ran only in CI.
- The PR's manual check is the human's.
