# LAD-108 session-head-status: review report

Pull request #116 `hotfix/lad-108-head-status` → `main`. Scale: hotfix, reviewed by
precision. Head reviewed last: `f3f073c` (= the remote head). The diff touches only the
web UI (`web/src/Sessions.tsx`, `web/src/styles.css`, vitest tests), `tests/ui/test_phone.py`,
`docs/design/ui.md`, CHANGELOG.md and openspec; `src/`, `providers/`, `hooks.py`,
`mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not change.

## Rounds

- **Round 1, local** (precision over `origin/main...01fa473`, 5 commits, 12 files): F1.
- **Round 2, local** (precision over `01fa473..ce57417`: the spec, `ui.md`, `tasks.md` 6.1,
  vitest; no product code): nothing new.
- **Round 1, external** (Claude Code GitHub Action, request comment #6274497054 at
  18:37 UTC, "Claude finished" at 18:38 UTC): no blockers; F2, F3. It is of the same model
  family, so its "nothing more" weighs less.
- **Round 3, local** (a return from `merge`: the archive's `openspec validate --specs
  --strict` failed on the phone-layout requirement's length over 500 characters and on
  `session-status-mark`'s placeholder Purpose; precision over `ce57417..f3f073c`, openspec
  deltas only): nothing new. The modified phone-layout requirement equals `main`'s but for
  "the mark's words" and the new scenario; an archive in a copy of `openspec/` validated
  42 of 42.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (spec) | a session in trouble (`tmux_gone`/`loop_down`) in which something waits is in Needs you and its strip icon says so, while the head shows the trouble; the spec and `ui.md` said the strip icon takes its mark from `sessionMark`, so code and spec disagreed, untested | confirmed | important | fixed in `ce57417`: the spec (requirement "The list's group follows what waits, not the mark", scenario "Trouble while a gate waits") and `ui.md` follow the code; a vitest in `web/src/Layout.test.tsx` pins it for `tmux_gone` and `loop_down`, shown red when the icon is drawn through `sessionMark` |
| F2 | 2 | external | `HEAD_MARKS` mixes the list's `dot`/`activity-*` classes with the old `session-dot-*`; asks for a one-line comment | confirmed | minor | declined: the comment above `HEAD_MARKS`/`StatusDot` already says it; the loop converged |
| F3 | 2 | external | "trouble while waiting" is covered by vitest only; the phone e2e checks only running and stopped | refuted | — | dropped: the rule is checked at the lowest layer (jsdom sees the classes and names), and `tests/ui/test_phone.py` checks the `needs you · 1 gate` mark |

Metrics: 3 local rounds, 1 external, 0 substitutes. Local confirmed 1 (important),
refuted 0; external confirmed 1 (minor), refuted 1. Findings in code changed by the
developer's cleanup (`groupOf` back on `isLive`/`waits`): 1 (F1).

## Checks

- CI of PR #116 on `f3f073c`: `ci-ok` green, all jobs pass; smoke skipped by the skip list.
- A flake on the way: `integration (3.13, 3)`,
  `tests/integration/test_uninstall_process.py::test_uninstall_leaves_nothing` (an agent
  process alive after uninstall), red on the first run, green after `gh run rerun
  --failed`; no tracker task yet, the human was asked (#302).
- `make lint` clean; vitest: round 1 three files, 130 passed; round 2 `Layout.test.tsx`
  75 passed; the developer's `make web` 973 passed.
- `openspec validate session-head-status --strict` valid; at the archive
  `openspec validate --specs --strict` 42 passed, 0 failed.

## Not checked (residual risk)

- No screenshots (Chromium does not start in the container, LAD-110; CI does not upload
  them): the diamond and the pulse in the top bar were checked against the mockup by code
  and CSS classes, not by picture.
- `make test` (no Python changed) and the UI e2e tests were not run locally; CI ran them.
- A conflict with LAD-109 (the phone layout) in `Sessions.tsx`/`styles.css` is possible
  at its merge.
