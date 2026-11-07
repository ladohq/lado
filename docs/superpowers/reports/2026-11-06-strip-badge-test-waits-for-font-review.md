# LAD-222 strip-badge-test-waits-for-font: review report

Pull request #236 `fix/lad-222-strip-badge-font` → `main`. Scale: tweak, review depth: precision.
Head reviewed: `57e720de`. The flake of `test_the_strips_badges_tell_task_sessions_apart`, a race
in the test and not a defect of LADO: the text of the badge `154·2` fills its box exactly in IBM
Plex Mono, and the fallback font is wider, so the check was false until the font arrived. The test
now waits for the badge's own font with `document.fonts.load`, and the entry goes from BACKLOG.md.
Tests only: no API, schema, MCP, CLI or UI change, no CHANGELOG.md line. No delta.

## Rounds

1. Local, precision, `941b875c..57e720de`: no wide pass needed, the diff touches no business logic,
   no user data and no code of earlier rounds. Every task of `tasks.md`, the design's decisions and
   the scope's limits were checked. No findings.
2. External 1, Claude Code GitHub Action: "good to merge once CI is green", 3 remarks, no blocker,
   all refuted (below). `Files not read` was empty, but the reviewer read the diff and the change's
   files only and ran no tests. It is the same model family, so its verdict weighs less.

External rounds used: 1 of 1.

## The human's decisions

- **Gate `merge_ok`, approved** with no comment.

## Findings

No finding confirmed, local or external. Found on the way: none.

Refuted, all external:

- **F1.** The layout may shift a frame after the font loads, so `expect.poll` or
  `requestAnimationFrame` was proposed. `getBoundingClientRect()` recomputes the layout at once and
  waits for no frame, the runs with a delayed font passed, and the design rejected a retry: a badge
  that overflows for a moment would pass.
- **F2.** `tasks.md` 1.2 and 1.3 name a `build-report` that the pull request lacks. It is an artifact
  of the run, not a file of the repository, and the same numbers are in the pull request's
  description.
- **F3.** The proposal names line 297, and the check has moved. It is the line of the failure before
  the fix, which is right for the history of the cause.

## Checks

| Check | Head | Result |
|---|---|---|
| The font delayed by 0.7 s, the wait switched off | `57e720de` | 6 of 6 failed; a seventh run showed the failure at the width check, `test_narrow_layout.py:301`, `assert False` |
| The font delayed by 0.7 s, the wait working | `57e720de` | 6 of 6 passed, the font's request delayed in each |
| `uv run pytest -m ui tests/ui/test_narrow_layout.py` | `57e720de` | 41 passed |
| `make lint` | `57e720de` | exit 0 |
| `openspec validate strip-badge-test-waits-for-font --strict` | `57e720de` | exit 0 |
| `openspec validate --specs --strict` | `57e720de` | 62 passed, 0 failed |
| A trial archive with `--skip-specs`, then the specs | `57e720de` | 62 passed, 0 failed |
| CI of the pull request (run 42288267461) | `57e720de` | `ci-ok` green: 15 pass, no reruns, smoke skipped, every file on the skip list |

The runs with a delay used a pytest plugin outside the tree, which held back the IBM Plex Mono file
and could switch `document.fonts.load` off; the working tree did not change. A first try with
`time.sleep` in the handler does not count: the wait switched off passed 6 of 6, as `sleep` stops
the test itself too. `make test` and the integration tests ran in CI, not locally. The live tests
were not needed: `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and
`tests/live/` did not change.

## Metrics

Rounds: 1 local, 1 external, 0 stand-in. Confirmed: 0 local, 0 external. Refuted: 0 local, 3
external. Findings in code changed by the developer's cleanup: 0.

## What was not checked

- AC-2 and AC-3 (20 runs each) were not repeated by the reviewer: they are the developer's results.
  The reviewer's own are the 6 runs with a delay and one run of the whole file.
- The flake was rare, so one green `ui (2)` in CI does not prove it gone. The ground is the red with
  the wait switched off against the green with it working.
- `make web` and `make test-js` were not run: `web/` and the plugin did not change. The smoke was
  skipped and the live tests were not run.
- Other tests that measure text without waiting for fonts stay out of scope by design; none is known
  to flake.
