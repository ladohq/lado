## Context

`ArtifactPanel.tsx` draws the panel: its edge (`Splitter`), a top bar `.panel-top` with
"Open in Artifacts tab" (a `Link` to `paths.artifactPath`), Expand (`panel-expand`, not
when `narrow`) and × (`panel-close`), then `.panel-body` with `ArtifactView`.
`ArtifactView.tsx` is the one viewer of the panel and of the artifact's page
(`ArtifactsTable.tsx`): its `<header className="artifact-head">` starts with
`.artifact-line`, the name (`KindIcon`, `FullName`) and `.artifact-actions` (Open in new
tab, Download, `CopyButton` Copy link). The panel's width is `width` (its stored width
fitted to the room, or the room when expanded); `narrow` (room < 400 px) shows it on the
whole screen with no inline width.

Options (mockup `mockup-panel-buttons.html`): 1, every button in the top bar with labels,
icons under 560 px (chosen by the human); 2, the same bar with icons only; 3, no bar, all
buttons in a sticky name line. Held against ROADMAP.md: the desktop stage runs the same UI;
nothing in the coming stages touches the panel's head. Design principles: one source of
truth (the actions stay one component for the page and the panel), only what is used (no
new option beyond where the actions show), neutral core (UI only, no provider).

## Decisions

- **D1. The actions are one component, `ArtifactActions`.** `ArtifactView.tsx` exports
  `ArtifactActions({ session, artifact, record, compact })`: Open in new tab (its address
  as now: the content address for HTML, `viewPath` else, none for `other`), Download and
  Copy link (its link as now). `ArtifactView` takes `actions?: boolean` (default true): the
  page passes nothing and shows them in the name line as now; the panel passes `false` and
  renders `ArtifactActions` in `.panel-top` after its Open in Artifacts tab. Why: one place
  computes the addresses; the page does not change.
- **D2. Compact by the panel's width, in JavaScript.** `ArtifactPanel` computes
  `compact = (narrow ? window width : width) < COMPACT_BELOW` (560) from what it already
  holds (`room` + ROOM_GAP is the window's width) and passes it to `ArtifactActions` and to
  its own Open in Artifacts tab. Compact: each action is an `icon-button` (28 px) with its
  icon, `aria-label` its name, wrapped in the UI's `Tooltip` with the name; not compact: a
  `quiet` button with icon and label and no tooltip. Copy link is an icon button with its
  tooltip either way, as now. Why not a CSS container query: the tooltip must exist only
  when the label is hidden, and vitest sees props, not layout.
- **D3. Open in Artifacts tab's icon is `ArtifactsIcon`**, the Artifacts tab's own, so the
  link looks like the tab it leads to. No new icon.
- **D4. The bar's order and look**: `.panel-top` holds a group `.panel-actions` (Open in
  Artifacts tab, then `ArtifactActions`; gap 6 px, no wrap) and Expand and × pushed right
  (`.panel-expand { margin-left: auto }` as now; × alone when there is no Expand). The bar
  never wraps: at 400 px compact it needs 4×28 + 2×28 px and gaps, well within the bar.
  `.artifact-actions` in the bar drops its `margin-left: auto`.
- **D5. While loading or failed**, no artifact is known: the bar holds Expand and × only,
  as now; the actions come with the record.
- **D6. Tests**: vitest for where the buttons are and when they are compact (the lowest
  layer that sees it: `ArtifactPanel.test.tsx`, `ArtifactView.test.tsx`); one UI e2e test
  that the bar's buttons share one row at a 1280 px and a 390 px window (layout needs a
  browser), with screenshots; the existing e2e tests of the buttons find them by role and
  name, which do not change.
