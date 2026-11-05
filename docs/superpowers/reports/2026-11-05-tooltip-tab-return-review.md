# LAD-207 tooltip-tab-return: review report

Pull request #221 `hotfix/lad-207-tooltip-tab-return` → `main`. Scale: hotfix, review depth:
targeted. Head reviewed: `4e237784`. A focus that comes back to a tooltip's trigger with the tab
or window shows no tooltip, whatever the last input was; a focus the keyboard moves and the
pointer show it as before. `web/src/Tooltip.tsx` alone, through it every tooltip of the UI: no
API, schema, MCP or CLI change. Delta: a new capability, `tooltip-focus`, 2 requirements.

## Rounds

- **Round 1, local** (targeted, `origin/main...87080f08`): the spec check, all the tooltips'
  triggers read, the screenshot. Found F1 to F5.
- **Round 1, external** (Claude Code GitHub Action): read the risky files `Tooltip.tsx`,
  `Tooltip.test.tsx` and `test_session_list.py`; not `CHANGELOG.md` or `docs/design/ui.md`, so
  its words on them carry no weight. Found F6 and F7.
- **Refused archive** (integrator, at `87080f08`): after the archive `openspec validate --specs
  --strict` gave 58 passed, 1 failed; undone before any commit. Fixed in `4e237784`.
- **Round 2, local** (targeted, `87080f08..4e237784`, three documents under `openspec/`, no
  code): no new defects; F9 on the missing CI.

External rounds used: 1 of 1. The external reviewer is of the same model family.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | the new ref `left` is shadowed by a `const left` in the component's `useLayoutEffect` | declined: the effect does not read the ref, behaviour is not affected |
| F2 | minor | `tasks.md` 1.1 and design D2 had fallen behind the tests | fixed in `4e237784` |
| F3 | minor | the fixture `tabs` leaves its browser open when its setup fails before `yield` | declined: happens only on a test already red, and the browser ends with the run |
| F4 | — | `activeElement === currentTarget` misses a trigger that wraps a focusable child | refuted: no such trigger in `web/src`; true only of future code |
| F5 | — | without a reset of `left` in `onFocus` a stale flag eats the next focus | refuted: every blur rewrites the flag; the UI test of Tab and Shift+Tab is green |
| F6 | minor | external: into the address bar and Tab back to the same trigger shows no tooltip, once | declined: the browser does not tell this from the window's return; a consequence of the option the human chose; read from the code, not reproduced in a browser |
| F7 | — | external: `wait_for_timeout(500)` breaks if `TOOLTIP_DELAY_MS` grows past 500 | refuted: a tooltip from a focus shows at once, without the delay |
| F8 | important | the delta of the new capability had no `## Purpose`, so the living spec kept the `TBD` placeholder and `validate --specs --strict` failed: the refused archive | fixed in `4e237784`; a trial archive in a copy gave 59 passed, 0 failed |
| F9 | — | no CI on `4e237784`: 0 check-runs, the pull request in conflict with `main` in `CHANGELOG.md` alone | accepted by the human (#3706): the integrator merges `main` and waits for `ci-ok` before the merge |

F8 passed round 1 because `openspec validate <change>` does not see the placeholder and no trial
archive was made for the new capability. It is the third case after F6 of LAD-199 and A1 of
LAD-192 that a trial archive in a copy catches.

## Checks

At `87080f08`, the code and tests the same as at the head: `make lint` exit 0; `make test` 4814
passed, 7 skipped; `make web` 62 files, 1182 tests passed, types fresh; `uv run pytest -m ui
tests/ui/test_session_list.py tests/ui/test_sessions_strip.py -n auto` 12 passed; the new unit
tests on `main`'s `Tooltip.tsx`, in a copy, 3 failed, 13 passed; `ci-ok` green, the smoke skipped
as the pull request is within CI's skip list.

At `4e237784`: `openspec validate tooltip-tab-return --strict` valid; a trial archive and
`openspec validate --specs --strict` 59 passed, 0 failed; no CI (F9).

Not run locally: `make test-integration` and `make check` (excluded by the settings, CI ran
them at `87080f08`), `make test-js` (the plugin did not change), `make test-live`. `make
test-smoke` ran nowhere.

## Metrics

Rounds: 2 local, 1 external, 0 stand-in. Confirmed: 4 local (F1, F2, F3, F9), 1 external (F6), 1
at the archive (F8). Refuted: 2 local (F4, F5), 1 external (F7). Findings in code changed by the
developer's clean-up: 0. `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
`agent_env.py` and `tests/live/` did not change, so no live test was needed.

## What was not checked

- The pull request's code together with the current `main`, before the CI of the merge step (F9).
- Firefox and Safari: the sign of the window's leaving was measured in Chromium alone, and the
  whole fix rests on it.
- Leaving for another window (Cmd+Tab): the tests switch tabs only, the spec promises the window
  too.
- The red run of the UI tests on `main`'s code was not repeated; it comes from the build report
  (4 of 5). The red unit run was repeated.
- A future `Tooltip` around a focusable child gets no protection (F4).
