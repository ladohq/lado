# LAD-54 waiting-card-minimize-resize: review report

Pull request #46 `fix/lad-54-fold-waiting-card` → `main`. Scale: tweak, reviewed for
precision, at most one external round. Head reviewed last: `c9e570a` (= the remote head);
the archive commit follows it. Only the web UI changed: `providers/`, `hooks.py`,
`mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not, so live tests are
not needed before the merge.

## Rounds

- **Round 1, local** (precision and the spec over `origin/main...f801fd4`): F1, F2, F3.
- **Round 2, local** (precision over the delta `5fed058`…`3da532c` and the merges of
  main): no new findings.
- **Round 1, external** (Claude Code GitHub Action, request 06:57:08Z, answer 06:58:16Z):
  F4, F5, F6 (refuted), F7 (= F3). At the gate `merge_ok` the human sent F4 back to be
  fixed.
- **Round 3, local** (precision over `cf6cfdc..c9e570a`, one commit: the fix of F4 and
  two tests): no new findings. No second external round: a tweak has one, and the delta
  is one line that closes the external reviewer's own finding. The external reviewer is
  of the same model family, so its "nothing blocking" weighs less.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (spec) | the minimized card's stored tab keys were cleared only on restore, so an agent whose tab had gone and who asked again did not restore the card (against the proposal) | confirmed | important | fixed in `5fed058`, `d99fdeb`: once questions and gates are loaded the keys narrow to the current tabs and go with no tabs left; vitest in `WaitingCard.test.tsx`, `Chat.test.tsx` |
| F2 | 1 | local (checks) | the pull request conflicted with `main`, so CI had not run | confirmed | blocker (for the merge) | fixed by merging main (`aa77088`, `cf6cfdc`); CI green on `c9e570a` |
| F3 | 1 | local | the top edge reports `aria-valuemin=0` while the card's least height is 166 px | confirmed | minor | declined: the range below the least height is "minimize" (AC-6); the external reviewer agreed |
| F4 | ext 1 | external | `preventDefault()` on the splitter's `pointerdown` (`3da532c`) cancelled the focus a click gives, so the arrow keys did not work after a click on any edge | confirmed (Playwright probe, Chromium and WebKit) | minor | fixed in `c9e570a` at the human's word: `separator.focus()` in `drag`; vitest in `Splitter.test.tsx` and the e2e edge test now clicks the edge first, both seen red |
| F5 | ext 1 | external | `minimize()` at the drag's end reads the `tabs` of the render the press began in; a gate opening mid-drag is not in the stored keys | confirmed | minor | declined: the card then restores at once (a new tab restores it), which is safe |
| F6 | ext 1 | external | the room for the card ignores `.chat`'s gap and the splitter's margins | refuted | — | the gap is constant and the margins sum to 0 (8 − 9 + 1) |
| F7 | ext 1 | external | the same as F3 | — | — | merged into F3 |

Metrics: 3 local rounds, 1 external, 0 substitutes. Local confirmed 3 (F1, F2, F3),
refuted 0; external confirmed 2 (F4, F5), refuted 1 (F6), 1 duplicate (F7). Findings in
code changed by the developer's cleanup: 0.

## Checks

On `c9e570a`: `npx vitest run src/Splitter.test.tsx src/WaitingCard.test.tsx` 53 passed;
`uv run pytest -m ui tests/ui/test_chat.py -n 2` 20 passed; CI run 38699283914, `ci-ok`
pass. A flake: `tests/ui/test_status_marks.py` failed once in the developer's local
`make test-ui` (143 passed, 1 failed) and passed rerun alone; it is not near this change,
and both UI shards are green in CI. No code changed for it.

## Residual risk (not checked)

- `make test` and `make lint` were not run locally in the last rounds: no Python changed,
  and CI ran the unit and integration tests green.
- The smoke was skipped by CI's `changes` rule (only `web/`, `tests/ui/`, `docs/`,
  `openspec/` changed).
- Live tests are not needed (no provider, hook, MCP or runtime change).
- The focus after a click on an edge was not checked in Firefox.

Found on the way: nothing.
