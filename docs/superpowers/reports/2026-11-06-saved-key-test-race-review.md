# LAD-206 saved-key-test-race: review report

Pull request #231 `fix/lad-206-saved-key-test-race` → `main`. Scale: tweak, review depth:
precision. Head reviewed: `7aba61e5`. The flaky unit test
`test_a_saved_key_replaces_lados_token_and_beats_the_outside_folders` raced the background
check of its own first save; the product is right. The test now starts no check. One test
changed, nothing in `src/`, no delta, no CHANGELOG.md line.

## Rounds

1. Local, precision, `59899a57..7aba61e5`: the diff and the change read by hand, the build
   report last. No finding. No breadth pass: no business logic, user data or `src/` touched.
2. External 1, Claude Code GitHub Action: no defect, two remarks without action (E1, E2). It read
   the test, `tasks.md` and the relevant parts of `app.py` and `provider_check.py`; not
   `.openspec.yaml` or `proposal.md`, which hold no risky code. It ran no tests.

External rounds used: 1 of 1. Stand-ins: 0.

## The human's decisions

- **Gate `merge_ok`, approved** with no comment.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| E1 | none | `cli_logins.calls[-1]` relies on the second save's read coming last | dropped, no defect: `fresh_row` reads synchronously, `start` is replaced, and the assertion that only `claude` was called catches another CLI |
| E2 | none | if `fresh_row` ever reads more than `claude`, the test fails on a bare set comparison | dropped, no defect: that is the check doing its job |

## Acceptance criteria

| Criterion | Result | How checked |
|---|---|---|
| AC-1: no background checks | met | the replacement stands before the first save; the route calls `provider_check.start()` through the module; with a thread held at the PR's head no check began |
| AC-2: the environment's check is as strict | met | the assertion did not change; with `agent_env.merge` mutated in a copy the test fails with `AssertionError` at line 220 |
| AC-3: 20 runs, lint, tests | met | see Checks |
| AC-4: `src/` unchanged | met | `git diff --stat origin/main...HEAD`: the test and the change's folder alone |

The cause was checked apart from the fix: a copy of `origin/main` with a plugin outside the
repository forcing CI's order of calls fails with `KeyError: 'ANTHROPIC_API_KEY'` at
`tests/test_server_providers.py:219`, as CI did; a copy of the PR's head with the same plugin
passes. `provider_check._one` throws the late read away when `_puts` changed, and `_again` runs
one more check. No other test takes the last of `cli_logins.calls`.

## Checks

At `7aba61e5`:

| Check | Result |
|---|---|
| `make lint` | exit 0 |
| `make test` | exit 0: 4823 passed, 7 skipped |
| The test alone, `-n0`, 20 times | 20 of 20 |
| `openspec validate saved-key-test-race --strict` | valid |
| `openspec validate --specs --strict` | 62 passed, 0 failed |
| Trial archive in a copy with `--skip-specs`, then the specs | both exit 0 |
| CI, run 42275436443 | 23 checks passed, `ci-ok` green, smoke included |

## Metrics

Rounds: local 1, external 1, stand-ins 0. Findings: local 0 confirmed, 0 refuted; external 0
confirmed, 2 refuted. Findings in code a cleanup changed: 0 (no cleanup).

## What was not checked

- The integration, UI and smoke tests were not run locally: no file of those layers changed, and
  CI ran them.
- `make test-live` was not run: it runs at a release. No file of `providers/`, `hooks.py`,
  `mcp_server.py`, `runtime.py`, `agent_env.py` or `tests/live/` changed.
- CI's failure happened once. The match rests on the forced order of calls, not on a repeat of
  that run.

Remaining risk: this test no longer covers the background check, on purpose;
`test_a_saved_token_is_lados_secret_and_never_given_back` and `tests/test_provider_check.py` do.

## Found on the way

Nothing.
