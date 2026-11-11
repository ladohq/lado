# LAD-246 login-sheet-socket-wait: review report

Pull request #287 `hotfix/lad-246-login-sheet-socket-wait` → `main`. Scale: hotfix, depth
precision. Head reviewed: `87a4d7bd`. The tests of `web/src/LoginSheet.test.tsx` no longer read
the login window's socket before it exists: the window makes its socket in an effect, after it
is in the page, so every window opened after the server's answer takes its socket through the
new helper `socketMade(n)` of `web/src/fakes.ts`, which waits for exactly `n` sockets. Tests
only, no product code; no delta. The BACKLOG.md entry of the flake is removed.

## Rounds

1. Local, precision. The whole diff `origin/main..87a4d7bd` (commits `8c89b24c`, `87a4d7bd`):
   every socket read of `LoginSheet.test.tsx` after a `fetch` answer goes through
   `await socketMade(n)`; `lastSocket()` stays only in `window_()`, where `render` is
   synchronous. Every assertion kept, imports used. Tasks of `tasks.md` 7 of 7 checked; the
   design's decisions kept (`LoginWindow.tsx` untouched, no retries). No findings.
2. External 1, Claude Code GitHub Action: one minor, E1, refuted. It read `fakes.ts`,
   `LoginSheet.test.tsx` and `BACKLOG.md`; it did not read the openspec files only.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| E1 | — | external: `socketMade(n)` checks for exactly `n` sockets, so a third socket makes the wait time out instead of returning one | refuted: by design, the exact length catches a window that opens its socket twice (`web/src/fakes.ts:47`); the earlier `waitFor` of the same tests checked the exact length too; the reviewer itself advised keeping it |

## Found on the way

None.

## Checks

On `87a4d7bd`:
- `npx vitest run src/LoginSheet.test.tsx` in `web/`: 10 of 10 runs exit 0, 17 tests each
  (reviewer); 20 of 20 in a row and 5 of 5 under the full Vitest suite as load (developer).
- `npx tsc --noEmit -p web` exit 0; `openspec validate login-sheet-socket-wait --strict` valid.
- The race shown before the fix (AC-2): with `socket.start()` delayed by 50 ms the test failed
  on `lastSocket().url` as in CI, and passed with the fix; the developer's probe, not repeated
  by the reviewer.
- CI of PR #287: all green, `ci-ok` pass; the smoke skipped, as the pull request is within the
  skip list.

## Residual risk

The flake showed only under CI's load, so later CI runs will confirm it is gone. No change to
`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or `tests/live/`; live
tests not needed.
