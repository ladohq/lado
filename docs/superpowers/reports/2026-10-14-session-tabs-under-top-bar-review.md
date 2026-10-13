# LAD-42 session-tabs-under-top-bar: review report

Pull request #29 `fix/lad-42-session-tabs-strip` → `main`. Scale: tweak, web UI CSS,
UI e2e tests and docs only. Head reviewed last: `5b730cf`; the archive commit follows it.
No API, schema or MCP change; `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
`agent_env.py` and `tests/live/` untouched, so no live tests before the merge.

## Rounds

- **Round 1** (`origin/main...e1d3498`): local precision pass (lenses spec, tests,
  comments, the architecture against AGENTS.md). Found F1. No external round requested.
- **Round 2** (`e1d3498..5b730cf`): local precision pass over the delta. F1 closed, F2
  found. External round 1 by the Claude Code Action (request 20:57:46 UTC, "Claude
  finished" 20:58:37 UTC): no blocker, three observations (F3–F5).

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | The alert "<agent> is not in this session" (`?terminal=` naming an absent agent) stuck to the top bar and touched the tabs once `.session-main` lost its top padding; the CSS comment and ui.md said only the start notice stands above the tabs | confirmed | important | fixed in `5b730cf`: `.session-main > .problem { margin: 12px 0 10px }`, comment and ui.md corrected; UI e2e `test_tabs.py::test_a_terminal_not_in_the_session_is_said_above_the_tabs` (red on the old CSS) |
| F2 | 2 | local | Alert and start notice shown together leave 22 px between them (flex items, margins do not collapse) | confirmed | minor | declined: both show together only on a resume with new settings and an absent `?terminal=` agent |
| F3 | ext 1 | external (Action) | The added ui.md sentence (Look, Tabs) runs past the file's line width | confirmed | minor | declined: docs only |
| F4 | ext 1 | external (Action) | The date 2026-10-14 in the docs differs from the PR's date | refuted | — | the work's local date; the PR's 2026-10-13 is UTC |
| F5 | ext 1 | external (Action) | The CHANGELOG line may not be under the unreleased section | refuted | — | `CHANGELOG.md:3` is `## 0.37.1 (unreleased)` |

| Source | Confirmed | Refuted |
|---|---|---|
| local | 2 (F1, F2) | 0 |
| external, Claude Code Action | 1 (F3) | 2 (F4, F5) |

## Deviations from the design accepted

- AC-3: in a window of 900 px or less the tab band starts right under the session list
  (or its strip), not under the top bar; recorded in tasks.md and ui.md.
- Task 3.2: the test changes the provider, not the permission mode, to make "Resumed with
  new settings" show.

## Checks

- Developer: `make lint`, `make web`, `make test`, the UI e2e files of task 3.3 (the known
  `test_gates` flake of BACKLOG.md failed once in the suite and passed alone).
- Reviewer: `uv run pytest -m ui tests/ui/test_tabs.py`: 16 passed.
- CI on `5b730cf` green: check (3.10, 3.13), ui, js, smoke × 8.

## Found on the way

None.

## Not checked

- The reviewer did not run the full UI suite, `make test`, `make web` or `make lint`;
  the developer and CI did.
- The external reviewer is the same model family and ran no tests.

## Result

Converged after round 2 (1 of 1 external rounds).
