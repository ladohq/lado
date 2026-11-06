## 1. F20: the list and the groups

- [x] 1.1 `KINDS` with row words, `groupByScope`, `GROUPS_FROM` in `artifacts.ts` (D2, D6).
  Check: `artifacts.test.ts`.
- [x] 1.2 `storedArtifactGroups`, `storeArtifactGroups` in `prefs.ts` (D3). Check: `prefs.test.ts`.
- [x] 1.3 `ArtifactItem`, the width picks list or table, the stacked-cells CSS out (D1, D5).
  Check: `ArtifactsTable.test.tsx`, `tests/ui/test_artifacts_tab.py`; AC-1, AC-2.
- [x] 1.4 Groups in the list and the table, folds, the `runs` watch (D3, D4).
  Check: `ArtifactsTable.test.tsx`, `tests/ui/test_artifacts_tab.py` with 115 artifacts; AC-3..AC-5.

## 2. F21: the panel

- [ ] 2.1 `sameHeading`, the read lifted to `ArtifactView`, the title hidden (D7).
  Check: `artifacts.test.ts`, `ArtifactView.test.tsx`; AC-6.
- [ ] 2.2 The pill (D10). Check: `ArtifactView.test.tsx`; AC-7.
- [ ] 2.3 Full page over the Artifacts tab (D8). Check: `ArtifactPanel.test.tsx`; AC-8.
- [ ] 2.4 The phone's bar and menu (D9). Check: `ArtifactPanel.test.tsx`,
  `tests/ui/test_artifacts_tab.py` at 390; AC-9.

## 3. F22: the empty tabs

- [ ] 3.1 `.empty` parts and the Artifacts text (D11). Check: `ArtifactsTable.test.tsx`; AC-10.
- [ ] 3.2 `SessionKitInfo.flows`, `make web-types` (D12). Check: `tests/test_server_session.py`,
  `make web`.
- [ ] 3.3 `flowsLine` and the Flows state (D11). Check: `Flows.test.tsx`; AC-10.

## 4. F23, F24: runs

- [ ] 4.1 `run-task` on the card and the row (D13). Check: `Flows.test.tsx`; AC-11.
- [ ] 4.2 The facts out, "Step took" one line (D15). Check: `Flows.test.tsx`; AC-12.

## 5. F27, F26: Stop and Take control

- [ ] 5.1 Stop and forget only when offered, the new line (D16). Check: `Launch.test.tsx`; AC-14.
- [ ] 5.2 The backdrop on `--scrim` (D17). Check: `tests/ui/test_terminal_panel.py`; AC-13.

## 6. F13: notices

- [ ] 6.1 The notices' rule and icon, the stripes out, `.pv-*` and `.kit-warning` to warnings (D14).
  Check: `tokens.test.ts`, a UI test on computed styles, `tests/ui/test_launch.py` for `launch-notes`;
  AC-15.

## 7. Close

- [ ] 7.1 `docs/design/ui.md`: Artifacts (the tab, the viewer, the panel), Flows (cards, rows, the
  event, the empty tab), Stop, New session's notes (no stripe), Look's notices if named.
  Check: read against the code.
- [ ] 7.2 CHANGELOG.md under `## 0.45.0 (unreleased)`, one item per visible change.
  Check: docs/release.md's rules.
- [ ] 7.3 Screenshots of each changed screen at 390, 768, 1024 and 1440, light and dark, as run
  artifacts, with sample data. Check: no horizontal scroll of the page; AC-16.
- [ ] 7.4 The regression run of the plan. Check: all green; numbers in `build-report`.
