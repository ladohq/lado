# LAD-38 ui-test-recommendation-race: review report

Pull request #16 `fix/lad-38-recommendation-test-race` → `main`. Scale: tweak, review
depth: precision. Head reviewed last: `edb6b23`; the archive commit follows it. Only
`tests/ui/test_gates.py` (`test_a_gate_with_a_recommendation_that_disagrees`) and the
openspec change; nothing in `src/` or `web/`, no provider code, no schema migration.

## Rounds

- **Round 1** (`66aedfe..edb6b23`): local precision pass. The wait was checked against
  `state.recommendations_missed` / `_missed` (`src/lado/state.py`): `missing` is set only
  at the end of a lead's turn, for a request `delivered`/`read` or a notice, so gate #1's
  `missing` means the turn that got the gate's own request ended; with no message to the
  supervisor pending or sent, no turn of it ends before the test's `runtime.recommend`.
  No finding. Then external round 1 by the Claude Code Action (request 10:24:55 UTC,
  "Claude finished" 10:25:51 UTC): the fix is correct, no blocker, two optional nits.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | external (Action) | `queued` collects summaries while only its emptiness is checked | refuted | — | on purpose: a failure shows the summaries in pytest's diff |
| F2 | 1 | external (Action) | `get_gate(1).recommendation_state` raises `AttributeError` when the gate is missing | refuted | — | gate #1 exists: its card with Approve is seen just before; a failure would be loud |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 0 | 0 | — |
| external, Claude Code Action | 0 | 2 (F1, F2) | — |

## Found on the way

None.

## Checks

- `make lint` clean; `uv run pytest -m ui -n0 tests/ui/test_gates.py -k disagrees` 3 of 3
  runs passed; `uv run pytest -m ui -n auto tests/ui/test_gates.py` 4 passed;
  `openspec validate ui-test-recommendation-race --strict` valid.
- CI of PR #16 on `edb6b23` green: check (3.10, 3.13), js, ui, smoke ubuntu/macos ×
  claude/codex/kilo/opencode.
- Not run locally: `make test` and the integration tests (only `tests/ui/` changed; CI ran
  them). Live tests not needed: no core or provider code changed.

## Residual risk

- That the flake is gone rests on the mechanism and the developer's probe (AC-3), not on
  many CI runs. Should it fail again, the assert names the extra queued message or
  `wait_for` times out with its diagnostics.

## Result

Converged after round 1 (1 of 1 external rounds).
