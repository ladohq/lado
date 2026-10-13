Task: LAD-38

## Why

Symptom: `tests/ui/test_gates.py::test_a_gate_with_a_recommendation_that_disagrees` fails
now and then (CI run 38381186476, commit 66aedfe, job ui): after it asks the supervisor
again for its recommendation on gate #1, the gate's card shows "The supervisor gave no
recommendation" instead of "Supervisor is preparing a recommendation…". It blocks the
release candidate 0.37.0rc1.

Cause: a race between the test and the fake supervisor's turns, not a defect of LADO.
`gated_session` starts run `ship/x` from the test's process, so LADO queues three messages
to the supervisor: the step `plan`, the step `review`, and the request `recommend on gate
#1` (`runs._ask_recommendation` with no notices). The fake supervisor takes them in one or
more turns. At the end of each of its turns `state.recommendations_missed` marks
`missing` every open gate whose recommendation is `asked` and whose request the lead got,
and a request of `NULL` (a notice, which in LADO only the lead's own tool call gives, in
the turn that ends next) counts as got. The test opens the page, waits for the Approve
button and calls `state.ask_recommendation(session, GATE, 1, None, "")`: a notice,
`asked` with request `NULL`. When the supervisor's last turn on those three messages ends
after that call, which on a slow CI runner it can, its turn end marks the gate `missing`,
and the card says so. When the turn ends before the call, nothing moves the gate again,
and the test passes.

Why it is not LADO's defect: in LADO a notice is asked only inside the lead's own
`flow_start` or `flow_advance`, so the turn end that follows is the end of the turn that
got it; the test's notice from outside any turn is a shortcut of the test.

## What Changes

- `tests/ui/test_gates.py`, `test_a_gate_with_a_recommendation_that_disagrees`: before it
  asks again, the test waits until the gate's own request is settled, that is until gate
  #1's recommendation is `missing` (the supervisor's turn on its last queued message
  ended), and checks that no message to the supervisor is pending or sent. From then on
  nothing ends a turn of the supervisor until the test's own answer at the gate, so the
  re-asked `asked` state stays until the test's `runtime.recommend`.

## Scope

The one test and its wait. Nothing in `src/` or `web/`.

## Out of scope

- Changing `state.recommendations_missed` so that a notice is missed only at the end of
  the turn that got it (keeping a turn id per notice): LADO gives a notice only inside the
  lead's own turn, so the rule is right for every real path; the extra state would serve a
  test's shortcut alone (AGENTS.md, "Only what is used").
- Re-asking with a real request (a summary, through the queue): the fake supervisor would
  take it and end a turn, marking it `missing` again, the same race the other way round.
- The wait in `gated_session` for every test that uses it: the other tests either give a
  recommendation (`given`, which no turn end changes) or never look at its state, so they
  have no such race; a wait there would slow eleven tests for one.
- A rerun plugin (pytest-rerunfailures) or a longer timeout: they hide the race rather
  than close it.

## Acceptance criteria

- AC-1: The test waits for gate #1's recommendation to be `missing` and asserts that the
  supervisor has no message pending or sent before it calls `state.ask_recommendation`;
  the rest of the test is unchanged.
- AC-2: With the fix, the test passes 20 times in a row run alone
  (`uv run pytest -m ui -n0 tests/ui/test_gates.py -k disagrees`), and 5 times in a row
  with the whole `tests/ui/test_gates.py` under `-n auto`.
- AC-3: The race is shown by hand once: with the old test and a message sent to the
  supervisor right after the re-ask (a turn that ends after it), the card shows "The
  supervisor gave no recommendation" (the build report quotes the failure; the probe is
  not committed).
- AC-4: `make lint` passes; `uv run pytest -m ui tests/ui/test_gates.py` passes; CI is
  green.

## Impact

- `tests/ui/test_gates.py` only.
- No API, schema, MCP, CLI or UI change; no CHANGELOG.md line (nothing users see) and no
  version bump: a fix inside 0.37.0rc1's line.

## Decisions for the record

- Scale tweak: a test-only change of known shape; review by precision.
- Root cause is the test's notice from outside any turn racing the fake supervisor's
  turn ends; fixed in the test, not in `state.recommendations_missed` (see Out of scope).
- The wait is on gate #1's own state (`missing`), the precise sign that the supervisor's
  last queued message was handled, not on the supervisor being idle: idle can come
  between two batches while a message still waits.
- The assert that no message to the supervisor is pending or sent makes the test's
  premise explicit, so a future change that queues one more message fails loudly here
  instead of flaking.
- The wait uses `agent_helpers.wait_for` and `state.get_gate`, as the integration test
  `test_a_gate_asks_the_lead_and_its_recommendation_reaches_the_gate` does.
- Test layer: UI e2e (`make test-ui`), the test itself; no new test.
- No delta spec: no behaviour rule changes; the change is archived with `--skip-specs`.
