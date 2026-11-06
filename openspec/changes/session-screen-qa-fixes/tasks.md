## 1. The focus (F46)

- [x] 1.1 `web/src/modal.ts`: `useModal` (D1). Check: `modal.test.ts`; AC-1.
- [x] 1.2 All 13 `showModal` calls go through `useModal`; the guard test. Check: `npm test`; AC-2.
- [x] 1.3 `Tooltip` stays silent on a focus given back (D2): no code, React drops the event during
  its commit; held by `tests/ui/test_layout.py`, not by `Tooltip.test.tsx`; AC-3.
- [x] 1.4 UI tests for Take control, Resume and the other windows. Check: `uv run pytest -m ui
  tests/ui/test_terminal_panel.py tests/ui/test_stopped_session.py tests/ui/test_layout.py`; AC-1, AC-2.

## 2. The toggle sideways (F47)

- [x] 2.1 `Session`, `Activity`, the CSS (D3). Check: `tests/ui/test_phone.py`, 844×390 and 568×320
  with touch, a running session and a stopped one with an empty feed; AC-4.

## 3. Notices (F48, F49)

- [x] 3.1 `.kit-alert` to `.kit-warning` (D4). Check: `tests/ui/test_kits_page.py`, in the live
  window, computed ground and a screenshot; AC-5.
- [x] 3.2 A failed login (D4). Check: `tests/ui/test_providers_section.py`, in the live window,
  computed ground, no left border on the quote, a screenshot; AC-6.

## 4. The run's task (F50)

- [x] 4.1 `taskTip`, `ListEntry.tip`, the measure (D5). Check: `Flows.test.tsx`,
  `tests/ui/test_flows_tab.py`; AC-7.
- [x] 4.2 The line stays `--muted` (D6). Check: `tests/ui/test_flows_tab.py`; AC-8.

## 5. Session first (F51)

- [x] 5.1 The order (D7). Check: `ArtifactsTable.test.tsx`, `tests/ui/test_artifacts_tab.py` with 100+
  artifacts; AC-9.

## 6. Console errors

- [ ] 6.1 Collect and sort them in `build-report` (D8); fix those of this change. Check: the list in
  `build-report`; AC-10.

## 7. Documents

- [x] 7.1 `docs/design/ui.md`: Take control (line 382) and a general line on windows and the focus;
  the toggle sideways in Phone layout; a kit's warning and the failed login; the run's tooltip and
  muted line in Flows; Session first in Artifacts. Check: read against the code.
- [x] 7.2 CHANGELOG.md, `## 0.45.0 (unreleased)`, under Fixed: the focus, the toggle sideways;
  under Improved: the notices, the task's tooltip, Session first, as edits of the items of the same
  features (`docs/release.md`, "One change, one item"). Check: `docs/release.md`'s rules.
- [ ] 7.3 `make lint`, `make test`, `make web`, the changed UI files with `-m ui`; `make check` as a
  whole is proved by CI (`.lado/sdlc.md`, Checks). Screenshots of each changed screen in the pull
  request and the run's artifacts.
