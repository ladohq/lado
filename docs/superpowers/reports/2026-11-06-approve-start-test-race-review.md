# LAD-221 approve-start-test-race: review report

Pull request #237 `fix/lad-221-approve-start-test-race` → `main`. Scale: tweak, review depth:
precision. Head reviewed: `5264c6b7`. The flake of the project secrets' integration tests, a race
in the test and not a delay in LADO: secrets play no part. A message sent while the supervisor is
still inside `spawn_worker` or `ask_human` comes in that tool's result, where the fake agent does
not act on it. `_approve_and_start` now waits for the supervisor to be idle at its start and
before it answers the question. Tests only: no API, schema, MCP, CLI or UI change, no CHANGELOG.md
line. No delta.

## Rounds

1. Local, precision, `941b875c..5264c6b7`: only a test helper changed, with no business logic or
   user data in the diff. Read by hand: both windows, the status path through `hooks.py`, the
   callers, and a possible third window, `askhuman` after `artifact_write`. No other test has the
   same risk: `supervisor_runs` already waits for idle (`test_agents.py:698-704`).
2. External 1, Claude Code GitHub Action, requested 20:39:42 UTC, answered 20:40:57 UTC: no
   blocking findings. It read the risky file `tests/integration/test_project_sessions.py`, but not
   `proposal.md`, `.openspec.yaml` or `hooks.py`, so it left its question on `idle` open (F4). It
   is the same model family, so "nothing found" weighs less.

External rounds used: 1 of 1.

## The human's decisions

- **Gate `merge_ok`, approved** with no comment: F1, F2 and F3 stay declined.

## Findings

| ID | Source | Finding | Verdict | Level | Fate |
|---|---|---|---|---|---|
| F1 | local | `proposal.md` says "14 passed" for four files that hold 18 tests | confirmed | minor | declined: no effect on behaviour; the right number is in the build report and the pull request's description, and the slip stays in the archive |
| F2 | local, external | The docstring's "where its turn may still run" says more than the two waits do: `askhuman` goes without a wait | confirmed | minor | declined: wording, not a defect; `fake_agent.py:362-364` writes `report` after the tool returns, with no other call in that turn |
| F3 | external | The wait's line appears twice (`test_project_sessions.py:88, 99`) | confirmed | minor | declined: two lines in a test helper, a function of its own adds no clarity |
| F4 | external | `idle` may be true too early: the message is handed over, the status not yet busy | refuted | — | dropped: before each wait an action of the turn is already visible, and the fake agent calls `hook("prompt_submit")` before `work(text)`, which sets BUSY (`hooks.py:176-177`); `fake` has no `says_continued`, so a continued turn goes through it too |

Found on the way: none.

## Checks

| Check | Head | Result |
|---|---|---|
| `make lint` | `5264c6b7` | clean |
| `uv run pytest -m integration -n auto tests/integration/test_project_sessions.py` | `5264c6b7` | 7 passed |
| A copy outside the tree, 4 s delay in `spawn_worker` and `ask_human`, with the fix, four files, `-m integration -n auto` | `5264c6b7` | 18 passed |
| The same copy, the helper of `main`, `test_every_agent_of_a_session_gets_its_project_s_secrets` | `main`'s helper | 1 failed, `timed out after 30s waiting for the brief written`, as on CI |
| `openspec validate approve-start-test-race --strict` | `5264c6b7` | valid |
| `openspec validate --specs --strict` | `5264c6b7` | 62 passed, 0 failed |
| A trial archive with `--skip-specs`, then the specs | `5264c6b7` | 62 passed, 0 failed |
| CI of the pull request (run 42289668345) | `5264c6b7` | `ci-ok` green: unit, 6 integration shards, js, ui, container, smoke on 8 cells |

AC-1, AC-2 and AC-3 are met, tasks 1.1 to 1.4 checked, nothing out of scope done. The live tests
were not needed: `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and
`tests/live/` did not change.

## Metrics

Rounds: 1 local, 1 external, 0 stand-in. Confirmed: 2 local, 1 external (one more external finding
matched F2). Refuted: 0 local, 1 external. Findings in code changed by the developer's cleanup: 1
(F2, the docstring).

## What was not checked

- `make test`, `make check`, the whole of `make test-integration` and `make test-smoke` did not run
  locally: excluded by the settings, and CI covers them. `make test-live` runs only at a release.
- AC-2 (20 runs in a row) was not repeated by the reviewer: it is the developer's result, taken at
  `fee18e2a`. Only the docstring and `tasks.md` changed after it.
- There is no regression test, by design: the window opens only with an artificial delay in the
  product. A new test that sends the supervisor a message in the middle of a turn, outside this
  helper, meets the same race.
- The reviewer's background poll did not recognise the finished comment and waited out the 25
  minute ceiling. The result is unaffected: the answer came in 75 seconds, checked by hand.
