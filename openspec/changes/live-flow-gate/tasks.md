## 1. The live flow test

- [ ] 1.1 `tests/live/test_live.py`, `TINY_FLOW`: after `step` (outcome `done: ok`) an
  approval gate `ok` (`ask:` a short question; outcomes `approved: after`,
  `rejected: end`), then a work state `after` (`agent: worker`) whose `do` tells the
  worker to write into `gate.txt` exactly the one word the human's comment at the gate
  names (from the note of the previous step), commit it, call flow_advance with `done`
  and do nothing else; `outcomes: {done: end}`. The module's docstring names the gate.
  Check: the kit installs in the test (`flows.py`'s validator) (AC-1).
- [ ] 1.2 `test_a_flow_run_moves_on_when_its_worker_reports`: wait (with `answering`, as
  today) until the run is `waiting` at `ok` with an open gate; answer it with
  `runs.answer_text(SESSION, run.name, "approve", "The word is <WORD>.")`, `<WORD>` a
  constant not written in the flow (e.g. `MARIGOLD`); then wait for the run to end
  (timeout as today's 240 s for the first step, a second 240 s after the answer). Check
  the flow events are exactly `[("w1", "step -done-> ok"), ("human", "ok -approved->
  after"), ("w1", "after -done-> end")]`, the message `flow <run>: step after` from LADO
  to `w1` reached `read`, `gate.txt` on `run.branch` is `<WORD>` and `flow.txt` is `OK`;
  the rest of the test stays (AC-2..AC-5). The docstring says the human's answer at the
  gate reaches the real CLI as the next step. If the passive supervisor's turn for the
  lead's recommendation is still going, `supervisor_quiet()` before the merge covers it
  (no wait for the recommendation itself).
  Check: `uv run pytest -m live --collect-only tests/live/test_live.py` collects it;
  `make lint`; `make test` green (the unit tests that read `tests/live/`). Written, not
  run locally (no key): say so in the build report.

## 2. Documents

- [ ] 2.1 `docs/release.md`, 4.3's paragraph "Flows and gates are the tests'": the live
  tests run the flow `tiny` with a gate, so a gate's answer reaching a real CLI is checked
  in `live.yml` on each RC. Check: read it.

## 3. The live run

- [ ] 3.1 After the merge into main (the key reaches only main): `gh workflow run
  live.yml` on main, all four cells green within 25 minutes, the flow test's time per
  provider (its `flow: Ns` line) noted in the closing report (AC-6). Before the merge the
  pull request's own CI must be green as usual (`ci-ok`; it does not run live tests).
