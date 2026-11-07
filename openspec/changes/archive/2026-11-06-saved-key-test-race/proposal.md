Task: LAD-206

## Why

Symptom: `tests/test_server_providers.py::test_a_saved_key_replaces_lados_token_and_beats_the_outside_folders`
failed once in CI with `KeyError: 'ANTHROPIC_API_KEY'` at line 219 (PR #218, head `3b2b1f34`,
run 42095153328, attempt 1, `unit (3.10)`; 1 failed, 4818 passed). That pull request changed
neither `src/` nor the test, and the rerun passed.

Cause: the test races the background check that its own first save started; the product
is right. The test saves a token, then a key. Each save starts `provider_check.start()`. The
first save's check reads the environment with the token and may run `claude`'s status command
only after the second save has read its row. The test then takes the *last* `claude` call of
`cli_logins.calls` and gets the older check's environment, which has the token and no key.

Reproduced 2026-11-06 with a throwaway test that holds the check's `claude` call until the
second save has answered. The `claude` calls, in order, held these login variables:

    [TOKEN]   the first save's own read
    [KEY]     the second save's own read
    [TOKEN]   the first check, late: the test's [-1], so KeyError
    [KEY]     the check that runs after it

In the same run the second save's answer and the row kept after both checks said "Pay per
use (API key)", "LADO's secret". So the late read is thrown away, as `provider_check._one`
intends: a row `put` after a check's snapshot of `_puts` wins over that check's read, and a
check asked for during another runs once more after it. A status command with the older
environment only reads, so no user sees it, and no agent gets that environment.
`test_provider_check.py::test_a_row_put_during_a_check_is_not_replaced_by_its_older_read`
already holds this rule.

Options weighed:

- A (taken): this test starts no check, with `provider_check.start` replaced, as
  `test_a_saved_token_starts_a_check` does. No thread is left, so the order is fixed, and
  the last call is the save's own read. Long-term cost: none; the test no longer covers the
  check, which `test_a_saved_token_is_lados_secret_and_never_given_back` and
  `tests/test_provider_check.py` do.
- B: `any(...)` over the `claude` calls, as the neighbouring token test does. One line, but
  the threads stay, and each later assertion on this test's calls can race again.
- C: wait for the first check to end before the second save. It keeps the real check, for a
  polling helper and a wait in a test that is not about the check; the test then depends on
  how many checks a save starts.
- D: make the product cancel or skip a check's read that an action outdated. It changes
  working code in the login path to spare a test, and no user sees a difference.

## What Changes

- The test replaces `provider_check.start` before its first save, and reads the save's
  environment from `cli_logins.calls[-1]`, after asserting that only `claude` was called.
  Its comment about the other CLIs goes.

## Scope

- That one test in `tests/test_server_providers.py`.

## Out of scope

- `src/lado/server/provider_check.py` and `app.py`: the behaviour is right (Why).
- A new test of the late read: `test_a_row_put_during_a_check_is_not_replaced_by_its_older_read`
  holds it.
- The other flakes of the review report of 2026-11-05 (`src/LoginSheet.test.tsx:238`,
  `test_a_project_secret_is_found_nowhere_else`): other causes, not this task.

## Impact

- Tests only. No behaviour rule changes, so there is no delta; archive with `--skip-specs`.
- Version: nothing users see, so no CHANGELOG.md line and no version bump of its own (the
  patch rule at most).
- Neutral core, one source of truth, no silent drops: untouched, as `src/` does not change.
