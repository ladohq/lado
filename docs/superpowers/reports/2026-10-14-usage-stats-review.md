# LAD-34 usage-stats: review report

Pull request #35 `feature/lad-34-usage-stats` → `main`. Scale: full, minor (0.38.0: a new
CLI command, `lado stats`, and schema 27, the `usage` table). Review depth: breadth first.
Head reviewed last: `b1ea42f` (= the remote head); the archive commit follows it.
`src/lado/runtime.py` changed (`_add_agent`: the role's kit in the `spawned` event) and
`src/lado/runs.py` (the gate-closing constants); `providers/`, `hooks.py`,
`mcp_server.py`, `agent_env.py` and `tests/live/` are untouched.

## Rounds

- **Round 1** (local, breadth, `origin/main...854ab99`): the lenses spec, tests, silent
  failures, comments, types, general, and the architecture against AGENTS.md. F1
  (important) and F2 (minor) found.
- **Round 2** (local, precision, `854ab99..b1ea42f`): F1 and F2 fixed; a grep for other
  writers of `cancelled` and `overridden` found only `runs.cancel` and `runs.force`, now
  through the constants. F3 (minor) found and declined.
- **External round 1** (Claude Code Action, `@claude review`, `origin/main..b1ea42f`):
  request at 08:15:47Z, "Claude finished" at 08:17:09Z (comment 6163991470). No blocker;
  four remarks, all refuted (E1-E4), the answer posted on the pull request (comment
  6164023676). 1 of 2 external rounds used.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | a gate closed by no answer of the human (`cancelled` by a run's cancel, `overridden` by `lado flow-set`) that had the lead's recommendation was counted with `agrees = 0`, as a disagreement with the lead | confirmed | important | fixed in `b1ea42f`: `agrees` NULL for `state.GATE_UNANSWERED` in the trigger and the backfill; tests `test_usage.py::test_a_gate_closed_by_no_answer_of_the_human_is_no_agreement`, `::test_the_migration_counts_no_agreement_for_a_gate_closed_by_no_answer`, `test_stats.py::test_the_agreement_counts_only_the_closes_with_a_recommended_choice`; a scenario added to the delta |
| F2 | 1 | local | the agreement line printed `12  of 14` (two spaces) instead of `12 of 14` (D7, AC-5) | confirmed | minor | fixed in `b1ea42f`, `test_stats.py` |
| F3 | 2 | local | a choice gate's outcome named `cancelled` or `overridden`, answered by the human, would be read as a close by no answer | confirmed | minor | declined: `gates.answer` already uses these words for LADO's own closes, as the UI, `lado answer` and the event read them; no kit names an outcome so |
| E1 | ext 1 | external | `message_failed` counts each failure live but once per message in the backfill | refuted | — | by design: design.md D2; the backfill counts what the rows keep, as the spec says |
| E2 | ext 1 | external | a dropped message's backfill time is its creation, not its drop | refuted | — | as the spec's migration requirement and D4 say |
| E3 | ext 1 | external | parsing `spawned_detail` and `error_line` in SQL may drift from Python | refuted | — | `test_usage.py::test_the_trigger_reads_the_spawned_detail_as_python_does` (both forms) and `::test_the_trigger_reads_an_errors_kind_as_error_line_writes_it` |
| E4 | ext 1 | external | a refactor could turn `--days 0` into 30 | refuted | — | `test_stats.py::test_bad_options_exit_2` keeps exit 2 for `--days 0` |

| Source | Confirmed | Refuted |
|---|---|---|
| local | 3 (F1, F2, F3) | 0 |
| external, Claude Code Action | 0 | 4 (E1-E4) |

## Checks

- Reviewer on `b1ea42f`: `make lint` clean; `make test` 2913 passed;
  `uv run pytest -m integration -n auto tests/integration/test_usage_stats.py
  tests/integration/test_flow_runs.py` 14 passed (round 1: `test_agents.py` with
  `test_usage_stats.py` 32 passed); `openspec validate usage-stats --strict` valid,
  `openspec validate --specs --strict` 17 passed.
- CI run 38533644294 on `b1ea42f` green: check (3.10, 3.13), ui, js, smoke × 8.
- At archive: the new capability's Purpose written in `openspec/specs/usage-stats/spec.md`
  (the archive leaves a placeholder that strict validation refuses); `openspec validate
  --specs --strict` 18 passed.

## Found on the way

None.

## Not checked

- `make check` as a whole locally: the green CI covers it.
- The live tests: they run at a release; `runtime.py` changed only in the `spawned`
  event's detail, and `runs.py` in the gate-closing constants.
- The external reviewer is the same model family as the kit's agents: its "nothing found"
  weighs accordingly.
