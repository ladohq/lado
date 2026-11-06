# LAD-218 session-tabs-status-words: review report

Pull request #229 `hotfix/lad-218-tabs-status-words` → `main`. Scale: hotfix, review depth:
precision. Head reviewed: `03727bbe`. Findings F1 to F4 of the design QA of LAD-197: on the last
level before the scroll `Yours | All` folds into the phone's icon, so a chat of 420 px keeps its
four tabs whole; a focused tab and the tab shown stand clear of the fade, › and ‹; the popup's six
words name an agent's status on the Agents tab, on an agent's page, in the update's list of what
to restart and in the accessible names of a terminal's tab and a phone's chip; the team's list
button shows its name as a tooltip, not while its list is open. The web UI alone: no API, schema,
MCP or CLI change. Delta: 4 requirements added, 4 modified in `activity-agent-messages`,
`session-head` and `session-layout`.

## Rounds

1. Local, precision, `origin/main...03727bbe`: the whole diff read by hand, `Tooltip.tsx` included;
   the spec compared; browser probes from a folder outside the repository. R1 to R4.
2. External 1, Claude Code GitHub Action: nothing blocking, two suggestions (E1, E2).

External rounds used: 1 of 1.

## The human's decisions

- **#4034:** the icon in place of `Yours | All` on the last level, and the rest as recommended.
- **Gate `merge_ok`, approved** with no comment: R1 to R4 stay declined.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| R1 | minor | the update's dialog has `supervisor working` beside `Busy agents lose their current turn.`; the same sentence is in the CLI (`self_update.py`) | declined: a sentence, not a status label; the spec names the list alone, and a fix must decide on the CLI too |
| R2 | minor | the list button's tooltip, closed by Esc, comes back after the window's width changes (`holdFocus`, a plain `focus()`); confirmed by a browser probe | declined: needs the keyboard's focus and a change of width at once |
| R3 | minor | the tab shown is kept in view when the tab or level changes, not when the width changes inside level 4 | declined: the old code did the same, and following every resize would undo a row scrolled by ›; read in the code, not reproduced in a browser |
| R4 | minor | no test in the repository for the list button's tooltip on the keyboard's focus | declined: the behaviour passed a browser probe, only the test is missing |
| E1 | — | external: wrap `focusQuietly` in `try/finally` | refuted: `focus()` does not throw here, the element comes from the DOM |
| E2 | — | external: a browser test that the hidden form is out of the tab order | refuted: `display: none`, and `to_have_count(0)` by role in two tests covers both sides |

## Checks

| Check | Head | Result |
|---|---|---|
| `openspec validate session-tabs-status-words --strict` | `03727bbe` | passed |
| `openspec archive`, `openspec validate --specs --strict` | `03727bbe` | 61 passed, 0 failed |
| CI of the pull request | `03727bbe` | `ci-ok` green: unit, integration, ui, js, container; smoke skipped, every file on the skip list |
| `make lint` | `03727bbe` | clean |
| `make web` | `03727bbe` | 69 files, 1458 passed |
| `uv run pytest -m ui -n 4` on 2 files | `03727bbe` | 68 passed |

`make test`, the whole UI layer and the integration tests ran in CI, not locally. The smoke and
live tests were not run: `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py`
and `tests/live/` did not change.

## Metrics

Rounds: 1 local, 1 external, 0 stand-in. Confirmed: 4 local, 0 external. Refuted: 0 local, 2
external. Findings in code changed by the developer's cleanup: 0.

## What was not checked

- The mockup `mockup-tabs-status.html` was not opened by the reviewer; the screenshots were held
  against the spec and `docs/design/ui.md`.
- R3 was not reproduced in a browser.
- The flake of `test_the_strips_badges_tell_task_sessions_apart` the developer met did not show
  in CI, and nobody compared it on a clean main; it is in BACKLOG.md.
- The external reviewer read only `Sessions.tsx`, `Tooltip.tsx`, `Team.tsx` and `styles.css`, not
  `Agents.tsx`, `SystemPanel.tsx`, `Terminals.tsx` or the tests. The reviewer is of the same model
  family.

## Found on the way

- The tooltip of the agents' chips after a trial of Team's levels: the same `holdFocus` as in R2,
  there since LAD-197. Read in the code; for BACKLOG.md.
