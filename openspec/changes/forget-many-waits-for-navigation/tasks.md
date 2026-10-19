## 1. The test

- [x] 1.1 `web/src/ForgetMany.test.tsx`, "when the session open in the page is forgotten,
  the page goes to /sessions": replace `expect(screen.getByText("No session open")).toBeTruthy();`
  with `expect(await screen.findByText("No session open")).toBeTruthy();`, and add a
  one-line comment that React Router applies the navigation in a transition, a render
  after Close (AC-1).
- [x] 1.2 At the human's word at design_ok: the same replacement in "the sessions are
  forgotten one at a time in the list's order, each reported, and Esc waits", after
  `onClose` is called (AC-1).

## 2. Checks

- [x] 2.1 By hand, not committed: turn the test into
  `test.each(Array.from({ length: 1000 }, (_, i) => i))("… %i", …)`, load the CPU (e.g.
  eight `yes > /dev/null` processes), run
  `npx vitest run src/ForgetMany.test.tsx -t "goes to /sessions"` from `web/`; all 1000
  pass; restore the file and kill the load. Optionally first show the same run on the
  code before 1.1 fails at least once in 300 (AC-2).
- [ ] 2.2 `make web` passes; CI is green on the pull request's last commit (AC-3).
