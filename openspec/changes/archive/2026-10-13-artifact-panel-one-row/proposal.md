Task: LAD-43

## Why

The artifact panel (a chip or a row of the Artifacts tab opens it on the right over the
page) shows its buttons in two rows: its top bar holds "Open in Artifacts tab", Expand
and ×, and under it the viewer's name line holds Open in new tab, Download and Copy link.
At the panel's least width, 400 px, the second group also wraps under the artifact's
name, so the head takes three rows before the title.

The root cause is that two components draw the buttons: `ArtifactPanel.tsx` draws the top
bar, and `ArtifactView.tsx`, the one viewer of the panel and of the artifact's page in the
Artifacts tab, draws its own actions in its name line. The page has no top bar, so the
viewer keeps them there for it; the panel adds its bar on top.

## What Changes

- **UI, the panel** (`web/src/ArtifactPanel.tsx`): one top bar holds every button: on the
  left Open in Artifacts tab, Open in new tab (not for a type the browser cannot show, as
  now), Download and Copy link; on the right Expand (not on a narrow window, as now) and
  ×. The viewer's name line in the panel holds only the type's icon and the full name.
  Approved mockup `mockup-panel-buttons.html`, option 1.
- When the panel is narrower than 560 px (its width, or the window's when it takes the
  whole screen), the four action buttons lose their visible labels and become icon
  buttons with the UI's tooltip; their accessible names stay "Open in Artifacts tab",
  "Open in new tab", "Download" and "Copy link".
- Open in Artifacts tab gets an icon, the Artifacts tab's own (`ArtifactsIcon`).
- **UI, the viewer** (`web/src/ArtifactView.tsx`): its actions become one component,
  `ArtifactActions`, which the page shows in the name line as now and the panel shows in
  its bar; the viewer takes whether to show them.
- Unchanged: the artifact's page in the Artifacts tab ("← Artifacts", the actions in the
  name line, wrapping on a narrow window), what each button does, the panel's width,
  edge, Expand and Esc.
- docs/design/ui.md, Artifacts, "The viewer" and "The panel": where the buttons are.
- CHANGELOG.md: one line under `## 0.37.0 (unreleased)`.

## Scope

The artifact panel's head in the web UI. Nothing in the core, the API, the MCP tools or the
schema.

## Out of scope

- Option 2, icon buttons only at every width: the labels would never show where there is
  room for them (the human's decision).
- Option 3, no top bar, every button in the name line kept in place: a long name is cut
  with an ellipsis, and the head is rebuilt the most (the human's decision).
- The artifact's page in the Artifacts tab, whose buttons wrap under the name on a narrow
  window: it has no bar to gather them in, and the task is about the panel (the analyst's
  recommendation, left to the human at design_ok).

## Acceptance criteria

- AC-1: In a panel 560 px wide or wider, Open in Artifacts tab, Open in new tab, Download,
  Copy link, Expand and × are in the panel's top bar, in that order, in one row, the four
  actions with their labels; the name line under it has no button.
- AC-2: In a panel narrower than 560 px (400 px, and a phone's full-screen panel), the same
  buttons are in one row of the top bar, the four actions as icon buttons with no visible
  label, each with the UI's tooltip and its accessible name as in AC-1.
- AC-3: For a type the browser cannot show, the bar has no Open in new tab; while the
  record loads or fails, the bar holds only Expand and ×, as now.
- AC-4: Each button does what it did: the Artifacts tab's page of the record, the record
  alone in a new tab, the download, the copied link (its field to copy by hand stays
  inside the window).
- AC-5: The artifact's page in the Artifacts tab shows its buttons in the name line as now.
- AC-6: docs/design/ui.md and CHANGELOG.md say so; vitest and the UI e2e tests check
  AC-1 to AC-5 and pass.

## Impact

- `web/src/ArtifactPanel.tsx`, `web/src/ArtifactView.tsx`, `web/src/styles.css`,
  `web/src/ArtifactPanel.test.tsx`, `web/src/ArtifactView.test.tsx`,
  `tests/ui/test_artifacts_tab.py`, `docs/design/ui.md`, CHANGELOG.md.
- No API, schema or MCP change: a fix (a patch alone; 0.37.0 is already the next version).

## Decisions for the record

- Scale tweak: one head's layout, its shape known; review as a tweak.
- A new capability `artifact-panel` in openspec: no living spec covers the artifacts UI
  yet, and where the panel's buttons are is behaviour a user sees.
- The labels go by the panel's width in JavaScript, not a CSS container query: the panel
  already knows its width, the tooltip must be there only when the label is not, and
  vitest can check it (design.md, D2).
