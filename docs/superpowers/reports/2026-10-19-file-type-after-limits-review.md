# LAD-102 file-type-after-limits: review report

Pull request #107 `hotfix/lad-102-file-type-after-limits` → `main`. Scale: hotfix,
reviewed for precision: the diff changes only how the web UI's file chips render, no
business logic or user data. Head reviewed last: `f339134` (= the remote head).
`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/`
are not changed: no live tests needed.

## Rounds

- **Round 1, local** (precision, `f46157d..f339134`): the whole diff read
  (`attachFiles.tsx`, its tests, docs, CHANGELOG, the openspec change); a grep of
  `web/src` finds no other reader of the removed `mediaType` and of `thumb`, now set for
  every file; the scenarios of `attached-file-chips` are covered (before and after the
  limits load by the new vitest test, attached after the limits by the Composer test "the
  paperclip opens the picker…"); D1-D4 kept, `tests/ui/test_chat.py` untouched. No
  findings.
- **Round 1, external** (Claude Code GitHub Action, request
  https://github.com/ladohq/lado/pull/107#issuecomment-6267143404, "Claude finished"):
  nothing blocking, two minor findings (E1, E2).

External rounds used: 1 of 1 (the cap for a hotfix). The external reviewer is of the same
model family, so its "nothing blocking" weighs less.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| E1 | 1 | external | An object URL is made for a file that is not an image and is never shown | confirmed | minor | declined: decision D2; the reason is in the comments above `attachFiles()` and on `thumb`, the URL copies no bytes and `release()` revokes every one |
| E2 | 1 | external | Files attached before the limits load skip the field's size and count checks; the server refuses them on upload | confirmed | minor | declined: the behaviour predates the pull request, is out of scope in the proposal and documented in docs/design/ui.md ("the server checks the rest") |

Confirmed 2 (both declined), refuted 0, fixed 0.

## Checks

- Local: `npx tsc --noEmit` clean; `npx vitest run src/attachFiles.test.tsx
  src/Composer.test.tsx src/WaitingCard.test.tsx` 68/68. The developer's `make lint`,
  `make test` (3607 passed, 1 skipped), `make web` (955/955) and `openspec validate` on
  the same head were not rerun.
- CI on `f339134`, run 39251642844: attempt 1, job "ui (1)" red in `make dist` (its
  `make web`) on the vitest flake `src/ForgetMany.test.tsx` "when the session open in the
  page is forgotten, the page goes to /sessions" (954/955), a file outside the diff,
  tracked as LAD-111; attempt 2 (`gh run rerun --failed`) green, 955/955 vitest, 101 UI
  tests passed, `ci-ok` success.

## Not checked (residual risk)

- Task 3.2 (the attach UI test 20 times in a row with `-n 2`) and task 3.3 (by hand, with
  `/api/limits` delayed 2 s: 3 eyes on main, 1 with the fix) were not run: Chromium does
  not start in LADO's container (LAD-110). They are left to the human; the browser's
  stability rests on 5 green CI runs of the shard "ui (1)" (4 in run 39247496368, 1 in
  run 39251642844). The human approved the merge without them.
- "The new test is red on main" was confirmed by reading the code, not by a run in the
  review; the developer reports it red on main (3 eyes).

## Found on the way

- The vitest flake `ForgetMany.test.tsx`: LAD-111, already in the tracker.
