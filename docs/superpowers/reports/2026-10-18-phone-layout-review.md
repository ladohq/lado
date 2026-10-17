# LAD-95 phone-layout: review report

Pull request #94 `feature/lad-95-phone-layout` → `main`. Scale: full, reviewed breadth
first. Head reviewed last: `6f13e0c` (= the remote head). `providers/`, `hooks.py`,
`mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not change, so live
tests are not needed before the merge.

## Rounds

- **Round 1, local** (breadth over `3070cb4..926f633`; lenses spec, tests, silent
  failures, comments, general/architecture; types skipped, no new types): F1.
- **Round 1, external** (Claude Code GitHub Action, request `issuecomment-6242504614`,
  answer `issuecomment-6242508418`): F2–F6.
- **Round 2, local** (precision over the delta `926f633..6f13e0c`): the fixes of F1, F3
  and F5 read, no new defects; the `pathname` effect is harmless on mount, F5's effect
  does not loop.
- **Round 2, external** (request `issuecomment-6242600627`, answer
  `issuecomment-6242604404`): nothing new; F2, F4 and F6 accepted. Its leftover from
  round 1, "grep the CSS outside `:root[data-phone]`", was checked locally in round 1:
  every selector of the section has that prefix. The external reviewer is of the same
  model family, so its "nothing new" weighs less.

External rounds used: 2 of 2.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (spec, D2) | the menu's drawer did not close on a route change from outside the rail (the back gesture) | confirmed | minor | fixed in `6f13e0c`: a `useEffect` on `pathname`; test in `web/src/Shell.test.tsx`, red before the fix |
| F2 | 1 | external | the pull request's description and the plan said `lado.waitingMinimized.*` is never written on a phone, while the human's own Minimize upright writes it | confirmed (the text was wrong; the code follows D5 and the spec) | important | fixed in `6f13e0c`: the plan and the description corrected; a guard test in `web/src/WaitingCard.test.tsx` (green before too, as the code was right) |
| F3 | 1 | external | Esc in the `SessionDetails` sheet also minimized an expanded waiting card | confirmed | minor | fixed in `6f13e0c`: the card ignores Esc inside a `dialog`; test in `web/src/WaitingCard.test.tsx`, red before the fix |
| F4 | 1 | external | Close terminal on a phone does not return the focus, and the page under the terminal is not `inert` | confirmed | minor | declined: the spec does not require it; it needs remembering who opened the terminal and a test, and `inert` is a decision for every overlay of the UI. The external reviewer agreed; the human approved the merge with it open |
| F5 | 1 | external | `phoneOpen` was not reset when the screen stopped being a phone, so control was not released | confirmed | minor | fixed in `6f13e0c`: an effect calls `closePhone()`; test in `web/src/Terminals.test.tsx`, red before the fix |
| F6 | 1 | external | a card expanded on a computer when the window turns into a "phone" | refuted | — | dropped: a mouse never matches `PHONE_QUERY`, both of its conditions include `pointer: coarse` (`phone.ts:8`) |

Metrics: 2 local rounds, 2 external, 0 substitutes. Local confirmed 1 (minor), refuted
0; external confirmed 4 (1 important, 3 minor), refuted 1. Findings in code changed by
the developer's cleanup: 0.

## Checks

- On `6f13e0c`: `make lint` green; `make web` green (vitest 890 passed, stale types
  clean).
- On `926f633`: `uv run pytest -m ui tests/ui/test_phone.py` 18 passed; `openspec
  validate --specs --strict` 33 passed, the change valid in strict mode. These files did
  not change after round 2.
- By the developer's build report on `6f13e0c`: `make test` 3411 passed, `make test-ui`
  175 passed.
- CI of PR #94 on `6f13e0c`: `ci-ok` SUCCESS (unit ×2, integration ×6, ui ×2, js,
  container ×2, changes). The smoke was skipped by the skip list: the change touches only
  `web/`, `docs/`, `openspec/`, `tests/ui/` and Markdown.

## Not checked (residual risk)

- Real devices (iOS Safari, Android Chrome): only Chromium's emulation with `is_mobile`
  and `has_touch`. The on-screen keyboard (`interactive-widget=resizes-content`, the
  composer above the keyboard) is not covered by e2e. The human will check on a phone
  after the release.
- `make test` and the whole `make test-ui` were not run locally by the reviewer: CI and
  the developer ran them.

Found on the way: none.
