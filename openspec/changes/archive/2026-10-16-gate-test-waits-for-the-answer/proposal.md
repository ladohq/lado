Task: LAD-72

## Why

The UI e2e test `tests/ui/test_gates.py::test_the_human_answers_a_gate_on_its_tab` failed
in CI (job `ui (2)`, PR #56, run 38717589640, attempt 1; the rerun passed) on its check of
the next step's text: the last message to the supervisor was not the step of `plan` but
LADO's request `recommend on gate #1: ship/x at check` (message #3), whose body has no
`Note from the previous step: rejected: split the form first`.

Root cause, **a race in the test, not a defect of LADO**: the human's answer moves the run
in two writes. `runs.answer` first stores the move (`state.update_run`: the gate closed,
the run in `plan` with its note, one transaction), then tells whoever acts now
(`runs._arrived` → `_deliver_step` → `runtime.post`, which queues the step message from
`lado` in a transaction of its own). The UI's feed shows the closed gate as soon as the
first write commits, while `POST /api/sessions/{name}/gates/{gate}/answer` is still in the
second. The test waits only for what the page shows (the gate's closed line, the card
gone), then reads lado.db at once: the run's state is already there (that check passes),
the step message may not be yet, and the newest message to the supervisor is then the
recommendation request queued when the gate opened. On a loaded runner the gap is wide
enough to lose.

The two writes are LADO's design (`runs._arrived`: "the transition is stored already"):
the step goes through the queue and its hand-over, which cannot share the run's
transaction; a session resumed between them gets the step anew (`session resumed` names
what waits). No user sees the gap: the step reaches the chat by the feed a moment later.

## What Changes

- The test waits for the answer's own response before it reads lado.db: the Reject click
  runs inside `page.expect_response` for the POST of
  `/api/sessions/<session>/gates/1/answer`, and the response is checked to be OK. The
  server answers only after `runs.answer_text` returned, so after the step message is
  queued. Every check of the test stays as it is, the step's text included.
- No product code changes, no delta (no behaviour rule changes), no CHANGELOG line, no
  version bump.

## Scope

`tests/ui/test_gates.py`, `test_the_human_answers_a_gate_on_its_tab` only.

## Out of scope

- Queueing the step message in the run's transaction (`state.update_run`): it would close
  a gap no user sees, at the cost of splitting `runtime.post` into a queue and a hand-over
  for every caller of `runs._arrived` (flow_advance, flow-set, gates, run start); the
  two-write order is by design and already recovered on resume.
- Polling lado.db for the step message (`agent_helpers.wait_for`): also green, but it
  waits by a timeout for something the server's response marks exactly; the response is
  the deterministic sign.
- The other tests of `tests/ui/` that read lado.db: checked, none reads a second write of
  the same action right after the page showed the first (`test_flows_tab.py`'s
  `status == ENDED` is in `update_run`'s transaction; `test_chat.py` waits with
  `wait_for` or reads a single insert).
- The general timeout flakes under load (BACKLOG.md, P1 "`make check` fails on
  timeouts"): another cause.

## Acceptance criteria

- AC-1: With a probe that makes the race certain (a `time.sleep(1)` at the start of
  `runs._deliver_step`, local only, never committed), the test before the fix fails on
  the step's text and the test after the fix passes; the build report shows both runs.
- AC-2: Without the probe the test passes 30 times in a row locally, beside the other
  tests of its file two at a time (`-n 2`, as CI's UI shards run).
- AC-3: No check of the test is removed or loosened; the diff touches only the Reject
  click and adds the response's check.
- AC-4: The pull request's CI (`ci-ok`) is green.

## Impact

- Tests only: `tests/ui/test_gates.py`. No API, schema, MCP, CLI or UI change; nothing a
  user of LADO sees.

## Decisions for the record

- Scale hotfix: a defect with a clear symptom and a proven cause (the CI log names
  message #3, the recommendation request), one test changed; reviewed for precision.
- Fix the test, not the code. Options weighed by long-term cost: (a) wait for the answer's
  response, deterministic, no cost; (b) poll lado.db for the step message, green but
  timeout-bound and a second way of saying "the answer is done"; (c) one transaction for
  the move and the step message, a refactor of `runtime.post` and `runs._arrived` for a
  gap no user sees. (a) is chosen.
- Test layer: the test stays a UI e2e test (layer 4): it checks the gate card in a browser;
  the race is between the feed and the POST's response of a real server.
- The regression proof is deterministic (AC-1, a probe that widens the gap), the 30 runs
  a second check.
- Design principles and ROADMAP unaffected: no provider, no second source of truth, no
  silent drop.
