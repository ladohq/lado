Plan: `docs/superpowers/plans/2026-10-18-phone-layout.md` (each task's tests and steps).
Design doc: `docs/superpowers/specs/2026-10-18-phone-layout-design.md`.

## 1. The query and the hook (D1)

- [x] 1.1 `web/src/phone.ts` (`PHONE_QUERY`, `SHORT_QUERY`, `usePhone`), the Shell's
  `data-phone`; vitest. Check: `cd web && npx vitest run src/phone.test.ts`, `make web`.

## 2. The app window and the CSS section (D4)

- [ ] 2.1 `styles.css` section "Phone layout", `index.html`'s viewport, the artifact
  tab's image by `dvh`. Check: `make web`, task 8's e2e.

## 3. The menu (D2)

- [ ] 3.1 Menu, badge, the rail as a drawer, scrim, Esc, focus; vitest. Check: `cd web &&
  npx vitest run src/Shell.test.tsx`, `make web`.

## 4. The compact head and the details sheet (D3)

- [ ] 4.1 `HeadLine`'s phone branch, the live dot, `SessionDetails`; vitest. Check: `cd
  web && npx vitest run src/SessionDetails.test.tsx`, `make web`.

## 5. Sessions and the waiting card (D5, D6)

- [ ] 5.1 The list as the Sessions page, no strip; the sideways card minimized by the
  layout; vitest. Check: `cd web && npx vitest run src/WaitingCard.test.tsx`, `make web`.

## 6. Terminals over the screen (D7)

- [ ] 6.1 No panel or strip on a phone, opened expanded, Close terminal; vitest. Check:
  `cd web && npx vitest run src/Terminals.test.tsx`, `make web`.

## 7. Tooltips on a tap (D8)

- [ ] 7.1 Touch tap on a hint shows it, buttons never; vitest. Check: `cd web && npx
  vitest run src/Tooltip.test.tsx`.

## 8. UI e2e (D9)

- [ ] 8.1 `tests/ui/test_phone.py`, the plan's table of tests, with screenshots. Check:
  `uv run pytest -m ui tests/ui/test_phone.py`.

## 9. Docs

- [ ] 9.1 `docs/design/ui.md` "Phone layout", CHANGELOG.md 0.41.0, BACKLOG.md's two
  entries dropped. Check: `openspec validate --specs --strict`.

## 10. Regression

- [ ] 10.1 `make lint`, `make test`, `make web`, the UI e2e files of the plan's
  regression list, unchanged but `test_phone.py`. Check: all green.
