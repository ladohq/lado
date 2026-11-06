# LAD-198 session-screen-polish: review report

Pull request #234 `feature/lad-198-session-screen-polish` → `main`. Scale: full, review depth:
breadth first. Head reviewed: `a5104bf2`. Findings F13, F20-F24, F26 and F27 of LAD-189: a column
under 720 px lists artifacts in two lines, 100 artifacts go in groups by scope that fold, the panel
says its title once, the empty tabs say where their content comes from, a run shows its task, an
opened event adds only "Step took", Stop offers no Stop and forget with open runs, and notices have
a ground and an icon. F6 matched the spec and did not change. One API field, `SessionKitInfo.flows`;
no schema, MCP or CLI change. Delta: the new capabilities `artifacts-list`, `flows-overview`,
`notices`, and changes to `artifact-panel`, `launch-notes`, `session-forget`, `session-layout`.

## Rounds

1. Local, breadth, `59899a57..e00d49f4`: lenses spec, tests, silent failures, comments, types,
   general and the architecture against AGENTS.md. Found R1 to R4.
2. Design QA of F20, run `ui-review/lad-198-f20`, head `e00d49f4`: 4 `fix`, 8 `consider`, taken in
   as QA-F1 to QA-F12.
3. Local, precision, `e00d49f4..a5104bf2`: the delta of code, specs and tests read whole, as the
   groups' logic was rewritten; no new finding.
4. External 1, Claude Code GitHub Action, the whole pull request `59899a57..a5104bf2`: E1 to E4. It
   read the changed code; `Menu.tsx` in part, `test_artifacts_tab.py` only lines 285-335. It read no
   specs, documents, generated files or other tests, and ran neither tests nor a browser.

External rounds used: 1 of 2. Stand-ins: 0.

## The human's decisions

- **Answers #4114, #4126 (design):** the list under 720 px, groups at any width, Full page on the
  Artifacts tab, Copy link for Share, the text for a session without flows, F26 on `--scrim`, Design
  QA for F20, one pull request.
- **Answers #4240, #4248 (Design QA):** QA-F1 to F4, F6, F8, F12 fixed; QA-F5, F7, F9, F10, F11
  declined, no tasks. Nothing moves under the reader.
- **Gate `merge_ok`, approved** with no comment: E1 stays an open risk, E2 and E3 stay declined.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| R1 | blocker | a long task line was not cut and widened the whole runs' overview (cards of 4262 px in a list of 600 px) | fixed in `52354b80` |
| R2 | important | the specs of `session-forget` and `artifact-panel` contradicted the new requirements | fixed in `52354b80` |
| R3 | minor | the version downgrade's warning showed as an error | fixed in `52354b80`, `.update-warning` |
| R4 | minor | an old step with no time or body opens on nothing | declined: only notes with no previous event, described in `ui.md` |
| QA-F1 | important | another run's write carried the row being read off the screen | fixed in `a5104bf2` |
| QA-F2 | important | a run's end folded its group and the focus fell to the body | fixed in `8bf66fac` |
| QA-F3 | important | the scope filter left the column with a long run name | fixed in `8bf66fac` |
| QA-F4 | important | in the flat list a run's prefix pushed the name out | fixed in `8bf66fac` |
| QA-F6 | minor | Full page and Expand did not read apart | fixed in `a5104bf2` |
| QA-F8 | minor | an ended run could stand above the working groups | fixed in `a5104bf2` |
| QA-F12 | minor | a screen reader heard a count with no unit | fixed in `a5104bf2`; no live screen reader tried |
| QA-F5, F7, F9, F10, F11 | — | a long name's end, the heading on scroll, a long heading's lines, a table row of 115 px, a search match not visible in the row | declined by the human |
| E1 | — | external: the row's link may cover only the text, as `container-type` on `.artifact-item-text` gives layout containment | unverifiable: not so in Chromium 153; Firefox and WebKit do not start here |
| E2 | minor | external: groups settle and fold when the runs arrive | declined: once, on the first load, and D3 chose to show everything |
| E3 | minor | external: `focusIn()` reads the focus during render | declined: only on a group's first layout, and it has a test |
| E4 | — | external: the contrast of `--danger` on `--danger-ground` is unchecked | refuted: `tokens.test.ts` holds both pairs at 4.5:1 in both themes |
| — | — | local: `NoRuns` keeps the previous session's flows; `useWidth` misses a root that comes later; "step null" on a run's record; Esc in "⋯" closes the panel; a long name widens the column; the tooltip fails at the row's right edge | refuted, six in all |

E1's probe: on a live page in Safari and Firefox press the type's icon in a row of the narrow list;
the panel must open. If it does not, move `container-type` from `.artifact-item-text` to
`.artifact-item`. The worst case is bounded: the row's text and the keyboard work.

## Checks

| Check | Head | Result |
|---|---|---|
| `openspec validate session-screen-polish --strict` | `a5104bf2` | valid |
| `openspec validate --specs --strict` | `a5104bf2` | 62 passed |
| trial archive, `openspec validate --specs --strict` | `a5104bf2` | 65 passed |
| CI of the pull request | `a5104bf2` | 23 of 23 |
| `make lint` | `a5104bf2` | clean |
| `make test` | `a5104bf2` | 4824 passed, 7 skipped |
| `make web` | `a5104bf2` | 69 files, 1520 passed |
| `uv run pytest -m ui` on the 3 files with changed tests | `a5104bf2` | 55 passed |

The other UI files ran at this head only in CI and in the developer's run (194 passed). The
integration and smoke tests ran only in CI. The live tests were not run: `providers/`, `hooks.py`,
`mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not change; on the server only
`models.py` and `launch.py` did, for `flows`.

Flakes: none in the reviewer's runs.

## Metrics

Rounds: 2 local, 1 external, 0 stand-in. Local: 4 confirmed, 6 refuted. External: 2 confirmed, 1
refuted, 1 unverifiable. Design QA: 12 findings, 7 fixed, 5 declined by the human. Findings in code
changed by the developer's cleanup: 0.

## What was not checked

- E1 in Safari and Firefox: every UI test runs in Chromium alone.
- A live screen reader and a real touch screen.
- `.title-edit .field-problem` in a row of the session list and `<span class="field-problem">` at
  `Notifications.tsx:90` were not seen in a browser.
- The long-data tests run at 390 and 1000 px, not at all four widths.
- The reviewer did not open the mockup, the retaken `screens-groups` and `screen-long-run-390`, nor
  `screens-no-runs`, `screens-no-artifacts`, `screen-take-control`, `screen-notice-warning-dark`;
  the check against the mockup is in Design QA's critique.
- Design QA was not repeated: the reviewer checked its fixes, as the human asked.

Deviations taken with the decisions: a run that ends while the tab is open stays in place and open
until the next visit, and the same holds for a session that crosses 100 artifacts; the Scope select
is held to 160 px, so a long run's name is cut while it is closed.

## Found on the way

Nothing outside the task.
