Task: LAD-191

## Why

Symptom: `tests/test_tmux.py::test_popup_opens_on_the_clients_attached_to_the_session` failed
once in CI with `AssertionError: assert '' == 'approve\n'` at `tests/test_tmux.py:156` (PR #211,
run 41818983454, attempt 1, `unit (3.13)`, commit a863eac2). That pull request did not touch
the test or `src/lado/tmux.py`, and the rerun passed.

Cause: the test races the shell in its own popup; the product is right. The test waits for
the answer file to exist and reads it at once, but `echo "$a" > "{out}"` creates the file
empty first and writes to it after. A poll that lands between the two reads `''`. The answer
did reach the popup, so `tmux.popup` and the popup itself play no part. The wait for the
client (lines 139-141), suspected at first, had already passed: the test failed on its last
step but one.

Reproduced 2026-11-06:

    a copy of the test, 0.3 s between creating the file and writing to it, no fix
                                                 assert '' == 'approve\n' at line 156, every run
    the same copy with the fix                   1 passed
    the same `sh` redirect, a tight poll         15 empty reads of 300
    the real test, unchanged, 8 at a time        60 of 60 passed

The last line shows how narrow the window is: a run of green tests proves little here, which
is why the widened window is the proof of the fix.

Options weighed:

- A (taken): the test's loop waits for the file to have content, not only to exist. One
  condition on one line, and `echo` writes the line in a single write, so content means the
  whole answer. Long-term cost: none.
- B: the popup's script writes to a temporary file and renames it. Closes the race too, but
  makes the script longer for the same result.
- C: a longer sleep before the read. Makes the failure rarer and keeps the race.

## What Changes

- The loop before `assert out.read_text() == "approve\n"` in
  `test_popup_opens_on_the_clients_attached_to_the_session` runs until the file exists and
  has content.

## Scope

- That one condition in `tests/test_tmux.py`.

## Out of scope

- `src/lado/tmux.py`: the behaviour is right (Why).
- The wait for the client at lines 139-141: it ends silently after 5 s, but the next line,
  `assert tmux.popup(...) == 1`, then fails at once and plainly, and this failure did not
  come from there.
- 20 runs in CI, which the task asked for: CI runs the test once per push, so it would take
  a temporary workflow or 20 reruns, and 60 green runs without the fix show such a count
  proves little. The human agreed on 2026-11-06 to replace it with 20 local runs, the widened
  window and the pull request's green CI.

## Impact

- Tests only. No behaviour rule changes, so there is no delta; archive with `--skip-specs`.
- Version: nothing users see, so no CHANGELOG.md line and no version bump of its own (the
  patch rule at most).
- Neutral core, one source of truth, no silent drops: untouched, as `src/` does not change.
