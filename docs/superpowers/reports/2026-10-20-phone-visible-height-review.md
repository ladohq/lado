# LAD-109 phone-visible-height: review report

Pull request #115 `hotfix/lad-109-phone-bottom-cut` → `main`. Scale: hotfix, reviewed
by precision. Head reviewed last: `926dc96` (= the remote head). The diff touches the web
UI (`web/src/phone.ts`, `web/src/Shell.tsx`, the "Phone layout" section of
`web/src/styles.css`, their unit tests), `tests/ui/test_phone.py`, `docs/design/ui.md`,
CHANGELOG.md, BACKLOG.md and openspec; `src/`, `providers/`, `hooks.py`,
`mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not change.

## Rounds

- **Round 1, local** (precision over `origin/main..c755185`): F1.
- **Round 1, external** (Claude Code GitHub Action; request comment 6274312705, answer
  6274320814, triage 6274364063): F2, F3, F4, F5, F6. It is of the same model family, so
  its "nothing more" weighs less.
- **Round 2, local** (precision over `c755185..16c3ada`, the F2 fix in `33c8bf7` and the
  BACKLOG.md entry in `16c3ada`): F2 resolved, F7.
- **Round 3, local** (`16c3ada..926dc96`, after a first archive attempt at `merge` failed
  `openspec validate --specs --strict`: the modified requirement's text was over 500
  characters): `53657bc` splits the keyboard out into its own requirement "On a phone the
  app shrinks above the on-screen keyboard", every scenario kept; `926dc96` merges
  `origin/main` (LAD-108, LAD-110, LAD-111), its one conflict in CHANGELOG.md, both lines
  kept. No new findings.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (precision) | the hook follows `visualViewport` during a pinch zoom too, so at 2× the app re-lays out to the zoomed area's height on every frame instead of the page simply growing | confirmed (by the code; not seen in Safari) | minor | declined: the spec says nothing of zoom, the content stays reachable as each area scrolls by itself, a fix needs a test of its own; left to the human at the merge gate |
| F2 | 1 | external | the CSS comment and the documents explained the fallback height as "html's box, which body clips to", while a `position: fixed` app takes its percentage from the viewport and `body` does not clip it | confirmed | important | fixed in `33c8bf7` (`styles.css`, `ui.md`, proposal, tasks, PR description) |
| F3 | 1 | external | the pan follows one frame late, as `visualViewport`'s `scroll` comes after the pan starts | refuted as a defect of the diff: that is how the events work | — | dropped; to look at during AC-4 |
| F4 | 1 | external + local | `position: fixed` makes `.app` a stacking context | refuted: outside `.app` are only the Tooltip portal (fixed, z-index 50, still on top), `Copy.tsx`'s off-screen field and `showModal` dialogs in the top layer; LAD-108's phone tooltip test, green in CI after the merge of main, shows it | — | dropped |
| F5 | 1 | external | no test of a rotation (`tall` → `short`) with the variables set | confirmed (a test gap) | minor | declined: a rotation re-runs the same `[phone]` effect, whose teardown and setup the unit tests cover |
| F6 | 1 | external | the hook ignores the UI test fake's `scale`/`offsetLeft` | refuted: the fake mirrors the real API | — | dropped |
| F7 | 2 | local (precision) | one line of `docs/design/ui.md` (1905) is 111 characters after the fix, its paragraph wrapped at ~90 | confirmed | minor | declined: Markdown source layout only, longer lines exist, nothing checks the length |

Metrics: 3 local rounds, 1 external, 0 substitutes. Local confirmed 2 (F1, F7), refuted
0; external confirmed 2 (F2, F5), refuted 3 (F3, F4, F6). Findings in code changed by
the developer's cleanup: 0.

## Spec coverage

- "On a phone the composer stays at hand": "Writing with a gate waiting" —
  `test_the_composer_stays_at_the_bottom_with_a_gate_waiting`; "The browser's bottom bar"
  and "The expanded card" — `test_the_composer_and_the_send_button_are_in_sight`.
- "On a phone the app shrinks above the on-screen keyboard": "The on-screen keyboard" and
  "The keyboard closes" — `test_the_app_shrinks_to_the_visible_part_and_grows_back` and
  `test_the_app_follows_safaris_pan`.
- AC-3 (a computer and a tablet keep their frame) — `keeps_the_computers_frame`.
- `tasks.md`: every task checked; 2.3 has no screenshots, the reason recorded (Chromium
  did not start in the container, LAD-110).

## Checks

- CI of PR #115 on `926dc96`: 15 jobs pass (unit 3.10/3.13, integration ×6, js, ui ×2,
  container ×2) with `ci-ok`; smoke skipped by the skip list. 196 UI tests passed on
  `c755185`, the 3 new ones among them.
- The developer on `926dc96`: `make lint` clean; `make web` 976/976; `make test` 3613
  passed, 1 skipped.
- A flake on the way: `tests/test_server_clones.py::test_a_window_that_went_away` timed
  out under load in round 1 and passed alone 2 of 2; unrelated to the diff.
- At the archive: `openspec validate --specs --strict` 42 passed, 0 failed.

## Found on the way

- The expanded terminal and the menu drawer are tied to the layout viewport, not to the
  visible part of the window: BACKLOG.md, P2 (`16c3ada`).

## Not checked (residual risk)

- The bug shows only in Safari of iOS 26 with its bars and keyboard; no automated browser
  reproduces them, and the AC-1 test in Chromium would have passed before the fix. Only
  the manual check AC-4 on an iPhone confirms it; look at F1 (zoom), F3 (the pan), the
  expanded terminal and the menu at the same time.
- The UI e2e tests were not run locally and no screenshots were taken (Chromium does not
  start in the reviewer's container); the screens were not compared with `ui.md` and the
  mockup. CI ran the UI tests green.
