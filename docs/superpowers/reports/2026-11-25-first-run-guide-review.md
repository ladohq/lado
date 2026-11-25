# LAD-311 first-run-guide: review report

Pull request #362 `feature/lad-311-first-run-guide` → `main`. Scale: full. Head reviewed:
`9a801a3a`. Stage 1 of the web UI's first-run guide: the guide's engine, the main path
(welcome → connect a model through Agent CLIs or Model servers, "I have none of these", the
commit author when missing, New session), five first-encounter tips (New session window,
session page, first gate, first agent question, first terminal), Help → Getting started,
the guide's marks on the server (`LADO_HOME/guide.json`, `GET`/`POST /api/guide`), the
switch `LADO_GUIDE=0`, all hints as data in one file and a unit test of the `data-guide`
markers.

## Rounds

1. Local, breadth, `51b966c3..6eb5ccc6`: 5 important, 2 unverifiable, 4 minor to fix,
   6 minor declined, 2 refuted.
2. Local, precision, `..430e1c7b`: F1–F11 resolved.
   External 1, Claude Code GitHub Action: no blockers, E1–E5 minor declined.
   Gate #610 returned by the human (first manual check), fixed in `fc29675d`.
3. Local, breadth, `430e1c7b..fc29675d`: G1 important; G2, G3 minor declined.
4. Local, precision, `fc29675d..5b43bc10`: G1 resolved; G4 minor declined.
   External 2, Claude Code GitHub Action (`430e1c7b..5b43bc10`, reply
   #issuecomment-7161324629): no blockers, E6–E12.
   Gate #612 returned by the human (second manual check), fixed in `86d8127e`,
   `3f963891`, `f7585564`.
5. Local, precision, `5b43bc10..f7585564`: no blockers or important; H1 minor declined.
   Gate #614 returned by the human (third manual check and the designer's colour scheme),
   fixed in `68c763c6`, `8b306334`, `9a801a3a`.
6. Local, precision, `f7585564..9a801a3a`: no blockers or important; H2 minor declined.

External rounds used: 2 of 2.

## Findings

| ID | Finding | Level | Outcome |
|---|---|---|---|
| F1–F6 | Round 1's important findings | important | fixed in `795ca38f`, a test for each |
| F7 | The hint's live region | unverifiable | fixed in `795ca38f`; not checked with a screen reader |
| F8–F11 | Round 1's minor findings to fix | minor | fixed in `795ca38f` |
| F12–F17, F20, F21 | Narrow races, degenerate conditions, log noise, heuristics the design chose, wording | minor | declined |
| F18 | A marker name | — | refuted: the design sets it |
| F19 | Only Claude Code and Codex CLI get login steps | — | refuted: stage 1's agreed scope |
| G1 | The guide stood on "Open your server" when no installed agent CLI could use the server | important | fixed in `5b43bc10` (`Guide.test.tsx`); on a phone Add server stays in view since `68c763c6` (`place.test.ts`) |
| G2 | A second tab's GET completes the record while the first runs the guide from Help | minor | declined: the human's rule |
| G3 | The page heading keeps `tabIndex=-1` after Not now | minor | declined: harmless |
| G4 | Step `model-no-cli` dimmed the page though it leads elsewhere | minor | resolved on the way in `86d8127e` (`dim: false`) |
| E1–E5 | External round 1 | minor | declined (comment 7157695041) |
| E6 | A model marked for an uninstalled CLI counts as connected | minor | declined: needs a CLI removed after the mark |
| E7 | `_done()` can complete the record right after a restart | minor | declined: a microsecond window, the G2 family |
| E8 | A restart on a set-up LADO lasts one page load | — | refuted as a defect: by design, a scenario of the spec |
| E9 | `useRoom` writes a ref during render | minor | declined: the ref only grows, cleanup restores it |
| E10 | `shownRect` clips only by ancestors with overflow | minor | declined: no current marker affected |
| E11 | `accessibleName` exported from a component file | minor | declined: the fast-refresh rule is not on |
| E12 | A stale `terminal-panel` marker in the design doc | minor | declined: the doc's appendix records the move |
| H1 | "You can start the guide again…" and the welcome note are outside the card's `aria-describedby` | minor | declined: read by navigation inside the dialog |
| H2 | A browser test's docstring still calls the ring "dashed" | minor | declined: does not affect the check |

Metrics: 6 local rounds, 2 external, 0 substitute; 22 local findings confirmed (7
important), 2 refuted; 12 external confirmed (all minor), 1 by design; three manual checks
by the human, every remark fixed; 0 findings in code changed by the developer's clean-up.

## Checks at `9a801a3a`

- `make lint`: clean
- `make web`: clean, vitest 2114 passed
- `pytest -m ui tests/ui/test_first_run_guide.py`: 3 passed
- `openspec validate first-run-guide --strict`: valid; after the archive `openspec
  validate --specs --strict`: 92 passed
- CI: 27/27 pass, `mergeStateStatus: CLEAN`

## Not checked, residual risk

- Screen reader reading (F5, F7, H1): checked only in jsdom and by the DOM.
- An agent CLI's login in state `unknown` counts as not logged in.
- Step `model-no-cli` on a phone is out of the browser test's reach (the test server's fake
  CLIs work with any server); covered by `place.test.ts` and `hints.test.ts`.
- Colour contrast checked by calculation in `tokens.test.ts` and the developer's
  screenshots, not by eye.
- The external reviewer did not see `5b43bc10..9a801a3a` (round cap reached), nor read
  `hints.ts`, `place.ts` and the tests whole.
- Not run locally: `make test-integration`, `make test-js`, live, smoke and the full
  `make test-ui` after `86d8127e`; no Docker image built. CI covers them.
- `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/`
  unchanged: no live tests needed before the merge.

Found on the way: no common error boundary in the web UI, recorded in BACKLOG.md
(`430e1c7b`).
