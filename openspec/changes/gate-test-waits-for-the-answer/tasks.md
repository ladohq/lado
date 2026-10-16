## 1. The test waits for the answer

- [x] 1.1 `tests/ui/test_gates.py`, `test_the_human_answers_a_gate_on_its_tab`: the click
  on Reject runs inside `with page.expect_response(<the POST to
  /api/sessions/<session>/gates/1/answer>) as answered:`, and `answered.value.ok` is
  asserted before the checks that read lado.db; no other line of the test changes.
  Check: `uv run pytest -m ui -n0 "tests/ui/test_gates.py::test_the_human_answers_a_gate_on_its_tab"`.
- [x] 1.2 Deterministic proof (AC-1): with a local, uncommitted `time.sleep(1)` at the
  start of `runs._deliver_step`, the test as on `main` fails on `Note from the previous
  step` and the test after 1.1 passes; both outputs in the build report; the probe is
  removed (`git status` clean but the test).
- [x] 1.3 Repetition (AC-2): 30 runs of the test without the probe, two tests at a time
  as CI's UI shards run, e.g. 30 rounds of `uv run pytest -m ui -n 2
  tests/ui/test_gates.py`, each with its exit status read (no pipe); the count in the
  build report.

## 2. Checks

- [x] 2.1 `make lint` green; `uv run pytest -m ui tests/ui/test_gates.py` green.
- [ ] 2.2 The pull request's CI (`ci-ok`) green.
