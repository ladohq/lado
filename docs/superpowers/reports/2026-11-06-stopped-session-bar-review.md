# LAD-196 stopped-session-bar: review report

Pull request #230 `feature/lad-196-stopped-session-bar` → `main`. Scale: full, review depth:
breadth first. Head reviewed: `59a5506a`. Finding F17 of LAD-189: on Activity a stopped session
has a bar with Resume session in the composer's place, its empty feed says what it shows, the head
has Resume with its word on the tabs without the bar, a phone shows no team, the terminals stand
folded and store nothing, and an opened terminal says the agent is not running, with no Reconnect.
The web UI alone: no API, schema, MCP or CLI change. Delta: the new capability `stopped-session`
(8 requirements), 1 requirement added to `activity-agent-messages`, 1 modified in `session-layout`.

## Rounds

1. Local, breadth, `45e986b5...2a2f9ef6`: the whole diff read by hand; lenses spec, tests, silent
   failures, comments, types, general and the architecture against AGENTS.md.
2. External 1, Claude Code GitHub Action: no new defect; it read only the sources of `web/src`.
3. ui-review of the build (`ui-review/lad-196-build/critique`): no `fix`, 8 `consider`, taken in as
   U1 to U8. This is AC-10's ui-review.
4. Local, precision, `2a2f9ef6..59a5506a`: the fixes, the BACKLOG.md entry and the merge
   `d3e30e5d` by `git show --remerge-diff`; no new finding.
5. External 2, Claude Code GitHub Action: no new defect; it read the merge in `Sessions.tsx` and
   the whole diff of `styles.css`, which round 1 had not.

External rounds used: 2 of 2. Stand-ins: 0.

## The human's decisions

- **Answers #4044, #4051 (recorded in LAD-196, comment 1793984595543):** no one-click Resume, no
  agents on the strip, the second empty text under Yours.
- **Gate `merge_ok`, approved** with no comment: the terminal's colour (U2) as built, Quote without
  a response until Resume (D3), and F3, F4, F5, U1, U4, U5, U7, U8 stay declined.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| U2 | important | the terminal's text was brighter than in g5-term | fixed in `0e24667a`, with a deviation: `rgb(160,163,167)` light and `rgb(151,153,158)` dark against `rgb(154,161,173)`, up to 15 per channel; an exact match needs a token the design forbids |
| U3 | important | the pressed toggle on a phone was grey, blue in the frame | fixed in `0e24667a` |
| F1 | minor | Session head in `docs/design/ui.md` still said "Resume and Forget stay icons." | fixed in `0e24667a` |
| F2 | minor | `StoppedTerminal` stood between `AgentTerminal` and its comment | fixed in `0e24667a` |
| F3 | minor | a width dragged in a stopped session with `lado.terminals` empty writes the key, and the key reads as the human's choice: at 1024 px the terminals then stay and the list folds | declined: a width cannot be stored without the key, and D7 stores it as ever |
| F4 | minor | the rules that hide the composer under an expanded card and in a low window do not hide the bar | declined: on Activity the bar is the only way to Resume |
| F5 | minor | `chat-question-card`: "In a stopped session the composer SHALL not fold", while `Chat` passes the composer `folded` | declined: no fold line shows in a stopped session (`WaitingCard.tsx`); only the prop's name differs |
| U1 | minor | at 320 px two letters of the title are left in the head | declined: the spec cuts the title, not the button; a tap shows the whole name |
| U4 | minor | Resume session 15/600, 14/500 in g5-1440 | declined: as `mockup-stopped-session.html` and `.primary` |
| U5 | minor | Forget has a frame, none in g5 | declined: as the mockup, Resume and Stop |
| U7 | minor | the toggle's icon differs | declined: the product's icon; the mockup's critique itself disliked ⇄ |
| U8 | minor | a phone's margins 12 against 16 px; the feed's text 2 px left of the bar's centre | declined: the product's margin, and the feed's `padding-right` shared with a running session |
| U6 | — | a square on the terminal's tab instead of a round dot | refuted: `.dot-stopped` is meant so |
| E1 | — | external: `StoppedTerminal` renders on every tab | refuted: only the active tab shows |
| E2 | — | external: `composerField.focus()` on a hidden field does nothing | refuted: that path cannot be reached |

## Checks

| Check | Head | Result |
|---|---|---|
| `openspec validate stopped-session-bar --strict` | `59a5506a` | passed |
| trial archive, `openspec validate --specs --strict` | `59a5506a` | passed |
| CI of the pull request | `59a5506a` | `ci-ok` green, 15 passed; smoke skipped, every file on the skip list |
| `make lint` | `59a5506a` | clean |
| `make web` | `59a5506a` | 69 files, 1482 passed |
| `make test` | `59a5506a` | 4823 passed, 7 skipped |
| `uv run pytest -m ui` on 5 changed files and `test_narrow_layout.py` | `59a5506a` | 182 passed |

The whole UI layer and the integration tests ran in CI, not locally. The smoke and live tests were
not run: `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/`
did not change.

Flakes: CI `ui (1)`, step `make dist`, `src/Launch.test.tsx` "Start in starts in the project's
repository chosen" (line 2599, a `waitFor` on the button) failed in run `42267569487` and passed on
`gh run rerun --failed`; neither the test nor the window's code changed.
`test_the_strips_badges_tell_task_sessions_apart` failed once in the developer's full `make
test-ui` and passed in the reviewer's run and in CI; it is in BACKLOG.md.

## Metrics

Rounds: 2 local, 2 external, 0 stand-in. Confirmed: 12 (5 local, 7 ui-review, 0 external). Refuted:
3 (1 ui-review, 2 external). Findings in code changed by the developer's cleanup: 0.

## What was not checked

- Storing a width in a stopped session has no test (F3).
- The expanded card above the bar was not seen in a browser (F4).
- A feed with entries at 768 and 390 was not looked at, only run by e2e.
- `test_no_team_shows...`: `to_have_count(0)` can pass before the agents load; the absence rests on
  `HeadTeam` and on a stop deleting the agents.
- A real phone: only Chromium's emulation.
- ui-review was not repeated after U2 and U3; the developer's screenshots were held against the
  frames, and the colour is tested only within its tolerance.
- The external reviewer read no tests, documents or specs in either round. The reviewer is of the
  same model family.

## Found on the way

- The focus after Esc in the launch window: in BACKLOG.md, `052544b1`.
- The flake of `Launch.test.tsx` above: handed to the supervisor for a tracker search.
