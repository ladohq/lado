# LAD-92 forget-stopped-sessions: review report

Pull request #98 `feature/lad-92-forget-stopped-sessions` → `main`. Scale: full, reviewed
breadth first. Head reviewed last: `db08cc1` (= the remote head). `providers/`,
`hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not
change, so live tests are not needed before the merge.

## Rounds

- **Round 1, local** (breadth over `origin/main...1578958`; lenses spec, tests, silent
  failures, comments and docs, types and invariants, general/architecture): F1, F2. No
  external round requested, as there was something to fix.
- **Round 2, local** (precision over the delta `1578958..e59dd02`): the merge `4fdc6a1`
  changes none of the pull request's own files (the same 18 files against main, the UI
  code unchanged); both CHANGELOG entries sit under `## 0.41.0 (unreleased)`; the ui.md
  wrap is right. Nothing new.
- **Round 1, external** (Claude Code GitHub Action, request `issuecomment-6243622845`,
  answer in run 39082159183; triage `issuecomment-6243636402`): no blockers, four minor
  remarks E1–E4. The external reviewer is of the same model family and says it did not
  read the tests, `styles.css` or the docs; its "nothing blocking" weighs accordingly.
- **Round 3, local** (precision over the delta `e59dd02..db08cc1`, the return from
  `conflicts` after `merge_ok`: main had moved on with #95, #97, #99 and #100): `72d3640`
  archives the change unedited and adds the living spec `session-forget`; `db08cc1` merges
  origin/main. The pull request's own diff in `web/` and `tests/ui/` is byte for byte the
  one at `e59dd02`; against main, CHANGELOG.md only gains the six lines of this change,
  main's 0.41.0 entries kept; no conflict markers left (`git grep`). The developer removed
  the markers with a script rather than an edit tool (a named deviation); the result was
  checked. Nothing new.
- **Round 2, external** (request `issuecomment-6253765125`, answer in run 39156058745):
  nothing new; it confirmed independently that against the merge's second parent the tree
  differs only in those six CHANGELOG lines, and agreed with F1–F2 and E1–E4.

External rounds used: 2 of 2.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (checks) | the pull request conflicted with `main` (CHANGELOG.md after PR #93), so GitHub ran no CI and there was no `ci-ok` | confirmed | important | fixed in `4fdc6a1` (origin/main merged, both entries under 0.41.0); again in `db08cc1` after the return from `conflicts`; CI run 39155499929 on `db08cc1`: `ci-ok` pass |
| F2 | 1 | local (docs) | `docs/design/ui.md`: a line of ~120 characters left unwrapped in the group band's paragraph | confirmed | minor | fixed in `e59dd02` |
| E1 | ext 1 | external | the tooltip on the disabled `Stop and forget` may not show, as browsers do not always hover a disabled `<button>` | unverifiable | — | declined (residual risk): the tooltip only names the button; the visible line "It has open runs…" says why it is off |
| E2 | ext 1 | external | after the stop the head swaps Stop for Resume, the popover unmounts and the forget's refusal is lost | refuted | — | dropped: `StopPopover` is drawn by `shown === "stop"` in `SessionActions` (`web/src/SessionControl.tsx`), not by the set of actions, and `SessionActions` stays in the head across the status change |
| E3 | ext 1 | external | in the window's final view the skipped sessions vanish; suggests a line "N stayed" | refuted (as a defect) | — | dropped: by design D5 the window says only what did not go; the skipped ones are named before the press ("While this is off, … stay.") |
| E4 | ext 1 | external | Escape is handled both in `onCancel` and in `onKeyDown` | refuted (as a defect) | — | dropped: the same pattern as the single Forget's window; the two windows are built alike on purpose |

## Metrics

Rounds: 3 local, 2 external, 0 substitute. Local findings: 2 confirmed (1 important,
1 minor), 0 refuted. External: 0 confirmed, 3 refuted, 1 unverifiable. Findings in code
changed by the developer's self-cleanup: 0.

## Accepted deviations from the design

From the build report: the Stop and forget tests live in `Launch.test.tsx` instead of a
new `SessionControl.test.tsx`; the Stop popover is 440 px wide instead of 380; "stays" for
a single session; an explicit focus on Cancel after `showModal`.

## What was checked

All five requirements of the `session-forget` delta and their scenarios have code and
tests (vitest and UI e2e); every task of `tasks.md` is checked; D1–D7 are kept; the
server, API, schema and CLI did not change; the screenshots match `docs/design/ui.md` and
the mockup (variant 1). The reviewer's runs (round 1; the UI code has not changed since):
`make lint` 0; `tsc` 0; vitest ForgetMany/GroupHead/Launch 126 passed; UI e2e forget/stop
in `test_launch.py` and `test_phone.py` 8 passed; `openspec validate --specs --strict` 35
passed, the change valid. CI on `e59dd02`: unit 3.10/3.13, integration 6 shards, UI 2
shards, js, container amd64/arm64 pass. After the merge `db08cc1` (the developer): `make
web` 954 passed, `make lint` 0, `make test` 3602 passed, UI e2e 59 passed; CI run
39155499929 on `db08cc1`: `ci-ok` and every job pass; `openspec validate --specs
--strict` 39 passed, 0 failed.

## Not checked (residual risk)

- Stop and forget's path "the stop succeeded, the forget was refused" is covered only by
  vitest (where the session's status does not change); not reproduced in a browser, as a
  core refusal at that point is hard to cause. By the code the popover stays open (E2).
- E1: whether the tooltip shows on the disabled button in each browser.
- CI's smoke tests skipped by the skip-list rule (the pull request touches only `web/`,
  `tests/ui/`, docs, openspec and CHANGELOG; no Python code).
- The reviewer did not rerun the tests locally after the return (the pull request's own
  code is byte for byte the same); the developer and CI did.

## Found on the way

Nothing.
