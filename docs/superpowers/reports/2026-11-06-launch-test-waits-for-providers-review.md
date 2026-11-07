# LAD-219 launch-test-waits-for-providers: review report

Pull request #239 `fix/lad-219-start-in-waits-for-providers` → `main`. Scale: tweak, review depth:
precision. Head reviewed: `1bbd039d`. The flake of "Start in starts in the project's repository
chosen", a race in the test and not a defect of LADO: the test picked a provider while the field
Provider was off, and the empty value counted as the human's choice, so no timeout cured it. The
test now waits for the field. Besides, by the human's decision (question #4305), the suite gets one
`testTimeout` of 30 s and one `asyncUtilTimeout` of 10 s, the twelve `{ timeout: 3000 }` go, and two
entries leave BACKLOG.md. Tests, their configuration and documents only: no API, schema, MCP, CLI or
UI change, no CHANGELOG.md line. No delta.

## Rounds

1. Local, precision, `origin/main...cb0a8036`: no wide pass needed, the diff touches no business
   logic, no user data and nothing under `src/`. One important and one minor finding, none refuted.
2. Local, precision, `cb0a8036..1bbd039d`: F1 and F2 closed, no new findings.
3. External 1, Claude Code GitHub Action, the whole pull request `f3bb9a0f..1bbd039d`: no blocker, 3
   remarks. It worked for 20 s and ran no tests. No risky file was left out of `Files read`: three
   openspec files were not read, and `Launch.test.tsx` and `Layout.test.tsx` were read in part, at
   the changed places. It is the same model family, so its verdict weighs less.

External rounds used: 1 of 1.

## The human's decisions

- **Question #4305:** fix the test and add the suite's settings too.
- **Gate `merge_ok`, approved** with no comment.

## Findings

Confirmed and fixed, both local:

- **F1 (important).** The settings did not reach `vi.waitFor`: 9 real waits of the suite kept
  vitest's own 1 s, while `docs/testing.md` and the proposal spoke of the whole suite. A probe on a
  condition of 3 s: `vi.waitFor` failed after 1010 ms, `waitFor` passed. Fixed in `1bbd039d`: they use
  Testing Library's `waitFor`, two empty calls remain, and the rule is in `docs/testing.md` and
  `testSetup.ts`.
- **F2 (minor).** The proposal did not name the new P2 entry of BACKLOG.md. Fixed in `1bbd039d`: it is
  in What Changes and Scope.

Refuted, external:

- **F3.** Fake timers of `Layout.test.tsx` might leak into the test at line 1044 and hang `waitFor`.
  Both tests restore the timers in `finally` (lines 633-635 and 699-701), and the whole suite passed.

Declined, external:

- **F4 (minor).** A lint rule to hold the rule against `vi.waitFor`. Too much for this stage, and the
  two empty calls would need an exception (AGENTS.md, Only what is used).
- **F5 (minor).** A test that really hangs now costs up to 30 s, not 5 s. That is the settings' known
  price, named in the design; an ordinary wait fails after 10 s.

Found on the way: none.

## Checks

| Check | Head | Result |
|---|---|---|
| `/api/providers` 150 ms late, with the new line, in a copy of `web/` | `cb0a8036` | 3 of 3 passed |
| The same, without the new line | `cb0a8036` | failed, `expected true to be false` |
| `make lint` | `1bbd039d` | exit 0 |
| `tsc --noEmit`, in a copy of `web/` | `1bbd039d` | exit 0 |
| `npx vitest run`, in a copy of `web/` | `1bbd039d` | exit 0, 69 files, 1482 of 1482 |
| `openspec validate launch-test-waits-for-providers --strict` | `1bbd039d` | valid |
| `openspec validate --specs --strict` | `1bbd039d` | 62 passed, 0 failed |
| A trial archive with `--skip-specs`, then the specs | `1bbd039d` | 62 passed, 0 failed |
| CI of the pull request (run 42305296434) | `1bbd039d` | `ci-ok` green: 15 pass, smoke skipped, every file on the skip list |

The developer's results, not repeated by the reviewer: 20 runs in a row with the late answer, and
`Launch.test.tsx` 5 of 5 at load averages of 6-14. A trial merge with `origin/main` (`506dd44d`) had
no conflict. One with `origin/epic/lad-154-models` (`ed56ed32`) conflicts only in `CHANGELOG.md`, which
this pull request does not change; `Launch.test.tsx` merges by itself, and the epic's nine explicit
timeouts, recorded in BACKLOG.md, are to be deleted at its merge.

The risks of the settings were checked and did not hold: no test relied on a wait failing fast (the
longest ran 2.1 s on `cb0a8036`), no hook uses `findBy` or `waitFor`, so `hookTimeout` does not meet
the 10 s wait, and no file where `vi.waitFor` was replaced has fake timers but `Layout.test.tsx` (F3).

## Metrics

Rounds: 2 local, 1 external, 0 stand-in. Confirmed: 2 local, 2 external. Refuted: 0 local, 1 external.
Findings in code changed by the developer's cleanup: 0.

## What was not checked

- The load of 60-238 in BACKLOG.md was not reproduced: the developer's load average was 6-14. That
  10 s and 30 s are enough at such a load is not proved.
- The state of the field Provider in the very failure on CI is not known: the page dump is cut off.
  The test line and the error are the same.
- The reviewer did not run `make web` whole, as it writes to the developer's working copy; `tsc` and
  vitest in a copy stood in. The developer ran it on this head, and CI checked the build.
- `make test`, the UI and the integration tests ran in CI, not locally. The smoke was skipped and the
  live tests were not run: `src/` did not change, and neither did `providers/`, `hooks.py`,
  `mcp_server.py`, `runtime.py`, `agent_env.py` or `tests/live/`.
