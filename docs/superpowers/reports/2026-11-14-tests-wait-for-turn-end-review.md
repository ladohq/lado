# LAD-284 tests-wait-for-turn-end: review report

Pull request #307 `hotfix/lad-284-tests-wait-for-turn-end` → `main`. Scale: hotfix, depth
precision. Head reviewed: `3ca984f1`. Two integration tests timed out once under load and passed
on rerun. Both were races in the tests, not slow timeouts: a test sent the human's next command
while the agent was still finishing its turn (or a reply reminder was still ahead of it). The tests
now wait until the agent is settled (idle, with no message of its own pending or sent) through a
shared helper in `tests/agent_helpers.py`; no timeout was raised and no retry added.

## Rounds

1. Local, precision (`d4b68a82..3ca984f1`), checked against `hooks.py`, `runtime.hand_over` and
   the message states of `state.py`; and external 1, Claude Code GitHub Action (request 18:33Z,
   "Claude finished" 18:34:56Z). The external round read every risky file of the diff and
   `hooks.py`, not the openspec files (no spec delta).

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | local and external: a 135-character line in `docs/testing.md:46` | declined: the file already has 7 other lines over 100 characters |
| F2 | minor | external: `settled` is a snapshot, not a latch | declined: both callers send the agent nothing else at those moments; a latch would be API no one needs |
| F3 | — | external: a delivered message with its body unread counts as taken | refuted: design decision D1 (AC-3), documented in the helper's docstring; the fake agent reads bodies only on command |
| F4 | minor | external: mixed import style in `test_flow_runs.py` | declined: style only |

Checked by reading: the reply reminder is queued before the agent goes idle, and going idle and
handing over the queue are one transaction, so there is no moment of "idle with nothing pending"
while the reminder is still ahead; on prompt submit the status turns busy before the delivery is
confirmed. The remaining waits for idle follow messages from `lado`, not the human, and have no
reminder behind them.

## Metrics

Rounds: 1 local, 1 external, 0 stand-ins. Findings: local 1 confirmed (F1) / 0 refuted; external
2 confirmed (F2, F4), 1 refuted (F3); findings in code changed by the developer's cleanup: 0.

## Checks

- `make lint`: exit 0.
- `uv run pytest -n0 tests/test_agent_helpers.py`: 16 passed.
- `uv run pytest -m integration -n auto tests/integration/test_session_start.py
  tests/integration/test_flow_runs.py`: 18 passed.
- `openspec validate tests-wait-for-turn-end --strict`: valid; trial archive with `--skip-specs`
  and `openspec validate --specs --strict`: 83 passed.
- CI on `3ca984f1`: `ci-ok` and all 26 checks pass (unit, integration 6 shards, ui 4, web,
  container 4, smoke 8).

## Residual risk

- AC-4 (forcing both races by a temporary sleep in `src/`) was done by the developer only; the
  reviewer confirmed the order of events by reading the code.
- `make test` was not run locally by the reviewer; CI's unit cells are green.
- The other integration tests of the same shape (about 64 human commands in 20 files) were left
  out by design: a P2 entry in BACKLOG.md.
- No change to `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
  `tests/live/`: no live tests needed.

Found on the way: none.
