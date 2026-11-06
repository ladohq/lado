## 1. The test

- [ ] 1.1 `web/src/Launch.test.tsx`, "Start in starts in the project's repository chosen" (unit,
  the layer of the test itself): before `fireEvent.change(providerSelect(), …)`, add
  `await waitFor(() => expect(providerSelect().disabled).toBe(false));`, with a comment on why:
  a change reaches a field that is off, and the empty value would count as the human's choice.
- [ ] 1.2 With `/api/providers` answered 150 ms late (kept out of the commit), the test passes
  20 times in a row; without the new line it fails. Say so in `build-report`.

## 2. The waits

- [ ] 2.1 `web/vite.config.ts`: `testTimeout: 30_000` under `test`, with a comment on why.
- [ ] 2.2 `web/src/testSetup.ts`: `configure({ asyncUtilTimeout: 10_000 })` from
  `@testing-library/react`, with a comment on why.
- [ ] 2.3 The `{ timeout: 3000 }` of `web/src/Launch.test.tsx` (7) and
  `web/src/ProjectRepos.test.tsx` (5) are gone. `grep -rn 'timeout: 3000' web/src` finds nothing.
- [ ] 2.4 `docs/testing.md`, the Unit layer: one sentence on the two settings and on why a test
  sets no timeout of its own.

## 3. The backlog

- [ ] 3.1 `BACKLOG.md`: the entries "Vitest tests time out at vitest's default 5 s under load, one
  entry per test" and "Flaky vitest: Launch's taken name of a running session" are gone, and the
  entries around them are untouched. `grep -c "Vitest tests time out\|Launch's taken name"
  BACKLOG.md` says 0.

## 4. The checks

- [ ] 4.1 `make lint` and `make web` green; report the tests as numbers.
- [ ] 4.2 `web/src/Launch.test.tsx` passes 5 times in a row beside a load of the machine (e.g. a
  second full `npx vitest run`); say so in `build-report`.
- [ ] 4.3 `openspec validate launch-test-waits-for-providers --strict`, and the trial archive with
  `--skip-specs`.
