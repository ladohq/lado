# LAD-260 live-flow-gate: review report

Pull request #309 `fix/lad-260-live-gate` → `main`. Scale: tweak, depth precision.
Head reviewed: `d1089951`. The live flow test's flow `tiny` now has an approval gate `ok`
between two steps of the worker; the test answers it as the human through
`lado.runs.answer_text` with a comment naming a word (`MARIGOLD`), and checks that the real
agent got the step `after` as a message from LADO, read it and wrote that word into
`gate.txt` on the run's branch. `docs/release.md` 4.3 says the live tests take a gate's
answer to a real CLI. No product code changed.

## Rounds

1. Local, precision, over `origin/main...d1089951`: the diff checked against the code
   (`runs.answer_text` → `find_gate`, `APPROVE`, `state.flow_detail`, `_answer_note` and
   `step_text`, `_deliver_step`; the lead's recommendation and the passive supervisor's
   "human answered" message covered by `supervisor_quiet()`); `TINY_FLOW` parses with
   `flows.parse`. Nothing found.
2. External 1, Claude Code GitHub Action (request 20:06:17Z, "Claude finished" 20:06:35Z).
   It read `tests/live/test_live.py` and `docs/release.md`; not the openspec files
   (checked locally).

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| E1 | — | external: checking that `step after` reached `read` after the run's end may be flaky if the hook confirms late | refuted: `read` is set by the `read_messages` call itself (`state.read_messages`), and the step's text and note come only in the body, so the worker cannot do the step without it |
| E2 | minor | external: the gate named `ok` reads like the file's `OK`; a name like `approve_step` would be clearer | declined: naming taste, the name was set by the approved design |
| E3 | — | external: the live test never ran; a break shows only in `live.yml` after the merge | refuted as a defect: by design (AC-6, task 3.1), the `live` environment's key reaches only main and `v*` tags |

Found on the way: nothing.

## Checks

- `make lint` green; `uv run pytest -m live --collect-only tests/live/test_live.py`: 16 tests.
- `openspec validate live-flow-gate --strict` valid; `openspec validate --specs --strict`: 84 passed.
- CI of the pull request: 27 of 27, `ci-ok` green. The developer's `make test`: 6153 passed.

## Not checked (residual risk)

- The live test itself has not run with any real CLI: written, not run. Task 3.1 runs
  `live.yml` on main right after the merge, as the human asked at `merge_ok`; a red cell
  means a fix on main before RC 0.47.0.
- A model that does not call `read_messages` and so does not do the step is what the test
  is meant to catch, not a defect of the test.
