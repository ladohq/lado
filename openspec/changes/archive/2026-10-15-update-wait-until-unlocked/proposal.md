Task: LAD-57

## Why

`tests/integration/test_update_process.py::test_the_ui_update_rolls_back_when_the_new_version_is_wrong`
failed in CI on `assert info["running"] is False` (run 38596138639, Python 3.10) and
passed when rerun.

Root cause, confirmed in the code: `self_update.run` writes an update's final result
(`ok`, `rolled_back`, `failed`, ...) through `_Update.end` inside `with lock:`, as its
last step, after the UI server is up again; `update.lock` is released a few milliseconds
later. `GET /api/update` derives `running` (and `can_update` / `why_not` through
`self_update.refusal`) from that lock. The test's `update_from_the_ui` waits for a
server started after the one before and a result of its id that is not `running`, but
not for the lock to go, so a poll in that window sees `running: true`.

It is a defect users can meet too. The page's wait (U2, `finished()` in
`web/src/SystemPanel.tsx`) ends by the same rule and keeps the `UpdateInfo` of the poll
that ended it. A poll in that window leaves `can_update: false` and "an update is
running, pid N." in the System panel, without the Update… button, until the page is
reloaded or "Check now" asks again: the page asks `/api/update` again only when the feed
opens, and the feed reopened before, when the server came back. After a rollback, when
the newer version is still out and retrying is the likely next step, the button is
missing.

Writing the result after the lock is released was rejected: in that gap a second update
could take the lock and write its `running` result, which ours would then overwrite.

## What Changes

- The UI's update wait ends only when, besides the result of its id that is not
  `running` and the server started after the one before, `/api/update` answers
  `running: false`. At most one more poll (`POLL_MS`, 2 s); the update that ended before
  it started (a `failed` result with no log, on the same server) ends the wait by the
  same added condition.
- `tests/integration/test_update_process.py`'s `update_from_the_ui` waits by that same
  rule, so both UI update tests read an `UpdateInfo` taken after the lock was released.
- `docs/design/ui.md`, The wait (U2): the end condition names `running` false.
- CHANGELOG.md: one line under `0.39.0 (unreleased)`.

## Scope

The end condition of the UI's update wait, in the page and in the integration test that
copies it, with a unit test of the condition and a repeated run of the flaky test.

## Out of scope

- **Writing the result after the lock is released** (`self_update.run`): opens a race in
  which a second update's `running` result is overwritten (Why).
- **Deriving `running` in the API from the lock and the result together**: a second
  source of truth, and wrong at an update's start, when the lock is held before the
  `running` result is written.
- **The page asking `/api/update` again on its own after the wait** (e.g. on opening the
  System panel): with the fixed end condition the kept answer is already fresh; a
  refresh rule more is not needed (AGENTS.md, "Only what is used").
- **The CLI** (`lado update`): it runs the update in its own process and reads no lock
  state afterwards.

## Acceptance criteria

- AC-1: `finished()` returns false for a result of the waited id that is no longer
  `running`, on a server started after the one before, while `UpdateInfo.running` is
  true, and true once it is false; also for the not-started case (vitest,
  `web/src/SystemPanel.test.tsx`).
- AC-2: `update_from_the_ui` waits for `running: false` too; both UI update tests in
  `tests/integration/test_update_process.py` keep their assertions,
  `assert info["running"] is False` included.
- AC-3: Before the fix, the failure is reproduced once by hand with a delay injected in
  `self_update.run` between the result's write and the lock's release (not committed);
  the build report quotes it. With the fix and the same delay, the test passes.
- AC-4: Without the delay, `test_the_ui_update_rolls_back_when_the_new_version_is_wrong`
  passes 20 runs in a row locally (`uv run pytest -m integration -n0 -k rolls_back`, in
  a loop), counted in the build report; `SystemPanel.test.tsx` passes 20 runs in a loop.
- AC-5: `make lint`, `make test`, `uv run pytest -m integration -n auto
  tests/integration/test_update_process.py` and `make web` pass; CI's `ci-ok` is green
  on the pull request.

## Impact

- `web/src/SystemPanel.tsx` (`finished`), `web/src/SystemPanel.test.tsx`,
  `tests/integration/test_update_process.py`, `docs/design/ui.md`, CHANGELOG.md.
- No API, MCP tool, CLI or schema change: a patch-level fix (it rides in the coming
  0.39.0, already unreleased).

## Decisions for the record

- Scale hotfix: a defect with a clear symptom and a confirmed cause, three files of code
  and tests.
- The fix is in the wait's end condition, in the page and the test alike (the human's
  choice), not in `self_update.run`: the lock stays the one source of `running`, and the
  result stays written under it so no second update can be overwritten.
- No delta to the API or the server: `UpdateInfo` already carries `running`.
- The test gets no longer timeout and no retry: it waits for the state it asserts.
