# LAD-31 release-candidates: review report

Pull request #13 `feature/lad-31-release-candidates` → `main`. Scale: full change, review
depth: breadth. Head reviewed last: `d610bc0`, after the archive commit `b37a85d` and a merge of `main`
with LAD-32 (usage telemetry). Release
candidates on PyPI for every minor release, an RC offered only to a LADO on an RC
(`update.offered`), the pre-release mark in `lado doctor`, its report and the UI's System
panel, `scripts/release_check.py` in the Release workflow (a final must be the code of its
last RC), `docs/release.md` and the openspec change; no provider code, no schema
migration, no MCP change.

## Rounds

- **Round 1** (`cdbaf19..76f470b`, the whole PR): local breadth pass with every lens and
  the architecture against AGENTS.md; the spec's requirements and scenarios covered by
  code and tests, `tasks.md` checked whole, D1–D11 kept. Found F1–F6.
- **External round 1** by the Claude Code Action (request 07:10:18 UTC, "Claude finished"
  07:11:14 UTC, `cdbaf19..76f470b`): no blockers, three minor (F7–F9).
- **Round 2** (`76f470b..b2ff7bb`: `cb23a0b`, `3e591e4`, `134b886` and the merge of
  `origin/main` 26e0a4a): local precision pass, clean. The PR's diff still holds only its
  own 31 files; CHANGELOG's conflict resolved with LAD-28's line and this one side by side
  under 0.37.0.
- **Round 3**, after `conflicts` (`b2ff7bb..d610bc0`): local precision pass over the
  archive (`b37a85d`: the living spec's requirements equal the archived delta) and the
  merge of `origin/main` with LAD-32, which touched many of the same files; the
  pre-release marks survived (`doctor.py`, `models.py`, `app.py`, `SystemPanel.tsx`,
  `api.gen.ts`, `offered` in `cli.py` and `self_update.py`), CHANGELOG has both lines
  under 0.37.0, the PR's diff holds 33 files, its own and the archive. Clean.
- **External round 2** by the Claude Code Action (request 07:52:58 UTC,
  `76f470b..d610bc0`): no blockers; agreed with the triage of F7–F9; one remark (F10),
  no defect. It ran no tests.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local: descriptions | The PR description lagged behind `76f470b` (the uv.lock rule, the test count) | confirmed | minor | fixed: description rewritten against `b2ff7bb` |
| F2 | 1 | local: efficiency | `blocks.setdefault(tag, packages(...))` ran `git show` for every changed line | confirmed | minor | fixed in `cb23a0b`; test `test_the_lock_is_read_once_per_side` |
| F3 | 1 | local: docs | The checklist's bare `lado start`/`lado stop` ran the final, not the RC | confirmed | minor | fixed in `3e591e4`: `uvx --from lado==X.Y.ZrcN lado …` |
| F4 | 1 | local: project rules | Long lines in AGENTS.md and design.md | confirmed | minor | fixed in `3e591e4` |
| F5 | 1 | local: comments | The comments of `UpdateInfo.latest` and `released` | confirmed | minor | fixed in `3e591e4` |
| F6 | 1 | checks: CI | CI `ui` red: vitest `ArtifactTab.test.tsx` flake | confirmed (flake, cause outside the work) | — | job rerun, all 12 jobs green; flake in BACKLOG.md P2 (`134b886`) |
| F7 | 1 | external (Action) | A `version = "…"` line in any section of pyproject.toml passes | confirmed | minor | declined: risk accepted in design.md (Risks); no such line outside `[project]` |
| F8 | 1 | external (Action) | No check that the final tag descends from the RC | confirmed | minor | declined: the spec requires equal code, not ancestry (D7) |
| F9 | 1 | external (Action) | The mark's hint reads as a general claim | refuted | — | the mark shows only with `info.prerelease` (`web/src/SystemPanel.tsx`) |
| F10 | 3 | external (Action) | A uv.lock line before the first `[[package]]` counts as another package's and is refused | refuted as a defect | — | by design: only the `lado` package's version line may differ (`scripts/release_check.py`) |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 6 (F1–F6) | 0 | — |
| external, Claude Code Action | 2 (F7, F8) | 2 (F9, F10) | — |

No blocker and no important finding.

Flakes (no code changed for them): `test_agent_liveness.py::test_finishing_a_worker_tells_no_one_it_stopped`
(timeout, `check (3.10)` on `cb52ffd`, passes alone); vitest `ArtifactTab.test.tsx` on
`76f470b` and `b2ff7bb` (F6); `test_agent_env::test_a_slow_shell_times_out` in a local
`make test`, 2 of 2 alone; vitest `Composer.test.tsx` locally, passed again.

## Found on the way

- The `ArtifactTab.test.tsx` (`document.title`) flake, in BACKLOG.md P2 (`134b886`).

## Checks

- Local: `make lint` clean; `make test` 2573 passed, `make web` 663 passed, UI e2e
  `tests/ui/test_system_panel.py` 4 passed (`76f470b`); `tests/test_release_check.py`,
  `tests/test_release_workflow.py`, `tests/test_update.py` 75 passed (`b2ff7bb`);
  `openspec validate --specs --strict` passed. On `d610bc0`: `make lint` clean, `make test`
  2712 passed, `make web` 694 passed (stale types ok), UI e2e `test_system_panel` 4
  passed, `openspec validate --specs --strict` 11 passed.
- CI of PR #13 on `b2ff7bb` and on `d610bc0` green: check (3.10, 3.13), js, ui, smoke ubuntu/macos ×
  claude/codex/kilo/opencode.
- Not run: `make check` and `make test-integration` as a whole, live and smoke locally (CI
  and the release run them). No change to `providers/`, `hooks.py`, `mcp_server.py`,
  `runtime.py`, `agent_env.py` or `tests/live/`.

## Residual risk

- The Release workflow's `release_check.py` step runs only on a tag push: covered by the
  script's unit tests (14) and a test of the step's place; its first real run is the first
  RC.
- The pre-release marks were not seen in a browser on a real RC: the test server runs the
  working copy's version; vitest and UI e2e cover them with mocked server answers.
- F7 and F8 as accepted.

## Result

Converged after round 3 (2 of 2 external rounds).
