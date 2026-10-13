## 1. The viewer and the panel

- [ ] 1.1 `web/src/ArtifactView.tsx`: export `ArtifactActions({ session, artifact,
  record, compact })` (Open in new tab, Download, Copy link, their addresses as now;
  compact: icon buttons with `aria-label` and the UI's `Tooltip`, else icon and label);
  `ArtifactView` takes `actions?: boolean` (default true) and shows `ArtifactActions` in
  its name line only then; the file's comment says so (design.md, D1, D2). Check: the
  existing `ArtifactView.test.tsx` passes unchanged (AC-5).
- [ ] 1.2 `web/src/ArtifactPanel.tsx`: `COMPACT_BELOW = 560`; `compact` from the panel's
  width, or the window's when `narrow`; `.panel-top` holds `.panel-actions` (Open in
  Artifacts tab with `ArtifactsIcon`, compact like the others, then `ArtifactActions`),
  then Expand and ×; `ArtifactView` with `actions={false}`; nothing but Expand and × while
  loading or failed; the file's comment says so (D3, D4, D5).
- [ ] 1.3 `web/src/styles.css`: `.panel-actions` (flex, gap 6 px, no wrap), the bar's
  `quiet` links and buttons with icon and label as `.artifact-actions a.quiet` now, no
  `margin-left: auto` for the actions in the bar; remove what no element uses any more.
  Check: the mockup's option 1 at 620 and 400 px.

## 2. Tests

- [ ] 2.1 `web/src/ArtifactPanel.test.tsx`: at a 1264 px window (620 px panel) the bar
  (`.panel-top`) holds links "Open in Artifacts tab", "Open in new tab", "Download", the
  button "Copy link", "Expand", "Close" in that order and the viewer's head (`banner`)
  holds none, labels visible (AC-1); with a stored width of 400 px, and at a 390 px window
  (no Expand), the four actions are icon buttons with those accessible names and no
  label text (AC-2); an `application/octet-stream` record has no "Open in new tab" (AC-3);
  before the record comes, the bar has Expand and × only (AC-3). Check: `make web`.
- [ ] 2.2 `web/src/ArtifactView.test.tsx`: `actions={false}` shows no button in the head;
  the default keeps them (AC-5). Check: `make web`.
- [ ] 2.3 `tests/ui/test_artifacts_tab.py`: a test, parametrized by window width 1280 and
  390, that opens `ship/x/design` in the panel and asserts the bar's buttons share one row
  (their boxes' vertical centres within 2 px) and the head has no button, with a
  screenshot each (AC-1, AC-2); the existing tests of Open in Artifacts tab, Open in new
  tab and Copy link (its field inside the window) pass unchanged (AC-4). Check: `uv run
  pytest -m ui tests/ui/test_artifacts_tab.py`.

## 3. Docs

- [ ] 3.1 docs/design/ui.md, Artifacts: "The viewer" says the page shows its actions in
  the name line and the panel in its bar; "The panel" says its top bar holds Open in
  Artifacts tab, Open in new tab, Download, Copy link, Expand and ×, the actions as icons
  with tooltips under 560 px (decided 2026-10-13, LAD-43, mockup
  `mockup-panel-buttons.html`, option 1).
- [ ] 3.2 CHANGELOG.md under `## 0.37.0 (unreleased)`: the artifact panel shows all its
  buttons in one row at the top.
- [ ] 3.3 `openspec validate artifact-panel-one-row --strict`, `make lint`, `make test`
  and `make web` pass.
