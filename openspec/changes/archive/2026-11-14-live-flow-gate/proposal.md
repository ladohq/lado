Task: LAD-260

## Why

Since LAD-258 the release's check by hand (docs/release.md, 4.3) runs a session of the
built-in supervisor without the kit sdlc, so no person takes a flow through a gate on a
release candidate any more. What is left: the browser tests check the gate's card with the
fake agent (`tests/ui/test_gates.py`), and the live flow test
(`tests/live/test_live.py::test_a_flow_run_moves_on_when_its_worker_reports`) runs the flow
`tiny`, one worker step and the end, with a real CLI. Nothing checks with a real CLI the
path that follows a human's answer at a gate: LADO posts the next step to the run's worker
as a message (`lado.runs.answer` → `_deliver_step` → `runtime.post`), not as the worker's
first input, with the human's answer and comment as the step's note. A provider whose
agent does not take that message, or does not see the note, would pass every test today.

## Options

1. **A gate inside the existing flow test** (chosen): `tiny` becomes step → approval gate
   → a second step of the same worker → end; the test answers the gate as the human with a
   comment, and the second step writes a word that only that comment names. Long-term
   cost: one test grows by about a minute per provider (today's cells take 1:12 to 2:01 of
   their 25 minutes); no second session start.
2. **A test of its own with its own flow**: the same check plus a second session start per
   provider; longer and dearer for nothing new.
3. **Back to a flow by hand in 4.3**: a person on each RC, the cost LAD-258 removed.

## What Changes

- `tests/live/test_live.py`: the flow `TINY_FLOW` gets an approval gate `ok` after `step`
  and a work state `after` of the same role `worker` before `end`; `after` tells the worker
  to write the one word the human's comment at the gate names into `gate.txt`, commit it
  and report `done`. The flow test waits for the gate to open after `step`, answers it as
  the human with approve and a comment naming the word, then waits for the run to end and
  checks that `w1` got the step `after` as a message from LADO and that `gate.txt` on the
  run's branch holds the word. Its docstring and the module's say so.
- `docs/release.md`, section 4.3: the line on the tests that cover flows says that the
  live flow test takes a gate's answer to a real CLI.

No product code, API, MCP tool, CLI or schema changes; no CHANGELOG line (users see
nothing); no version bump of its own.

## Acceptance criteria

- AC-1: The flow `tiny` of the live kit has a gate between two work states of the role
  `worker`, and LADO's flow validator accepts it (the test's kit installs).
- AC-2: The flow test answers the gate through `lado.runs.answer_text`, the same function
  `lado answer`, the popup and the UI's server call, as the human, with the option approve
  and a comment that names a word not written anywhere in the flow.
- AC-3: After the answer, the run's events are exactly `step -done-> ok` by `w1`,
  `ok -approved-> after` by the human and `after -done-> end` by `w1`; `w1` got
  `flow <run>: step after` as a message from LADO and it reached the state read.
- AC-4: `gate.txt` on the run's branch holds exactly the word of the human's comment, and
  `flow.txt` still holds `OK`.
- AC-5: The rest of the test holds as today: the supervisor is told the run ended and kept
  its worktree and branch, the human's merge and `finish_worker` remove them, the passive
  supervisor changed nothing.
- AC-6: `live.yml` on the pull request's branch merged into main runs green on all four
  cells (claude, codex, kilo, opencode), each within its 25 minutes; the test is run by
  hand with `gh workflow run live.yml` after the merge (the key reaches only main).

## Scope

- `tests/live/test_live.py` (the flow `tiny`, the flow test, docstrings).
- `docs/release.md` (4.3's line on flows and gates). `docs/testing.md` describes the live
  workflow, not each test, and stays as it is.

## Out of scope

- The answer reject at the gate: it reaches the worker by the same message with the next
  step; a second round would double the test's time and check nothing new.
- The lead's recommendation on the gate: LADO asks the passive supervisor for one, and
  whether a model gives it is the model's choice; the test neither waits for it nor
  requires it (the human answers without it, as in the product).
- Answering through the UI's server or `lado answer`'s process: the browser and
  integration tests cover those surfaces with the fake agent; the live test checks the
  real CLI's side of the delivery.
- A gate in the release's check by hand (4.3): LAD-258 removed it on purpose.

## Impact

- Live tests only: CI's `ci-ok` is unchanged (`live.yml` is outside it); the live run
  grows by about a minute per cell and a few cents in all.
