# LAD-234 unread-message-reminder: review report

Pull request #305 `hotfix/lad-234-unread-message-reminder` → `main`. Scale: hotfix, depth
precision, widened by the reviewer to broad. Head reviewed: `dc7306e8`. An agent that ended a
clean turn without reading the text of a message it got was never told so; LADO now queues it one
reminder from `lado` naming those messages, at most once per message, with a schema migration
(39 → 40) for the mark.

## Rounds

1. Local, broad (`d4b68a82..dc7306e8`): the migration changes every existing row of `messages`
   and the hooks' shared code, so the pass went wider than the design's precision. Lenses: spec,
   tests, silent failures, comments, types and invariants, general, architecture against
   AGENTS.md. External 1, Claude Code GitHub Action (request 18:01:09Z, "Claude finished"
   18:02:12Z). It read `hooks.py` and `state.py` as diff hunks with context ("Risky code not fully
   read"), not `tests/test_state.py`, `tests/test_runtime.py`, the docs or the openspec files;
   those were read locally in full.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| E1 | — | external: an agent that got a message's line mid-turn in a tool result and did not read it gets an "extra" reminder | refuted: the spec's first requirement asks for exactly this; "if it asks nothing of you, do nothing" bounds the cost |
| E2 | — | external: no test of a batch handed over in the hook's output | refuted: covered by unit tests in `tests/test_runtime.py` (`test_a_text_handed_over_at_the_turn_end_is_checked_at_the_next_one`, `test_texts_left_unread_get_one_reminder_naming_each`) |
| E3 | minor | external, refined locally: the integration test `test_a_reminder_ignored_gets_no_second_one` may check its count before the last turn ends, as the fake agent logs its input before the `prompt_submit` hook | declined: the test gets weaker, never red; the rule is checked deterministically by the unit test `test_a_text_is_reminded_once_also_when_the_reminder_is_ignored` |
| E4 | — | external: the test filter `UNREAD_REMINDER.partition("{")[0]` depends on the template's first placeholder | refuted as a defect: style; the filter is right and proven by `test_agents.py` |

The local pass found no defect.

## Metrics

Rounds: 1 local, 1 external, 0 stand-ins. Findings: local 0 confirmed / 0 refuted; external 1
confirmed (minor, declined), 3 refuted; findings in code changed by the developer's cleanup: 0.

## Checks

- `make lint`: green.
- `tests/test_state.py` and `tests/test_runtime.py` (`-n auto`): 917 passed.
- `-m integration -n auto` on `test_unread_reminder.py`, `test_agents.py`,
  `test_human_messages.py`, `test_flow_runs.py`: 63 passed.
- `openspec validate unread-message-reminder --strict`: valid; `openspec validate --specs
  --strict`: 83 of 83; trial archive then `--specs --strict`: 84 of 84.
- CI on `dc7306e8`: 27 of 27 SUCCESS, smoke and container included; no reruns.
- Full `make test` by the developer: 6135 passed, 1 failed (`test_temp_dirs[shell]`, red on the
  base too, in BACKLOG.md); CI's unit cells green.

## Residual risk

- Live tests were not run and not changed; the change touches `hooks.py` and `state.py`, so the
  human may run `live.yml`.
- Full `make test` and `make test-integration` were not run by the reviewer; green CI covers them.
- Behaviour on a weak model was not measured: the reminder fires only on a miss, and the live
  cells run on a strong model (LAD-273).

Found on the way: none.
