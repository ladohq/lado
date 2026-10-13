# LAD-43 artifact-panel-one-row: review report

Pull request #20 `fix/lad-43-artifact-panel-buttons` → `main`. Scale: tweak, review depth:
precision. Head reviewed last: `077e8d4`; the archive commit follows it. The web UI only:
the artifact panel's top bar holds every button (Open in Artifacts tab, Open in new tab,
Download, Copy link, Expand, ×), the actions as icon buttons with tooltips under 560 px;
the viewer's actions became one component, `ArtifactActions`. No core, API, schema, MCP or
provider change. The human chose option 1 of `mockup-panel-buttons.html`.

## Rounds

- **Round 1** (`origin/main..077e8d4`): local precision pass (the diff by hand, against the
  spec, tasks and design D1–D6, the screenshots against docs/design/ui.md and option 1,
  the architecture against AGENTS.md); then external round 1 by the Claude Code Action
  (request 13:53:13 UTC, "Claude finished" 13:54:12 UTC). No blocker.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local: layout | The labelled bar may not fit at exactly 560 px (`COMPACT_BELOW`) and overflow (nowrap) | refuted | — | measured in Chromium with the built CSS: 8 px to spare at 560 px, the bar's scrollWidth equals its clientWidth |
| F2 | 1 | local: docs | docs/design/ui.md, "The viewer" (lines 1711–1713): the sentence lists "its actions (`ArtifactActions` …)" and then Download, Copy link, Open in new tab as separate items | confirmed | minor | declined at convergence: wording only, left to the human at the merge gate (approved as it is) |
| F3 | 1 | external (Action) | Little room in the bar at 560 px: text zoom, a fallback or a large system font could push Expand and × out | refuted but one case | — | page zoom changes the window's CSS width and `useRoom` computes `compact` again; the bar's font is 13 px and Inter ships in the bundle. Left: a browser minimum font size above 13 px (residual risk) |
| F4 | 1 | external (Action) | The e2e test checks the exact order of the bar's links and buttons: brittle | refuted | — | the order is acceptance criterion AC-1; the test must fail when it changes |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 1 (F2) | 1 (F1) | — |
| external, Claude Code Action | 0 | 2 (F3, F4) | — |

No blocker and no important finding.

## Found on the way

None new: the Codex smoke on macOS failed once more on its known flake (BACKLOG.md, run
38408163443) and passed on a rerun.

## Checks

- Local at `077e8d4`: `make lint` clean; `make web` 700 tests passed (tsc, stale-types,
  build); UI e2e `tests/ui/test_artifacts_tab.py` 19 passed, the new 1280/390 px test
  included; `openspec validate artifact-panel-one-row --strict` and `openspec validate
  --specs --strict` valid.
- CI of PR #20 on `077e8d4` green: check (3.10, 3.13), js, ui, smoke ubuntu/macos for
  every provider (the Codex smoke on macOS after one rerun).
- Not run locally: `make test` (no Python changed; CI green). Live tests not needed: no
  change to `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
  `tests/live/`.

## Design decisions left as they are

- The artifact's page in the Artifacts tab still wraps its buttons under the name on a
  narrow window: out of scope by the approved design.
- Compact by the panel's width in JavaScript, not a CSS container query (D2).

## Residual risk

- A browser minimum font size above 13 px may widen the labelled bar of a panel near
  560–600 px past its edge; not reproduced.
- F2 as wording.

## Result

Converged after round 1 (1 of 1 external rounds).
