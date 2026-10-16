# LAD-85 closed-gate-card: review report

Pull request #84 `fix/lad-85-closed-gate-card` → `main`. Scale: tweak, reviewed for
precision; `state.py`, the migration and `tests/agent_helpers.previous_schema` were read
for breadth, as the change migrates the user's data (lado.db schema 29 → 30, with a
backfill of old gates). Head reviewed last: `76b6a93` (= the remote head).
`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/`
did not change, so live tests are not needed before the merge.

## Rounds

- **Round 1, local** (breadth over `state.py`, the migration and the server, precision
  over the UI; `origin/main...876f6e9`): F1 (blocker), F2 and F3 (minor). No external
  round requested while a blocker stood.
- **Round 2, local** (precision over the delta `876f6e9..76b6a93`: the merge of main,
  `1aa9929`, `76b6a93`): F1 and F2 resolved, F4 (found by CI) resolved, no new findings.
- **Round 1, external** (Claude Code GitHub Action over `main...76b6a93`, request
  11:24:00Z, "Claude finished" 11:24:56Z): nothing blocking, two minor (E1 refuted, E2
  declined). The external reviewer is of the same model family, so its "nothing
  blocking" weighs less.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (checks) | the pull request conflicted with `main` (CHANGELOG.md after #83), so CI never ran and `ci-ok` was not green | confirmed | blocker | fixed in `916843c` (merged origin/main, both 0.40.0 lines kept); CI run 38892903718 23/23 pass |
| F2 | 1 | local (types) | `_close_gate` was annotated `-> int \| None` but also returns `False` | confirmed | minor | fixed in `1aa9929` (`int \| bool \| None`) |
| F3 | 1 | local | the migration's backfill is a correlated subquery over `events` without an index, O(gates × events): a probe of 2000 × 204k took 20 s; the human's 63 × 2870 is instant | confirmed | minor | declined: a one-time step on small real volumes; an index for one step would be schema without use |
| F4 | 2 | CI (container amd64/arm64) | `tests/container/test_migration.py` expected the column of the former last step `resume_at_start` in the error text; the last step is now `closed_event` | confirmed | important | fixed in `76b6a93`; no other reference to the last step's column in tests, scripts or docker |
| E1 | ext 1 | external | the backfill takes the run's first event after `gate_answer`; if a close wrote no event, another one would be linked; it proposed `e.kind IN ('flow','flow_set','flow_cancel')` | refuted | — | every close path writes its event right after `_close_gate` in the same transaction (`runs.py:151/223/338/354`), the order holds since 5f0e932; the filter would not fix the hypothetical case either |
| E2 | ext 1 | external | no vitest of `GateLine` for a closed gate whose run is not loaded (`states = null`) | confirmed | minor | declined: `GateLine` passes `null` to the shared `OutcomeChip`, whose neutral branch is covered (`Chat.test.tsx:928`) |

Metrics: 2 local rounds, 1 external, 0 substitutes. Local confirmed 3 (1 blocker, 2
minor), refuted 0; CI confirmed 1 (important); external confirmed 1 (minor), refuted 1.
Findings in code changed by the developer's cleanup: 0.

## Checks

- On `876f6e9`: `make lint` green; `make test` 3369 passed; `make web` 835 vitest passed;
  `uv run pytest -m ui tests/ui/test_gates.py tests/ui/test_chat.py` 33 passed;
  `openspec validate --specs --strict` 32 passed, `closed-gate-card --strict` valid.
- On `76b6a93`: CI run 38892903718, 23/23 pass (unit 3.10/3.13, integration 6 shards, ui
  2 shards, js, container amd64/arm64, smoke 8 cells, `ci-ok`). The round 2 delta was not
  rerun locally.

## Not checked (residual risk)

- F3: on a very large lado.db the backfill may take tens of seconds, once (a backup
  precedes the migration).
- Integration, smoke and container ran in CI only; live not run (not needed).
- Keyboard activation (Enter/Space) of the folded card is checked by the UI e2e tests
  only.

Found on the way: none.
