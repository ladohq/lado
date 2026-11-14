# LAD-283 waiting-tabs-test-one-layout: review report

Pull request #306 `hotfix/lad-283-waiting-tabs-test-one-layout` → `main`. Scale: hotfix,
depth precision. Head reviewed: `b0564f0c`. The UI test
`test_many_tabs_stay_on_one_line_on_the_panel_and_scroll_sideways` (`tests/ui/test_chat.py`)
read the shown tab's box and the panel's box with two `bounding_box()` calls, which under CI's
load came from two layouts while the card settled after a tab click. Its check now reads every
box in one `evaluate` (one layout) and first waits until the card's geometry is the same over
two animation frames. No product code changes; BACKLOG.md's flaky-test summary names the
test's file and this fix.

## Rounds

1. Local, precision (`d4b68a82..b0564f0c`), the change checked against its proposal and tasks,
   and external 1, Claude Code GitHub Action (no blockers; raised E1-E3). The external reviewer
   read `tests/ui/test_chat.py` and `BACKLOG.md`, not the openspec files, which the local round
   checked.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| E1 | minor | external: a small window remains between `settle()` returning and the next `evaluate` | declined: every box of a check comes from one `evaluate`, and in any one layout the tab lies on the panel; only the expand button's x and the screenshot could fall in the window; close it only if the test flakes again |
| E2 | — | external: handles taken once could go stale, so `settle()` would pass on zero boxes | refuted: the card itself is among the waited parts, and after `settle` the boxes are read again with fresh handles in one `evaluate` |
| E3 | — | external: `window.__ladoSettled` is a page global | refuted: reset before each wait, and the waits run one at a time |

## Spec check

No delta (archived with `--skip-specs`).
- AC-1: no assertion compares boxes of two `bounding_box()` calls; all come from one
  `evaluate`.
- AC-2: `wait_for_function` with `polling="raf"`, Playwright's default timeout and a message
  naming what did not settle.
- AC-3 (CSS mutations fail the test) and AC-4 (20 runs under load green): from the build
  report, not repeated by the reviewer.

## Found on the way

None new. The card's jump after a tab click and other tests pairing two `bounding_box()`
calls were out of scope by the design.

## Checks

On `b0564f0c`:
- `make lint`: clean.
- `openspec validate waiting-tabs-test-one-layout --strict`: valid.
- `uv run pytest -m ui -n 2 tests/ui/test_chat.py`: 41 passed.
- The test by node id with `-n0`: 5 of 5 green (no load, ~3 s).
- CI on the pull request: `ci-ok` success; smoke skipped by the skip list.

Not run locally: `make test` and the integration tests (CI ran them). No change to
`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or `tests/live/`.

## Residual risk

The window of E1 could still flake the expand button's x comparison under CI's load; the
panel and one-line checks cannot.
