# Small fixes of the session's screen Implementation Plan

**Goal:** a session of 115 artifacts reads on a screen, and the panel, the empty tabs, the runs, the
Stop popover and the notices say what they mean once.

**Architecture:** the web UI, plus one field on the session's about. `ArtifactsTable` picks a table
or a list by its width and groups both through one pure function; each other finding is a local edit.

**Tech Stack:** React, TypeScript, CSS, vitest, Python, pytest with Playwright.

**Spec:** `openspec/changes/session-screen-polish/` (AC-1..AC-16, D1-D18),
`docs/superpowers/specs/2026-11-06-session-screen-polish-design.md`, run artifact
`mockup-session-tweaks.html`.

## Global Constraints

- Build in the order below, one commit or more per task: F20 first.
- UI texts word for word, from the design doc's table.
- Colours by tokens only.
- Do not touch F6 (it matches), LAD-216 or LAD-190.
- CHANGELOG.md: items under `## 0.45.0 (unreleased)`, `### Improved`, by docs/release.md's rules.
- `make web-types` after the model change; commit both generated files.
- UI tests with `-m ui`; suites with `-n auto`.
- No session of a working stand is touched. A screenshot attached to the tracker is public: sample
  data only.

## Tests per requirement

| Requirement | Unit | UI e2e |
|---|---|---|
| artifacts-list: two lines | `ArtifactsTable.test.tsx`: words, table from 720 | `test_artifacts_tab.py`: 436 px column, row height 44-52 |
| artifacts-list: tooltip | `ArtifactsTable.test.tsx` | focus returns after Esc |
| artifacts-list: groups | `artifacts.test.ts`: `groupByScope`; `ArtifactsTable.test.tsx`: 99, 100, filter, one scope | 115 artifacts: groups in order |
| artifacts-list: folds | `prefs.test.ts`; `ArtifactsTable.test.tsx`: defaults, search, Enter | reload keeps a fold; keyboard opens |
| artifacts-list: empty | `ArtifactsTable.test.tsx` | not needed |
| flows-overview: empty | `Flows.test.tsx`: `flowsLine` cases, ended runs | not needed |
| flows-overview: about | `tests/test_server_session.py`: valid, not found | not needed |
| flows-overview: task | `Flows.test.tsx`: card, row, blank | not needed |
| flows-overview: event | `Flows.test.tsx` | not needed |
| artifact-panel: one row | `ArtifactPanel.test.tsx`: label by tab | not needed |
| artifact-panel: phone's menu | `ArtifactPanel.test.tsx`: items, `other`, Esc | `test_artifacts_tab.py` at 390 |
| artifact-panel: title, pill | `ArtifactView.test.tsx`, `artifacts.test.ts`: `sameHeading` | not needed |
| session-forget | `Launch.test.tsx`: open runs, loading | `test_launch.py` if it presses the button that is off |
| notices, launch-notes | `tokens.test.ts`: the pairs in both themes | computed ground on `.problem` and Share; the selected row's stripe |
| session-layout: scrim | not possible in jsdom | `test_terminal_panel.py`: computed `::backdrop` |

The behaviour crosses no process, so no integration test is added; the UI tests reach a real server.
Regression run: `make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_artifacts_tab.py
tests/ui/test_terminal_panel.py tests/ui/test_launch.py tests/ui/test_main_screen.py
tests/ui/test_connection.py`; CI runs the rest (`make check` in full).

## Tasks

The steps with their checks are in `openspec/changes/session-screen-polish/tasks.md`.

1. **F20.** `artifacts.ts` helpers, `prefs.ts`, `ArtifactItem`, the groups in both views, the CSS.
2. **F21.** `sameHeading`, the read lifted, the pill, Full page, the phone's menu.
3. **F22.** `.empty` parts, the Artifacts text, `SessionKitInfo.flows`, the Flows state.
4. **F23, F24.** `run-task`, the facts' column out.
5. **F27, F26.** Stop's button and line; the backdrop.
6. **F13.** The notices' rule; the stripes out.
7. **Close.** `docs/design/ui.md`, CHANGELOG.md, screenshots at four widths and two themes, the
   tracker's note on F6 and F26.
