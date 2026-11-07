# LAD-223 session-card: review report

Pull request #241 `fix/lad-223-session-card` → `main`. Scale: tweak, review depth: precision,
widened to breadth for round 1 (the diff writes in `state.py` and changes the shared `Tooltip`).
Head reviewed: `59d24a50`. A row of the session list drops the agents' count, `idle` drops it
wherever the mark's words go, and the session's card becomes labelled facts (Project, Ran, Folder,
Kits, CLI, Mode) under a state line, 360 px wide, right of the list and inside the window.
`SessionInfo` gets `project_title`, and a project's rename reaches open windows. No schema
migration, no MCP or CLI change. Delta: the new capability `session-card` (9 requirements), 1
requirement modified in each of `session-status-mark`, `session-head` and `session-title`.

## Rounds

1. Local, breadth, `origin/main...943c48c9`: 1 important, 2 minor, 5 refuted.
2. Local, precision, `943c48c9..71c3d858`: F1 to F3 closed, one new minor (F4).
3. External 1, Claude Code GitHub Action, `506dd44d..71c3d858`: no blocker, two notes with no
   action. It read every risky file (`models.py`, `state.py`, `Sessions.tsx`, `Tooltip.tsx`,
   `styles.css`) and `tests/test_state.py`, `tests/test_feed.py`; not the specs, the documents or
   the other tests. It is the same model family as the kit's agents.
4. Local, precision, `71c3d858..9b531796`, the return from `merge`: PR #240 (LAD-224) conflicted in
   `web/src/Tooltip.tsx` and `tests/ui/test_layout.py`. The resolution and the archive are right;
   one new important (C1).
5. Local, precision, `9b531796..59d24a50`: `git show --remerge-diff` is empty, no code in the
   commit. C1 closed, one new minor (C2).

External rounds used: 1 of 1, on `71c3d858`; rounds 4 and 5 asked for none, the delta being merges
and the archive. Stand-ins: 0.

## The human's decisions

- **Answers #4348, #4361, #4385:** labelled rows, no count in the card when idle, the project by
  its title, the card right of the list, and the pointer on the card (WCAG 1.4.13) left out as a
  deliberate exception.
- **Gate `merge_ok`, approved** twice, on `71c3d858` and on `59d24a50`.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | after `lado project rename` the card showed the new title and the head's breadcrumb the old one | fixed in `71c3d858` |
| C1 | important | after PR #242 (LAD-226) the pull request did not merge: `mergeable: false`, `dirty`, from a conflict in `BACKLOG.md` that `merge=union` hides locally | fixed in `59d24a50`, both sides' entries kept |
| F2 | minor | no test covered the card's bounded height | fixed in `71c3d858`, `test_in_a_window_lower_than_the_card_it_is_cut_at_the_windows_height` |
| F3 | minor | D6 of `design.md` described what the code does not have | fixed in `71c3d858` |
| F4 | minor | the check commented `its arrow stays` reads the arrow's computed `left`, which does not change when the arrow is cut | declined: the behaviour is right, only the check is loose |
| E1 | minor | external: in a very low window the line on how to go on is cut first | declined: the card's cut end is out of scope in `proposal.md`, and Details and the session's page give the same way |
| C2 | minor | no empty line before `## The rail's…` in `BACKLOG.md` | declined: a trace of `merge=union`, the same gap is on `main`, and only people read the file |
| E2 | — | external: the arrow's place on a cut card | refuted: `size.height` is taken after the cut |
| R1 | — | removing `.tooltip-line.waits` took the colour from `AgentPopup` | refuted: `.tooltip .tip-status.waits` sets it |
| R2 | — | the new `waits(session)` condition shows `1 gate` in a stopped session's row | refuted: `waits` needs `isLive` |
| R3 | — | the empty `UPDATE sessions` sets off other triggers | refuted: the statistics fire on INSERT, and `changes` is read by `feed.py` alone |
| R4 | — | `Open it and press Resume` is wrong for `tmux_gone` | refuted: `tmux_gone` has Resume |
| R5 | — | the MODIFIED deltas lose scenarios of the living specs | refuted: a trial archive changed only the lines meant |

## Checks on `59d24a50`

| Check | Result |
|---|---|
| `make lint` | clean |
| `npx tsc --noEmit` | clean |
| `npx vitest run` | 70 files, 1537 passed |
| `uv run pytest -m ui` on `test_layout`, `test_session_list`, `test_launch`, `test_phone` | 138 passed |
| `openspec validate --specs --strict` | 67 passed |
| CI | 23 pass, `ci-ok` green |

## Not checked

- `make test` was not run by the reviewer; CI and the developer's run (4826 passed, 7 skipped)
  cover it.
- `make test-live` was not run. The diff does not change `providers/`, `hooks.py`,
  `mcp_server.py`, `runtime.py`, `agent_env.py` or `tests/live/`, so none was needed before the
  merge. It changes `state.py` and `server/models.py`.
- That F1's new test was red before the fix, and F2's probe (222.56 > 184 without `max-height`),
  come from the developer's report; the reviewer read both and did not reproduce them.
- The reviewer looked at the screenshots `shot-list`, `shot-card-working`, `-gone-gated` and
  `-kits` only, in round 1.
- That GitHub does not apply `merge=union` is drawn from what was seen: clean locally, `dirty` on
  GitHub, and a conflict in `BACKLOG.md` without the attribute.

## Notes

- The 640 px scenario changed after the approval: at 640 px the list is folded into icons and has
  no rows, so it became two scenarios, a row at 590 px and an icon at 640 px. The rule is the same.
  The run's artifact `design` still holds the old AC-7; the archived change is right.
- A tall tooltip moves inside the window when it fits neither under nor over its trigger, and its
  arrow may then miss the trigger. Staying in the window comes first.
- The archive's commit replaces the placeholder Purpose of `session-card` with the text at the end
  of `design.md`.

## Found on the way

- A trap for `.lado/sdlc.md`, Review traps: a local `git merge-tree` says no conflict in
  `BACKLOG.md` where GitHub sees one, as `merge=union` works only here. Look at the pull request's
  own `mergeable`. The human keeps that file; not changed.
- A row's trouble status is grey, where the mockup and `docs/design/ui.md` say `--danger`. Older
  than this task; in BACKLOG.md, P2, `ce261f4d`.
