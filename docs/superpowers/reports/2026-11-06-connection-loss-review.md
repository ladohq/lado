# LAD-195 connection-loss: review report

Pull request #227 `feature/lad-195-connection-loss` → `main`. Scale: full, review depth: breadth
first. Head reviewed: `9ed795bc`. Two seconds after the change feed is lost the Live mark turns
into an amber `reconnecting…`, and the buttons that write wait. A request without an answer shows
"<What> not confirmed" with a disabled Retry; LADO reads the state itself and either the error
goes or it reads "<What> not delivered" with an active Retry. Send is settled by the feed, with no
server change. No raw exception text shows in the UI, and a failed reload keeps what the page
shows. The web UI alone: no API, schema, MCP or CLI change, `src/lado` untouched. Delta: the new
capability `connection-loss` with 12 requirements, 1 modified in `phone-layout`.

## Rounds

1. Local, breadth, `origin/main...a2595bbf`: F1 to F9. The code's diff read by hand, of the tests
   only `tests/test_closed_refusals.py` whole.
2. Local, precision, `a2595bbf..fbac6c30`: F10; the new screenshots held against the mockup.
3. External 1, Claude Code GitHub Action, `fbac6c30`, the whole pull request: F11, F12, F13. Read
   the risky files of `web/src` but `styles.css` and `icons.tsx`; no tests, documents or openspec.
4. Local, precision, `fbac6c30..9ed795bc`: F14 from CI's red `ui (1)`, nothing else new.
5. External 2, the same reviewer, `9ed795bc`, the delta: F15, nothing blocking; F11 and F12
   confirmed fixed.

External rounds used: 2 of 2.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | blocker | the global `.waits` met the existing class `waits`: waiting rows showed a forbidding cursor with the connection fine, `.strip-session` lost its grid | fixed in `cb6eb2e8`: class `lost-wait` |
| F2 | important | the `role="status"` region said "live" on a refused stream | fixed in `cb6eb2e8` |
| F3 | important | the pin of the refusals' texts missed the real path of questions | fixed in `cb6eb2e8`: through `runtime.answer_questions` |
| F4 | important | a drop while reading a record's body showed the raw exception | fixed in `cb6eb2e8` |
| F5 | minor | "Waiting for connection" on a run's page too large and out of line | fixed in `cb6eb2e8` |
| F6 | minor | Resume's table in `docs/design/ui.md` lacked `loop_down` | fixed in `cb6eb2e8` |
| F7 | minor | a second constant `SUPERVISOR` in `Composer.tsx` | fixed in `cb6eb2e8` |
| F8 | minor | two questions, one closed elsewhere: Retry refused whole counts as reached, the second answer is not sent | declined: the spec has it so, and the open question stays in the card with Send active |
| F9 | minor | the status region's "A short drop" has no test of its own | declined: its text comes from `lost`, covered in `live.lost.test.ts` |
| F10 | minor | a test's name promises "everywhere", it covers the chat | declined: the other places have tests beside it |
| F11 | important | external: `reached` of Stop closed any window of the head, an open Forget too | fixed in `d22afcae`: `closeStop` |
| F12 | important | external: Send's look with cursor 0 found the same earlier words, so a new message counted as reached and was lost silently | fixed in `d22afcae`: `Live.messageCursor`, without a cursor no message counts |
| F13 | — | external: `recover()` does not run when the stream opens after `refused` | refuted: after a 401 nothing connects again |
| F14 | important | CI at `fbac6c30`: `test_a_new_link_logs_another_browser_out_and_keeps_this_page` red; a short drop no longer unmounts Live (AC-2), the System panel stays open and the locator met two buttons | fixed in `d22afcae`: `exact=True` |
| F15 | — | external: `looks.send` with a `null` cursor could skip its request | refuted: without the server's answer `Unreached` must keep the outcome unknown; pinned in `attempts.test.ts` |

## Checks

| Check | Head | Result |
|---|---|---|
| `openspec archive`, `openspec validate --specs --strict` | `9ed795bc` | 61 passed, 0 failed |
| CI of the pull request, run 42222565251 | `9ed795bc` | 23 of 23 passed, `ci-ok` green, the smoke of every provider on Linux and macOS passed |
| `make lint` | `9ed795bc` | clean |
| `make web` | `9ed795bc` | 1410 passed |
| `make test` | `9ed795bc` | 4823 passed, 7 skipped |
| `uv run pytest -m ui` on `test_connection.py`, `test_share_access.py` | `9ed795bc` | 22 passed |

The rest of `tests/ui/`, integration and the smoke ran in CI, not locally. `make test-js` was not
needed: the plugin did not change. `make test-live` runs at a release.

## Metrics

Rounds: 3 local, 2 external, 0 stand-in. Confirmed: 10 local, 2 external, 1 by a red CI; of these
10 fixed (1 blocker, 6 important, 3 minor) and 3 minor declined. Refuted: 0 local, 2 external.
Findings in code changed by the developer's cleanup: 0. `providers/`, `hooks.py`, `mcp_server.py`,
`runtime.py`, `agent_env.py` and `tests/live/` did not change, so no live test was needed.

## What was not checked

- AC-18 and the brief's ui-review: no step of its own. The developer and the reviewer held the
  screenshots against `mockup-connection.html`; the dark theme was shot for the chat, Needs you,
  Approve, Stop, Resume and Message. Frames g4-* were not compared: the mockup replaces them where
  they differ.
- A duplicate Send: with no retry key, Retry can send twice in two rare cases, when the look ran
  while the server was still writing the message, or when no cursor could be taken and the message
  had reached it. The human's choice: better a duplicate than a silent loss.
- A visible result of AC-2: the System panel no longer closes by itself after a new link in Share
  (F14).
- Needs you and a run's page opened with no connection read `No connection`, not the card; a
  gate's error shows there after the return.
- A proxy's 502 counts as a refusal of the server, not as `Unreached`. Not checked.
- F4 was not reproduced by a real drop in a browser, only by the code and a test with a failing
  stream.
- `LoginSheet.test.tsx` failed once at the first attempt and never again (1403, 1405, 1410 passed).
  Cause unknown, no flake proven.
- The external reviewer read no tests, documents or CSS, and is of the same model family; only the
  local pass covered them, and the new test files were not read line by line.

## Process

The developer reported their own departures from "edit tools only" (`api.ts`,
`connection.test.tsx`, a temporary `sed` for the probe of F3, undone). `cb6eb2e8` went out with one
failing UI test, fixed in `f0989b27`.
