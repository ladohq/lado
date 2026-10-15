## 1. The listener

- [x] 1.1 `web/src/Launch.test.tsx`, the case "a window whose page goes away during a
  clone cancels it at once with a beacon": besides its present checks, a
  `MutationObserver` on `document.body` dispatches `pagehide` once at the first DOM change
  that shows the button Cancel clone, and once at the first change that shows the session
  region "Session marketplace"; the case then expects the beacon called with
  `/api/clones/j1/cancel` once from the first and no new call from the second (the
  present `pagehide` after `findByRole` and the final `toHaveBeenCalledTimes` adjusted to
  the count). No `waitFor` around a beacon check. Check: on the code before 1.2 the case
  fails (the beacon not called at the Cancel clone change); its output goes to the build
  report (AC-1, AC-2, AC-3).
- [x] 1.2 `web/src/Launch.tsx`, `LaunchDialog`: the effect keyed by `runningId` that adds
  and removes the `pagehide` listener becomes `useLayoutEffect` (import it); its comment
  says why: the listener must exist in the commit that shows the clone running and be gone
  in the one that shows its end, as a passive effect runs a task later. Check: the case
  of 1.1 passes; then 200 runs of it, eight at a time
  (`npx vitest run src/Launch.test.tsx -t "page goes away"`, each run's exit status
  kept), all pass, the count in the build report (AC-1, AC-2, AC-3).

## 2. Changelog

- [x] 2.1 `CHANGELOG.md` under `## 0.40.0 (unreleased)`: a line: a tab of the web UI
  closed or reloaded the very moment its clone shows running now cancels the clone at
  once too (before, the server cancelled it only after 150 s).

## 3. Regression

- [x] 3.1 `make web` (typecheck, the whole vitest suite, build; no API change),
  `openspec validate clone-beacon-at-once --strict`; the pull request's CI `ci-ok` green
  (AC-4).
