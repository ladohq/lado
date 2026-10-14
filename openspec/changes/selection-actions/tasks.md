Plan: `docs/superpowers/plans/2026-10-15-selection-actions.md` (each task's tests and steps).
Design doc: `docs/superpowers/specs/2026-10-15-selection-actions-design.md`.

## 1. The quote's text (D3)

- [x] 1.1 `web/src/quote.ts`: `blockquote`, `fenced`, `artifactLead`, `withQuote`. Check:
  `cd web && npx vitest run src/quote.test.ts`.

## 2. Composers take a quote (D4)

- [x] 2.1 `web/src/quotes.ts`, `Composer` registers and takes a pending quote, the waiting
  card folds on a quote. Check: `cd web && npx vitest run src/quotes.test.ts
  src/Composer.test.tsx`, `make web`.

## 3. Icons and readable areas (D1, D6)

- [x] 3.1 `CopyIcon`, `QuoteIcon`; `data-quote*` and `data-line` on the areas of the design
  doc's table. Check: `cd web && npx vitest run src/Chat.test.tsx src/ArtifactView.test.tsx`,
  `make web`.

## 4. The selection bar (D1, D2, D8)

- [x] 4.1 `SelectionBar.tsx` in the shell, its styles; vitest of `areaOf`/`quoteOf`; UI
  e2e `tests/ui/test_selection.py` with screenshots. Check: `make web`, `uv run pytest -m ui
  tests/ui/test_selection.py`.

## 5. Copy code and Copy message (D5, D7)

- [x] 5.1 `pre` override, `FeedRow`'s `copy`, `messageText`, the hover CSS; vitest; e2e of
  hover and touch. Check: `make web`, `uv run pytest -m ui tests/ui/test_selection.py
  tests/ui/test_chat.py tests/ui/test_artifacts_tab.py`.

## 6. Docs

- [x] 6.1 `docs/design/ui.md` section "Selected text and copy buttons", CHANGELOG.md under
  0.39.0. Check: `openspec validate --specs --strict`.

## 7. Regression

- [x] 7.1 `make lint`, `make test`, `make web`, the UI e2e files of the plan's regression
  run.
