# LAD-215 status-marks-test-waits-for-team: review report

Pull request #232 `fix/lad-215-status-marks-team-wait` → `main`. Scale: tweak, review depth:
precision. Head reviewed: `664bb9e5`. The flake of `tests/ui/test_status_marks.py`, a race in the
test and not a defect of LADO: `Locator.all()` does not wait, and the head draws no team until the
agents have loaded. The test now waits with `to_have_count(2)` before `.all()`, and the entry goes
from BACKLOG.md. Tests only: no API, schema, MCP, CLI or UI change, no CHANGELOG.md line. No delta.

## Rounds

1. Local, precision, `59899a57..664bb9e5`: no wide pass needed, only a test changed, with no
   business logic or user data in the diff. No findings.
2. External 1, Claude Code GitHub Action: no findings. `Files not read` was empty, but
   `tests/ui/test_status_marks.py` was read as the diff and its imports only, and the reviewer ran
   no tests. It is the same model family, so "nothing found" weighs less.

External rounds used: 1 of 1.

## The human's decisions

- **Gate `merge_ok`, approved** with no comment.

## Findings

None, local or external. Found on the way: none.

## What the code shows

- `HeadTeam` returns `null` until the agents have loaded (`web/src/Team.tsx:639`), so there are no
  buttons and `.all()` gives an empty list.
- On level 0 the team has two buttons only: the list button comes at `step.level > 0`
  (`Team.tsx:586`). The level is fitted in a microtask through `flushSync` (`Team.tsx:446-461`), so
  Playwright sees no state in between; were it to, the accessible-name checks that follow catch it.
- The proposal's numbers hold: sixteen `.all()` calls, and a wait stands before `test_chat.py:84`
  and `test_kits_page.py:217`.
- BACKLOG.md lost that entry alone, and nothing else in the repository mentions it.

## Checks

| Check | Head | Result |
|---|---|---|
| The test with `-m ui -n0`, no delay | `664bb9e5` | 1 passed |
| The old test (`origin/main`), the response of `…/agents` held back 3 s | `origin/main` | 1 failed, `ValueError: not enough values to unpack (expected 2, got 0)` |
| The test with the fix, the same delay, 2 runs | `664bb9e5` | 2 of 2 passed |
| The test with the fix, a delay of 6 s | `664bb9e5` | 1 passed |
| `make lint` | `664bb9e5` | clean |
| `openspec validate status-marks-test-waits-for-team --strict` | `664bb9e5` | valid |
| `openspec validate --specs --strict` | `664bb9e5` | 62 passed, 0 failed |
| A trial archive with `--skip-specs`, then the specs | `664bb9e5` | 62 passed, 0 failed |
| CI of the pull request (run 42275956314) | `664bb9e5` | `ci-ok` green: 15 pass, smoke skipped, every file on the skip list |

The runs with a delay came from copies of the tree in a temporary folder, with an outside pytest
plugin; the working tree did not change. `make test`, the integration tests and the rest of the UI
tests ran in CI, not locally. The live tests were not needed: `providers/`, `hooks.py`,
`mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not change.

## Metrics

Rounds: 1 local, 1 external, 0 stand-in. Confirmed: 0 local, 0 external. Refuted: 0 local, 0
external. Findings in code changed by the developer's cleanup: 0.

## What was not checked

- AC-3 (20 and 5 runs in a row) was not repeated by the reviewer: it is the developer's result. No
  one ran the test under real load.
- The margin of the wait was not measured. `to_have_count(2)` waits the 5 s of `expect`. The pass
  with a delay of 6 s says nothing against that: `time.sleep` in the handler also blocks the test's
  own Python process. Agents later than the timeout fail the test with a clear message on the
  number of buttons, not the `ValueError`: a usual timeout, as of every `expect` in the suite.
- The other two unpackings of `.all()` stay out of scope by design.
