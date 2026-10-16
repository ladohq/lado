# LAD-72 gate-test-waits-for-the-answer: review report

Pull request #81 `hotfix/lad-72-gate-test-race` → `main`. Scale: hotfix, reviewed for
precision (not widened: only one UI test and the openspec change changed, no logic, user
data or code rewritten in earlier rounds). Head reviewed last: `12f8d57` (= the remote
head). `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and
`tests/live/` did not change, so live tests are not needed before the merge.

## Rounds

- **Round 1, local** (precision over `origin/main..12f8d57`): the diff against
  proposal.md and tasks.md, and the mechanism in the code: `POST
  /api/sessions/{name}/gates/{gate}/answer` (`app.py`) runs `runs.answer_text` →
  `answer` → `_commit` → `update_run`, then `_arrived`, in the request, so its response
  comes only after the step message is queued, and `page.expect_response` closes the
  race. No check of the test removed or loosened (AC-3). No new findings.
- **Round 1, external** (Claude Code GitHub Action over `main..12f8d57`, request
  07:41:52Z, "Claude finished" after it): no blocking findings, two notes (F1, F2), both
  refuted. The external reviewer is of the same model family, so its "nothing blocking"
  weighs less.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | ext 1 | external | other UI tests that read `state.*` right after an answer's click may share the race | refuted | — | dropped: no test of `tests/ui/` reads a second write of the same action right after the page showed the first (`test_flows_tab.py`'s `status == ENDED` is in `update_run`'s transaction; `test_gates.py` and `test_chat.py` wait with `wait_for` or read a single insert the UI showed) |
| F2 | ext 1 | external | the product has a short gap where the feed shows the closed gate before the step is queued | refuted (no defect) | — | dropped: the two writes are by design (`runs._commit`: `update_run`, then `_arrived`), no user sees the gap, and the design records the decision (Out of scope) |

Metrics: 1 local round, 1 external, 0 substitutes. Local confirmed 0, refuted 0;
external confirmed 0, refuted 2. Findings in code changed by the developer's cleanup: 0.

## Checks

- On `12f8d57`: `make lint` green; `uv run pytest -m ui -n 2 tests/ui/test_gates.py`, 10
  passed; `openspec validate gate-test-waits-for-the-answer --strict` valid.
- CI on `12f8d57` (run 38868369125): all jobs green; the smoke skipped by the skip list
  (only `tests/ui/` and `openspec/` changed). The run on `731f17b` (38867804046) green
  too.
- The developer (build report): with a local probe (`time.sleep(1)` at the start of
  `runs._deliver_step`) the test as on `main` fails on the step's text and the fixed test
  passes (AC-1); 30 of 30 runs without the probe, two tests at a time (AC-2).

## Residual risk (not checked)

- The reviewer did not repeat the AC-1 probe or the 30 runs (a read-only role): it relies
  on the build report and on the mechanism read in the code.
- `make test` and the integration tests were not run locally: no code under them
  changed, and CI ran them.
