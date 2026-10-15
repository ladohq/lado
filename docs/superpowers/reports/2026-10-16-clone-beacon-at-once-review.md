# LAD-79 clone-beacon-at-once: review report

Pull request #73 `hotfix/lad-79-clone-beacon-at-once` → `main`. Scale: hotfix, reviewed
for precision (not widened: one line of web UI code and one vitest case, no business
logic or user data). Head reviewed last: `62e9639` (= the remote head before the
archive). `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and
`tests/live/` did not change, so live tests are not needed before the merge.

## Rounds

- **Round 1, local** (precision over `origin/main...92820cf`): F1. No external round
  requested while F1 was open.
- **Round 2, local** (precision over the delta `92820cf..62e9639`): F1 resolved.
- **Round 1, external** (Claude Code GitHub Action, request
  https://github.com/ladohq/lado/pull/73#issuecomment-6203244229 at 22:05:21Z, "Claude
  finished" in job https://github.com/ladohq/lado/actions/runs/38814679470): no blockers,
  two optional nits (F2, F3). CI on `62e9639`: `ci-ok` pass (run 38813715022).

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (tests, spec) | The AC-2 check (no new beacon at the change that shows the clone's end) could not fail: its second `pagehide` was sent when the region "Session marketplace" appeared, after `POST /api/sessions` and the navigation, when any listener removal had already run | confirmed (a probe that deferred the removal with `setTimeout` stayed green) | important | fixed in `62e9639`: the second `pagehide` goes when Cancel clone disappears; a deferred removal now fails `expected 3 to be 2` |
| F2 | ext 1 | external | The `MutationObserver` watches `attributes` and `characterData` of the whole `body`; could be narrowed to `childList` | confirmed | minor | declined: the `atRunning`/`atEnd` flags make extra calls harmless, and a narrower observer could miss the change that shows or hides Cancel clone, weakening the check for test speed only |
| F3 | ext 1 | external | The CHANGELOG line ("the very moment its clone shows running") is narrow: the race lasted until React's passive effects ran | confirmed | minor | declined: the window is milliseconds after that same moment; the reviewer itself said it reads fine |

Refuted: none.

## Checked

- The fix `useEffect` → `useLayoutEffect` (`web/src/Launch.tsx`): the layout effect and
  its cleanup run synchronously in the commit, before the `MutationObserver`'s microtask.
- The case is red on the code before the fix: `expected +0 to be 1`.
- On the pull request's code: 40 of 40 runs (eight at a time) on `92820cf`, 8 of 8 on
  `62e9639`; the developer reported 200 of 200.
- `openspec validate clone-beacon-at-once --strict` valid; every task of tasks.md
  checked.

## Not checked (residual risk)

- `make web` as a whole was not run by the reviewer (the developer reports 825 of 825
  vitest; CI runs it).
- Python tests not run locally: no Python changed; CI runs them.
- The external reviewer is of the same model family and ran no tests: its "no blockers"
  weighs less.

## Found on the way

None.
