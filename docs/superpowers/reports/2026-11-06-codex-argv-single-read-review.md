# LAD-214 codex-argv-single-read: review report

Pull request #233 `fix/lad-214-codex-argv-single-read` → `main`. Scale: tweak, review depth:
precision. Head reviewed: `8a5159c1`. `tests/container/test_codex_sandbox.py` read
`/proc/<pid>/cmdline` twice, and the second read could land inside an `execve`, read empty with
exit 0 and fail with `ValueError: '-a' is not in list`. `codex_pid` became `codex_args`: it returns
the argv of the one read that matched, past `lado.agent_env`, and the asserts print that argv.
Tests only: no delta, no CHANGELOG line, no version bump.

## Rounds

1. Local, precision, `59899a57..8a5159c1`: the diff against the design and AGENTS.md.
2. External 1, Claude Code GitHub Action: no blocker; every file of the diff read, `Files not
   read` empty.

External rounds used: 1 of 1. Stand-ins: 0. Nothing changed after the review.

## The human's decisions

- **Gate `merge_ok`, approved** with no comment: task 3.1 stays dropped, and F1 and E2 stay
  declined.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | `proposal.md`, option A says "a few lines fewer"; the test file grew by 3 lines (+11/-8) | declined: wording of a document, no effect on behaviour |
| E2 | minor | external: the pair check would pass with `-a` and `on-request` side by side elsewhere in the argv; the old code looked at the first `-a` only | declined: the design chose pairs on purpose, the prompt is one element and no such pair exists in a real argv; the external reviewer itself advises keeping it |
| E3 | — | external: tick task 3.1 or delete it, should tools count open items | refuted: `openspec-changes` keeps a dropped task unticked with a line saying why; the trial archive passed with a warning only |

## Deviation from the design

Task 3.1, a `BACKLOG.md` entry that CI loses a failed container test's evidence, was dropped: the
gap does not exist. `scripts/smoke_ci.py:135` copies the evidence and `ci.yml` uploads that folder;
artifact 13465277605 of the failed run (42135583465, attempt 1, amd64) holds `evidence/`, with
`ValueError` at line 53 in `container.log`. `proposal.md` was corrected; the run's `design` artifact
keeps the old wording.

## Checks

| Check | Head | Result |
|---|---|---|
| `openspec validate codex-argv-single-read --strict` | `8a5159c1` | valid |
| `openspec validate --specs --strict` | `8a5159c1` | 62 passed, 0 failed |
| trial archive with `--skip-specs`, `openspec validate --specs --strict` | `8a5159c1` | 62 passed, 0 failed |
| `pytest -m container --collect-only` | `8a5159c1` | 1 test collected |
| `make lint` | `8a5159c1` | clean |
| `make test` | `8a5159c1` | 4823 passed, 7 skipped |
| CI of the pull request | `8a5159c1` | 23 of 23, `ci-ok` green |
| container cells, amd64 and arm64 | runs `42277574716`, `42279245462` | the test passed, 64 passed in each |

Replays: the developer 0 of 4000 on the new code against 13 of 4000 on the old; the reviewer ran
the real `codex_args` on the real chain `lado.agent_env` → `env` → `node`, 300 launches, 0 bad,
matched at `env` 204 times, at `node` 96, at Python never. Without the filter of AC-2 the first
match falls on the Python stage, so the filter can fail.

`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not
change; no live test was needed.

## Metrics

Rounds: 1 local, 1 external, 0 stand-in. Confirmed: 2 (1 local, 1 external). Refuted: 1 (external).
Findings in code changed by the developer's cleanup: 0.

## What was not checked

- The container test was not run locally: the agents' container has no Docker. Its real runs are
  CI's, four green (two runs on two architectures).
- At the old failure rate of about 0.3% a green CI alone does not show the failure is gone; the
  replays above do.
- The cause is shown by reproduction, not read from a log: the failed run's argv was not kept.
- `make check` and `make test-integration` as a whole, `make test-live` and `make test-smoke` were
  not run locally, excluded by the settings; CI ran the integration and smoke tests.

## Found on the way

- `.lado/sdlc.md`, "What CI proves", does not list the container jobs, though `ci-ok` depends on
  them (`.github/workflows/ci.yml:229`). The human keeps that file.
