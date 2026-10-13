## 1. The card expands in its page

- [ ] 1.1 `web/src/WaitingCard.tsx`: no `createPortal` and no `.waiting-overlay`; the
  section gets `.expanded` in place, without `role="dialog"` and `aria-modal`; the expand
  button gets `aria-expanded`; the focus moves as now (design.md, D1, D2). The file's
  comment says the card expands within its page. Check: `make web`.
- [ ] 1.2 `web/src/WaitingCard.tsx`: the Esc listener does nothing while the address has
  `view` (`useSearchParams`), so the panel's own Esc closes it first (D3). Check: 2.1.
- [ ] 1.3 `web/src/styles.css`: remove `.waiting-overlay`; `.chat:has(> .waiting-card.expanded)`
  hides `.chat-feed` and `.composer`, the expanded card `flex: 1`, no max height or width,
  no centring margin; `.needs-you:has(.waiting-card.expanded)` hides the sessions without
  the expanded card and the `.waits-item` rows, the expanded one filling the content's
  height; at 900 px or less the expanded card's `min-height` is the window less the top
  bar and it scrolls into view under the sticky top bar (D1, D5). Check: the mockup's
  screens 3, 4 and 7, light and dark.

## 2. The panel over Needs you

- [ ] 2.1 `web/src/paths.ts`: `VIEW_SESSION_PARAM = "session"` with its comment;
  `web/src/Attachments.tsx` `useView`: on the session's page as now, on `/needs-you` set
  `view` and `session` (a history step), elsewhere navigate as now;
  `web/src/NeedsYou.tsx` renders `ArtifactPanel` when both are in the address;
  `web/src/ArtifactPanel.tsx` close deletes both (D4). Check: `make web`.

## 3. Tests

- [ ] 3.1 `web/src/WaitingCard.test.tsx`: the expanded card is in place (no dialog role,
  no `.waiting-overlay`, the expand button `aria-expanded="true"`); with `?view=` in the
  address Esc leaves it expanded, without it Esc folds it (AC-1, AC-2, AC-5); the tests
  that looked for the dialog now look for the region by its name. Check: `make web`.
- [ ] 3.2 `web/src/NeedsYou.test.tsx`: a chip click sets `view` and `session` and stays on
  `/needs-you`; the panel renders; × clears both and the card keeps its pick (AC-4).
  `web/src/ArtifactPanel.test.tsx`: close removes `session` too. Check: `make web`.
- [ ] 3.3 `tests/ui/test_chat.py`: the expand test asserts the card's box lies inside the
  chat's (not the window's), the session tabs are visible and clickable and no scrim;
  a new test with a question that carries an artifact: expand, click its chip, the panel
  is visible and on top (`elementFromPoint` at the panel's centre is inside the panel),
  Esc closes it and the card stays expanded, Esc folds it (AC-1, AC-2), screenshots light
  and dark. Check: `uv run pytest -m ui tests/ui/test_chat.py`.
- [ ] 3.4 A UI test of Needs you (`tests/ui/`, the file that tests Needs you, else a new
  `test_needs_you.py`): two sessions waiting, expand one (the other hidden, AC-3), click
  its chip: the panel is on top over `/needs-you`, Back closes it and the card stays
  expanded with its pick (AC-4); a window of 390 px: the expanded card is the window's
  height under the top bar (AC-5); screenshots. Check: `uv run pytest -m ui <file>`.

## 4. Docs

- [ ] 4.1 docs/design/ui.md: The waiting card, Height: expanded within its page (the chat's
  area, Needs you's content area), no scrim, not a dialog, Esc closes an open panel first
  (decided 2026-10-13, LAD-48, mockup `task/lad-48/mockup-expanded-card.html`, option A);
  Needs you: a chip opens the panel over the page; Artifacts, The panel: "from Needs you,
  over the session's Activity tab" becomes over Needs you (`?view=&session=`).
- [ ] 4.2 CHANGELOG.md: `## 0.37.1 (unreleased)` on top with a line: the expanded waiting
  card covers the chat (on Needs you the page) instead of the whole window, so an artifact
  opened from it is seen; on Needs you an artifact opens over the page.
- [ ] 4.3 `openspec validate waiting-card-expands-in-page --strict`, `make lint`,
  `make test` and `make web` pass.
