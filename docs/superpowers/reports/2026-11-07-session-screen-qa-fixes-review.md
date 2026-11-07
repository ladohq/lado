# LAD-224 session-screen-qa-fixes: review report

Pull request #240 `fix/lad-224-session-screen-qa-fixes` → `main`. Scale: tweak, review depth:
precision by the design, widened to breadth by the reviewer, as the diff changes all 13 windows and
`RowMenu`'s behaviour. Head reviewed: `9b724eb7`. Findings F46 to F51 of the design QA after LAD-196
and LAD-198: a closed window gives the focus back through one hook, `useModal`, with no tooltip; on a
phone held sideways the toggle Messages between agents ends the tab row; the kit windows' warnings
and a failed login are notices; a run's tooltip shows the task its row hides, and its line stays
`--muted` on a waiting run; Session is the first group of the Artifacts tab. No server, API, schema
or provider change. Delta: the new capability `dialog-focus`, and changes to
`activity-agent-messages`, `artifacts-list`, `flows-overview`, `notices`, `stopped-session`,
`tooltip-focus`.

## Rounds

1. Local, breadth, `506dd44d..e538daad`: lenses spec, tests, silent failures, comments, general and
   the architecture against AGENTS.md; the types lens skipped, as there are almost no new types and
   the fields `tip` and `tipWhen` were read in the general lens. Found R1-1, R1-2 and the refuted
   R1-6 to R1-11.
2. External 1, Claude Code GitHub Action: no blocker, 5 minor remarks: R1-1 and R1-2 again, and the
   new R1-3, R1-4, R1-5. It read all the risky code of `web/src`; it read no tests, `openspec/` or
   `CHANGELOG.md`.
3. Local, precision, `e538daad..9b724eb7`: comments, documents and BACKLOG.md only; no new finding.
   No external round: the cap of 1 was used and no code changed.

External rounds used: 1 of 1. Stand-ins: 0.

## The human's decisions

- **Design:** the icon in the tab row for the toggle sideways (mockup option 1); the notes on 720 px
  and Copy link need no edit, closed on 2026-11-06.
- **Answer #4430:** the screenshots are attached to the task and shown in the pull request.
- **Gate `merge_ok`, approved** with no comment: R1-3 and R1-4 stay declined.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| R1-1 | minor | `ui.md` said 26 px for the phone's icon, the code and the same file's new line 36 px | fixed in `85085dfc` |
| R1-2 | minor | a comment promised that the run's tooltip fits a window of 390 px, which does not always hold | fixed in `85085dfc`, in D5 too |
| R1-3 | minor | external: `.slice(0, 600)` can cut a surrogate pair, leaving half an emoji before "…" | declined: looks only, a task over 600 characters with an emoji on the limit |
| R1-4 | minor | external: `modal.ts` and `design.md` do not say what to do if a React update stops firing events in commit | declined: D2 describes the departure, and the UI test falls on such a change |
| R1-5 | — | external: `split("\n")` leaves `\r` in a CRLF task | refuted: `white-space: pre-line` collapses it, the line count is the same |
| R1-6 | — | local: a window closed by the browser, outside React's commit, shows the button's tooltip | refuted: all 13 windows cancel `cancel` and Esc's default, and the one `method="dialog"` form cancels its submit |
| R1-7 | — | local: StrictMode's trial close fires `close` and shuts the window at once | refuted: no `<dialog>` has an `onClose` listener |
| R1-8 | — | local: a window from the System panel loses its opener | refuted: the panel stays while `asking` or `sharing` runs |
| R1-9 | — | local: `.run-task-line` cannot be measured in a History row | refuted in Chromium: a cut line measures 1724 at a width of 508, a whole one 508 |
| R1-10 | — | local: at 568 px the icon does not fit beside the tabs after a return to Activity | refuted in Chromium with touch: the tabs end at x = 287, the icon at x = 524 |
| R1-11 | — | local: the kit's window of several steps changes `Modal` and loses its opener | refuted: Install → Esc and Install → Back → Cancel give the focus back to Install, with no tooltip |

## Checks

| Check | Head | Result |
|---|---|---|
| CI of the pull request, required `ci-ok` | `9b724eb7` | green: unit, integration, UI 1 and 2, JS, container; first attempt, no reruns |
| smoke | `9b724eb7` | skipped: the diff is within ci.yml's skip list |
| `make lint` | `9b724eb7` | clean |
| `openspec validate session-screen-qa-fixes --strict` | `9b724eb7` | valid |
| `npx vitest run`, `npx tsc --noEmit` | `e538daad` | exit 0 for both; the test count was not taken. Only comments changed in `web/src` afterwards, and CI ran `make web` |
| `openspec validate --specs --strict`; trial archive | `e538daad` | 65 and 66 passed; the developer repeated both at the new head with the same result |
| the reviewer's Chromium probes, outside the repository | `e538daad` | 4 passed (R1-9, R1-10, R1-11) |

`make check` was not run locally: CI ran what it holds. The live tests were not run: `providers/`,
`hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not change.

Flakes: none.

## Metrics

Rounds: 2 local, 1 external, 0 stand-in. Local: 2 confirmed, 6 refuted. External: 2 confirmed, 1
refuted, and 2 the same as the local ones. Findings in code changed by the developer's cleanup: 0.

## What was not checked

- That no tooltip shows after a window closes rests on an inner trait of React, not on the code. Its
  guard is the UI test `test_forget_gives_the_focus_back_with_no_tooltip`, which the developer showed
  able to fail.
- The console errors (AC-10) are sorted only in part. The report's 16 cannot be sorted, as it holds
  no texts; 130 messages of the UI suite were sorted instead, some by test names alone. Three 404s
  stay unexplained, one of them on `forget-preview`, the Forget window that changed; no link to the
  change is seen, but none was checked.
- The focus's return was checked in Chromium alone, not in Safari or Firefox.
- Details, ForgetMany, the removal of a project and of a repository, New project and the LADO update
  have no browser test of their own; they share the hook, and a unit test forbids any other path.
- The scenario "A tap" has no test on a run's row; `Tooltip`'s shared logic holds it.
- The reviewer looked at 4 of the 8 screenshots and did not check them against the HTML mockups; the
  developer looked at all 8 for secrets.

## Found on the way

All in BACKLOG.md at `9b724eb7`; no tracker task was created.

- P2: `POST /api/sessions/{name}/messages` answers 500 when the session stops during delivery:
  `TmuxError` is not caught.
- P2: `.kit-danger` in the kit removal window has a border and no icon, against the notices rule.
- P3: 3 errors 404 on `agents/*/details` and `forget-preview`, cause unknown.
