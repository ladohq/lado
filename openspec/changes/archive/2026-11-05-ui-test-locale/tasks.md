## 1. The failing test

- [x] 1.1 `web/src/testLocale.test.ts` (unit, vitest; design D2). Fails before 2.1. Run:
  `cd web && npx vitest run src/testLocale.test.ts`.

## 2. The fix

- [x] 2.1 `web/vite.config.ts`: `test.env` (design D1). 1.1 passes.
- [x] 2.2 `cd web && LC_ALL=ru_RU.UTF-8 npx vitest run` exits 0, and so does it with
  `LANG=ru_RU.UTF-8` alone; say so in `build-report`.
- [x] 2.3 The same with the commit on top of `origin/epic/lad-154-models` in a temporary copy
  outside the tree: the two Model tests pass there; say so in `build-report`.
- [x] 2.4 `make lint`, `make web` green.

## 3. Docs

- [x] 3.1 `docs/testing.md`: the web UI's unit tests run in en-US whatever the machine's
  locale, and why.
- [x] 3.2 `BACKLOG.md`: the entry "UI unit tests depend on the process's locale and nothing
  guards it" goes.
- [x] 3.3 `openspec validate ui-test-locale --strict` passes.
