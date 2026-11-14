# LAD-281 new-session-focus-stays: review report

Pull request #301 `hotfix/lad-281-new-session-focus-stays` → `main`. Scale: hotfix, depth
precision. Head reviewed: `3a29b3e5`. The New session window moved the focus to Task (or Folder
name) whenever the recent places came, so a slow answer took a focus the human had already moved;
under CI load this made `test_the_session_list_and_session_windows_give_the_focus_back` flaky.
The window now moves the focus on that answer only while it is still where the window put it at
opening, or on the page's body.

## Rounds

1. Local, precision (`85dafa79..3a29b3e5`), checked against the change's spec and design; and
   external 1, Claude Code GitHub Action (request 16:42:24Z, "Claude finished" 16:43:14Z). The
   external round read `Launch.tsx`, `modal.ts`, `test_launch.py`, `ui.md` and `CHANGELOG.md`,
   not the openspec files (checked locally).

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | external: no vitest test of the guard; `make web` would not catch a regression in jsdom | declined: design D2 makes the UI test the required layer; the race of the browser's focus and a network answer shows only in Chromium, and CI's UI cells catch it |
| F2 | — | external: the body check is redundant, as the opening focus is body when focus is lost at opening | refuted: the body branch covers a focus lost after opening (a click on a non-focusable area) |

The local pass found no defect. Checked by reading: `useModal` calls `showModal()` in a layout
effect, the opening focus is taken in a passive effect declared before the effect on `opened`, so
an at-once `opened` (a draft, a project, a path) moves the focus as before; typing in Where before
the answer sets `placeTouched` and no move follows; the other focus moves are untouched.

## Metrics

Rounds: 1 local, 1 external, 0 stand-ins. Findings: local 0 confirmed / 0 refuted; external 1
confirmed (minor, declined), 1 refuted; findings in code changed by the developer's cleanup: 0.

## Checks

- `uv run pytest -m ui -n auto tests/ui/test_launch.py tests/ui/test_layout.py -k "recent_places
  or give_the_focus_back"`: 4 passed.
- `openspec validate new-session-focus-stays --strict`: valid.
- CI on `3a29b3e5`: `ci-ok` pass; unit, integration (6 shards), ui (4), web, container (4) pass;
  smoke skipped (every changed file is on ci.yml's skip list).

## Residual risk

- The new test's red run on the old code was seen by the developer only; the reviewer confirmed
  the mechanism by reading (the old effect moved the focus unconditionally).
- `make test`, `make web` and `make lint` were not run locally by the reviewer; green CI covers
  them. The smoke was not run.
- No change to `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
  `tests/live/`: no live tests needed.

Found on the way: none.
