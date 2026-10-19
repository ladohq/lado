# LAD-111 forget-many-waits-for-navigation: review report

Pull request #114 `hotfix/lad-111-forget-many-navigation-wait` → `main`. Scale: hotfix,
reviewed by precision. Head reviewed last: `affaa3c` (= the remote head). The diff touches
only `web/src/ForgetMany.test.tsx` and openspec; `src/`, `providers/`, `hooks.py`,
`mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not change, so no
live tests are needed.

## Rounds

- **Round 1, local** (precision over `a44835e..affaa3c`: tests, false greens, spec,
  architecture): F1, F2.
- **Round 1, external** (Claude Code GitHub Action, request `issuecomment-6274274524` at
  18:25:57 UTC, answer "Claude finished" at 18:26:50 UTC): F3. No blockers; it agreed
  with declining F1 and F2. It ran no tests and is of the same model family, so its
  "nothing more" weighs less.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (false green) | the last check of "the sessions are forgotten one at a time … and Esc waits" proves nothing about the navigation: the test opens on `/sessions` (`open()` defaults to `at="/sessions"`), so "No session open" shows from the start; the change only makes it awaited | confirmed | minor | declined: older than the change, outside the flake; Found on the way (P3, XS: open the test on `/sessions/lad-97` or drop the check) |
| F2 | 1 | local (false green) | "another session open in the page stays" checks "A session open" synchronously right after `onClose`; a wrong `navigate` in a transition could land after the check and pass unnoticed | confirmed | minor | declined: older than the change; Found on the way (P3, XS: `await act(async () => {})` before the check) |
| F3 | 1 | external | the comment "a render after Close" holds only for React Router 8's transitions and would need updating with another router | refuted | — | dropped: the comment is accurate for the current code, and `findByText` does not depend on the number of renders |

Metrics: 1 local round, 1 external, 0 substitutes. Local confirmed 2 (minor), refuted 0;
external confirmed 0, refuted 1. Findings in code changed by the developer's cleanup: 0.

## Spec

- AC-1: "goes to /sessions" awaits `screen.findByText("No session open")` after Close,
  with a one-line comment (`ForgetMany.test.tsx:258-259`); task 1.2 (the human's word at
  design_ok) does the same in the "one at a time" test (`:233`).
- AC-2: the developer ran the test 2000/2000 green with the CPU loaded by eight `yes`
  processes; the reviewer's own repeat, 40/40 under the same load. Before the fix the
  design reproduced the failure 1 in 300.
- AC-3: CI on `affaa3c` green (`ci-ok`, `ui (1)`/`ui (2)` run `make web`); smoke skipped
  by the skip list.

## Checks

- `npx vitest run src/ForgetMany.test.tsx` (web/): 11 passed.
- `openspec validate forget-many-waits-for-navigation --strict`: valid.
- At the archive: `openspec validate --specs --strict` 41 passed, 0 failed.

## Not checked (residual risk)

- `make web` was not run locally by the reviewer (the developer ran it: 955/955; CI ran it
  on the same head).
- The reviewer's repeat is 40 runs, not 1000; the 2000 are the developer's report.
- Other vitest tests were not searched for the same pattern (a synchronous check of the
  page after a navigation): out of scope by design.
