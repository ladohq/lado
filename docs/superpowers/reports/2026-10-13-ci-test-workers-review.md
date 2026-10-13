# LAD-41 ci-test-workers: review report

Pull request #19 `fix/lad-41-ci-test-workers` → `main`. Scale: tweak, review depth:
precision. Head reviewed last: `59f44c1`; the archive commit follows it. Changed:
`.github/workflows/ci.yml` (the integration step `-n0`, the UI step `-n 2`, each with a
comment), `tests/test_ci_workflow.py` (a test that pins the pytest commands of jobs
`check` and `ui`), the CI paragraph of AGENTS.md; nothing in `src/` or `web/`, no
provider code, no schema migration, no MCP change.

## Rounds

- **Round 1** (`origin/main..59f44c1`): local precision pass with a check against the
  change, then external round 1 by the Claude Code Action (request 13:17:15 UTC, "Claude
  finished" 13:18:06 UTC): no blockers, three observations (F1-F3). External rounds used:
  1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (spec); external | `proposal.md` AC-4 and Decisions describe the first verification rule (three whole-run reruns); the human's rule (question #4467: a run counts when the integration steps of both Pythons and the `ui` pytest step are green, other failed jobs rerun with `--failed`) is written only in `tasks.md` 2.1 | confirmed | minor | declined: the human's rule is in `tasks.md`, the build report and the PR description; left to the human at the merge gate, approved as is |
| F2 | 1 | external | AGENTS.md keeps a short line (`commands). A cell is`) after the paragraph was rewrapped | confirmed | minor | declined: cosmetic, the text is right |
| F3 | 1 | external | the integration step with `-n0` is about 1.7 times slower; `check (3.10)` up to 8:37 | refuted (no defect) | — | the cost the design states (Impact); within CI's 40-minute ceiling (AC-5) |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 1 (F1) | 0 | 0 |
| external, Claude Code Action | 2 (F1 again, F2) | 1 (F3) | — |

No blocker and no confirmed important finding; no fixing commits.

## Found on the way

- The smoke on macOS with Codex fails now and then with "the supervisor's turn reached no
  model API" (`tests/smoke/test_smoke.py`): 3 of the last 25 CI runs (38395055244,
  38391058624, 38403448248), each green on rerun. Outside the task; for BACKLOG.md with
  the task that stabilises the flakes.

## Checks

- `make lint` exit 0; `uv run pytest -n0 tests/test_ci_workflow.py
  tests/test_workflow_security.py` 18 passed; `openspec validate ci-test-workers --strict`
  valid.
- AC-4 by the human's rule (#4467): run 38399466423, attempts 1, 2 and 3+4 (in the build
  report and the PR description).
- CI on `59f44c1`, run 38403448248: attempt 1 green but the smoke macOS codex flake above;
  attempt 2 (`--failed`) green. Times of attempt 1: `check (3.10)` 5:13, `check (3.13)`
  6:50, `ui` 5:08.
- Not run: integration and UI locally (CI is what this change is about); live tests (not
  needed: `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py`,
  `tests/live/` untouched).

## Residual risk

- Few green runs (three counted and one on `59f44c1`) against five kinds of flake: watch
  the integration steps on the next merges. The unit `test_terminal_socket`, the vitest
  `ArtifactTab` and `Launch` and the smoke macOS codex flakes stay; their stabilisation is
  a task of its own.
