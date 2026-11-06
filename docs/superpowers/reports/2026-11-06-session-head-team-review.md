# LAD-197 session-head-team: review report

Pull request #228 `feature/lad-197-session-head-team` → `main`. Scale: full, review depth:
breadth first. Head reviewed: `d9479cd2`. Above a phone the team stands in the session's head on
every tab, in four levels of give, one level for all its agents; a team with names leaves the
title its first 24 characters. `Yours | All` moved to the tab bar, the keys hint shows only in an
empty field with the focus, and at 1440×900 the feed starts at y = 88 and is 742 px high. The
marks like `D2` and the ring at a status mark hold in the terminal strip too. The web UI alone:
no API, schema, MCP or CLI change. Delta: 12 requirements added, 13 modified, 2 renamed in
`activity-agent-messages`, `chat-question-card`, `phone-layout`, `session-head` and
`session-layout`.

## Rounds

1. Local, breadth, `origin/main...48c7ae8e`: F1 to F12.
2. Local, precision, `48c7ae8e..d9479cd2`: `2ad3729d` read whole, the conflicts' resolution
   checked with `--remerge-diff`, the browser probe repeated: nothing new.
3. External 1, Claude Code GitHub Action, `84304099..d9479cd2`: nothing blocking, four notes
   (F13 to F16).

External rounds used: 1 of 2. The design QA through `ui-review` had not run at the merge.

## The human's decisions

- **#3978, 2026-11-06:** the mockup is the base; the title gives way before the agents' names,
  but below about 24 characters the team goes to the next level; one level for the whole team,
  no mixed row; the feed's targets at 1440×900 are y = 88 and 742 px instead of 90 and 744; the
  `D2` marks and the status ring also hold in the terminal strip.
- **Gate `merge_ok`, approved:** F13 and F14 stay declined.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | blocker | the pull request conflicted with `main`, so CI did not run at all | fixed in `2ea2be3d`, both sides kept |
| F2 | important | opening the title field set off a trial: the team widened and the field narrowed | fixed in `2ad3729d` |
| F3 | important | a trial dropped the focus to `body` and closed an open list | fixed in `2ad3729d` |
| F4 | minor | the run time took the title's room without a trial | fixed in `2ad3729d` |
| F5 | minor | with storage refused, the choice was lost when the tab changed | fixed in `2ad3729d` |
| F6 | minor | the toolbar and the radiogroup swallowed Alt+← | fixed in `2ad3729d` |
| F7 | minor | task 7.2 was checked though the dark theme was not shot everywhere | fixed in `2ad3729d`: the task names what is left to the design QA |
| F8 | important | `reconnecting…` is wider than `live` and set off no trial: the row ran 4.5 px into Stop | fixed in `2ad3729d` |
| F9 | — | an empty mark on the terminal strip | refuted: the strip and the marks come from one list |
| F10 | — | no team in a window up to 600 px with a mouse | refuted: `PHONE_QUERY` holds such a window a phone |
| F11 | — | the portal loses the terminals' context | refuted: `createPortal` keeps React's context |
| F12 | — | the list goes under the terminal panel | refuted: `elementFromPoint` at 768, 1024 and 1440 gives the list, repeated at `d9479cd2` |
| F13 | minor | external: `useAgentMessages` subscribes in an effect, a write between render and effect is missed | declined: nothing writes the choice in that window |
| F14 | minor | external: a long line in the head comment of `Composer.tsx` | declined: the comment's width only |
| F15 | — | external: `data-short` on levels 1 to 3 is not explained | refuted: the comment above `LAST_FIT` says it |
| F16 | — | external: the radios answer the up and down arrows | refuted: the usual keys of a radio group |

## Checks

| Check | Head | Result |
|---|---|---|
| `openspec archive`, `openspec validate --specs --strict` | `d9479cd2` | 61 passed, 0 failed |
| CI of the pull request | `d9479cd2` | `ci-ok` green; smoke skipped, every file on the skip list |
| `make lint` | `d9479cd2` | clean |
| `make web` | `d9479cd2` | 69 files, 1449 passed |
| `make test` | `d9479cd2` | 1 failed: `test_kits_lists_the_same_kits_in_every_folder`, the word `team` in the worktree's path; the unit tests are green in CI, the test is in BACKLOG.md |
| `uv run pytest -m ui` on 2 files | `d9479cd2` | 90 passed |

The whole UI layer ran in CI, not locally. The smoke and live tests were not run: `providers/`,
`hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not change.

## Metrics

Rounds: 2 local, 1 external, 0 stand-in. Confirmed: 8 local, 2 external. Refuted: 4 local, 2
external. Findings in code changed by the developer's cleanup: 0.

## What was not checked

- The design QA through `ui-review` had not run: the title field beside Team, the Agents tab,
  the branch at 1600 px, whether `Yours | All` reads without its word, the dark theme of the
  screens not shot in it. The questions are in the pull request's description.
- A column of 420 px on Activity: the tabs go into their scroll beside `Yours | All`. The spec
  allows it; a question for the design QA.
- The margin of `.action-problem` from LAD-195 (`2ad3729d`) has no test of its own; the rule is
  the same as `.field-problem`'s.
- Some tests of the developer's first visit were not seen red; the test of the list at level 0
  was written with the code.
- A live agent's `run` changing with the names unchanged sets off no trial; whether the server
  does that was not checked. The level holds until the next trial.
- The message of `167d9a9e` names a wrong cause; `build-report` has the analysis.
- The external reviewer ran nothing and did not read `styles.css`, the tests or the documents.
  The reviewer is of the same model family.
