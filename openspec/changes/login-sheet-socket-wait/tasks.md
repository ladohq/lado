## 1. The race shown

- [ ] 1.1 By hand, before the fix: in `web/src/LoginWindow.tsx` wrap `socket.start()` of the
  terminal's effect in `setTimeout(..., 50)` (and clear it in the cleanup); run
  `npx vitest run src/LoginSheet.test.tsx` from `web/`: the OpenCode test fails on
  `lastSocket().url` (`Cannot read properties of undefined`) (AC-2). Keep the probe
  uncommitted; quote the failure in the build report.

## 2. The fix

- [ ] 2.1 `web/src/fakes.ts`: `export async function socketMade(n: number)` that awaits
  `waitFor(() => expect(FakeSocket.all).toHaveLength(n))` (Testing Library's `waitFor`,
  Vitest's `expect`) and returns `FakeSocket.all[n - 1]`; a one-line comment says why (the
  login window makes its socket in an effect, after it is in the page) (AC-1).
- [ ] 2.2 `web/src/LoginSheet.test.tsx`: the OpenCode test ("OpenCode's sheet opens its own
  login window at once…") takes `const first = await socketMade(1)` after
  `findByLabelText("Text to send")` and checks `first.url`; its second socket is
  `await socketMade(2)` in place of the `waitFor` on two sockets and `lastSocket()`. The
  three Codex tests' `await waitFor(() => expect(FakeSocket.all).toHaveLength(1))` (and the
  sign-in code test's wait for two) followed by `lastSocket()` become `await socketMade(n)`.
  Drop imports that fall unused; every assertion stays (AC-1).
- [ ] 2.3 The probe of 1.1 again with the fix: the file passes; then undo the probe and check
  `git diff web/src/LoginWindow.tsx` is empty (AC-2).

## 3. Checks

- [ ] 3.1 `npx vitest run src/LoginSheet.test.tsx` from `web/` 20 times in a row, each exit
  status read (not piped); then 5 times while the full Vitest suite runs in parallel, as
  load (AC-3).
- [ ] 3.2 BACKLOG.md: remove the entry "Flaky: an OpenCode test of `LoginSheet.test.tsx` in a
  full vitest run".
- [ ] 3.3 `make web` and `make lint` pass; the build report gives the counts (AC-4).
