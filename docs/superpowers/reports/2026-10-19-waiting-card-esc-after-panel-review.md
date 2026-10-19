# LAD-99 waiting-card-esc-after-panel: review report

Pull request #108 `hotfix/lad-99-waiting-card-esc-race` → `main`. Scale: hotfix, reviewed
by precision. Head reviewed last: `32db38b` (= the remote head). The diff touches only
`tests/ui/test_chat.py`, BACKLOG.md and openspec; `src/`, `web/`, `providers/`,
`hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not
change.

## Rounds

- **Round 1, local** (precision over `origin/main...32db38b`): F1.
- **Round 1, external** (Claude Code GitHub Action, request `issuecomment-6267878858`
  at 13:04 UTC, answer "Claude finished" in job 39257014366): F2, F3, F4. It ran no UI
  tests (shallow checkout, no Chromium) and read the files directly; it is of the same
  model family, so its "nothing more" weighs less.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (recorder's correctness) | in a "card class" entry `now` is the card's class at the `MutationObserver` callback; two class changes in one callback both show the final class | confirmed | minor | declined: `was` of the next entry (`attributeOldValue`) gives the true sequence and the last `now` is right; the record is diagnostics, not a check; the external reviewer agreed |
| F2 | 1 | external | the BACKLOG.md entry points at the local branch `lad-99-backup` (99b32ad), which no one else can read | confirmed | minor | declined: the candidate is described in words (Esc listeners in `useLayoutEffect` instead of `useEffect`), enough to redo it; not publishing the fix is the human's decision (#193) |
| F3 | 1 | external | `record_esc`'s docstring ("two probes and 100 runs in CI stayed green") will go stale once the flake is explained | confirmed | minor | declined: it says why the recorder exists; once the flake is explained the recorder goes with it |
| F4 | 1 | external | the record has no `focus`/`blur` events | confirmed | minor | declined: each keydown's `active` field already shows the focus at the moment that matters (as the AC-3 record shows); `focusin` is needed only if the cause turns out to be focus, which the next record will tell |

Checked and not a finding:
- `defaultPrevented` in the bubble phase on `window` does tell the card's listener: every
  keydown listener of the page is on `document` (`WaitingCard.tsx`, `ArtifactPanel.tsx`,
  `Shell.tsx`, `Tooltip.tsx`, `Sessions.tsx`), only the card calls `preventDefault` on
  Escape, and none calls `stopPropagation` (but the test fake `fakes.ts`).
- `printed_on_failure` catches `Exception`, both `expect`'s `AssertionError` and
  Playwright's `TimeoutError`; an error reading the record does not replace the failure;
  a pass prints nothing.
- `record_esc` runs before the session page's `page.goto`; the wrapped
  `pushState`/`replaceState` with `url == null` records the current query, which is right.
- The probe `test_a_second_esc_while_the_page_is_busy_folds_the_card` is gone; the
  original test's steps and checks are unchanged (only indented).

Metrics: 1 local round, 1 external, 0 substitutes. Local confirmed 1 (minor), refuted 0;
external confirmed 3 (all minor), refuted 0. Findings in code changed by the developer's
cleanup: 0.

## Checks

- CI of PR #108 on `32db38b`: all jobs pass (unit ×2, integration ×6, js, ui ×2,
  container ×2) with `ci-ok`; smoke skipped by the skip list.
- `make lint` clean; `openspec validate waiting-card-esc-after-panel --strict` valid;
  `openspec validate --specs --strict` exit 0.
- `uv run pytest -m ui --collect-only -n0 tests/ui/test_chat.py`: the test is listed, the
  probe is not.
- AC-3: the temporary F2 for the second Esc (`9b13262`) failed in CI run 39252914783 and
  printed the record (quoted in the build report); reverted in `83c9735`.
- A flake on the way: run 39253696528 on `93daa14`, `ui (1)` failed on
  `test_the_human_attaches_files_and_the_agent_gets_them` (LAD-102, already in the
  tracker); green after `rerun --failed`, unrelated to the diff.
- At the archive: `openspec validate --specs --strict` 39 passed, 0 failed.

## Not checked (residual risk)

- The UI e2e tests were not run locally (Chromium does not start in the container); CI ran
  them, and the test is green with the recorder.
- The cause of LAD-99's flake is **not found**, and the change does not make the test
  more stable: it only prints data at the next failure. This was the human's choice
  (#193), not the task's original wording ("make the test stable"). The flake is rarer
  than 1 in 100; when it fails again, read the record in the `ui` job's log and file a
  task with it (BACKLOG.md, P2).
- The `useLayoutEffect` fix candidate exists only on the local branch `lad-99-backup` of
  LADO's container (F2).
