# LAD-131 late-agent-window: review report

Pull request #147 `hotfix/lad-131-late-agent-window` → `main`. Scale: hotfix, designed
for precision but reviewed by breadth in round 1: the diff migrates lado.db (schema
34 → 35, existing `agents` rows) and changes the rule that declares an agent dead and
drops its task. Head reviewed last: `62cbb3a` (= the remote head). `src/lado/runtime.py`
changed (`spawn_worker`, `start_session`, `check_windows`); `providers/`, `hooks.py`,
`mcp_server.py`, `agent_env.py` and `tests/live/` did not, so the reviewer saw no need
for live tests and left it to the human.

## Rounds

- **Round 1, local** (breadth, `d11c543..2fb5496`): lenses spec, tests, silent
  failures, comments, types, general and the architecture against AGENTS.md. Every
  requirement and scenario of `agent-window-check` has code and a test; `tasks.md` 8 of
  8. Only `tmux.new_window` and `tmux.new_session` make an agent's window, and each is
  followed by `window_opened` inside the `try`. The migration follows step 32's pattern
  and `schema_before(35)` undoes it. Red without the fix shown by the reviewer: in a
  copy of the tree with the old `check_windows`, the new integration test fails 3 of 3
  (`w1: ended its window closed without a session-end hook`).
- **Round 1, external** (Claude Code GitHub Action; request comment 6358245012 at
  05:37:49Z, "Claude finished" at 05:38:54Z): no new defects; F1 and F2 confirmed as
  minor, F3 raised as a trade-off. Same model family, so its "nothing more" weighs less.
- **Gate `merge_ok`**: the human sent the change back to fix F1 and F2.
- **Round 2, local** (precision, `2fb5496..62cbb3a`): comments and a test helper only, no
  product code changed. `past_spawn_deadline(-2)` with `created_at` rounded down to the
  second still gives an age under the deadline: the test is not fragile. No new findings.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (comments) | the comment on `loop.INTERVAL` still said the interval is how long `check_windows` spares a new agent's window | confirmed | minor | fixed in `62cbb3a` (declined first; the human asked for the fix at `merge_ok`) |
| F2 | 1 | local (tests, comments) | the docstring of `later()` was stale, and the deadline tests took 60 s from `later()` instead of `runtime.SPAWN_DEADLINE` | confirmed | minor | fixed in `62cbb3a` via `past_spawn_deadline()`; checked with a temporary `SPAWN_DEADLINE = 120` (9 passed) |
| F3 | 1 | external | a slow but live spawn longer than 60 s is ended with "its start ended before its window opened" | refuted as a defect: the worst path between the row and the window is about 20 s (`tmux.TIMEOUT` 10 s plus one retry); the rest is the design's stated risk with its own loud reason | — | dropped |

Found on the way: nothing.

Metrics: 2 local rounds, 1 external, 0 substitutes. Local confirmed 2 (F1, F2), refuted
0; external confirmed 0 new, refuted 1 (F3). Findings in code changed by the developer's
cleanup: 0.

## Checks

- Round 1 on `2fb5496`: `make lint` exit 0; `make test` 3959 passed, 2 skipped;
  `uv run pytest -m integration -n auto tests/integration/test_agent_liveness.py` 11
  passed; `openspec validate late-agent-window --strict` valid; `openspec validate
  --specs --strict` 45 passed.
- Round 2 on `62cbb3a`: `make lint` exit 0; `tests/test_liveness.py` and
  `tests/test_state.py` 207 passed; the integration file 11 passed. The developer's
  `make test` on `62cbb3a`: 3959 passed, 2 skipped.
- The flaky test 40 times, 16 at once: 40 of 40 (the developer's build report).
- CI on `62cbb3a`: 23 of 23 success, `ci-ok` green.
- At archive: `openspec validate --specs --strict` 46 of 46.

## Not checked

- The milliseconds between `tmux.new_window` and the mark's write: a CLI that dies
  exactly there is ended after 60 s with "its start ended…" rather than within seconds
  with "its window closed…"; it is still stopped with its own reason.
- The whole integration layer and the 40-run loop were not rerun by the reviewer; CI and
  the build report cover them.
