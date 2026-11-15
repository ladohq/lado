# LAD-209 new-session-phone-fit: review report

Pull request #315 `fix/lad-209-new-session-phone-fit` → `main`. Scale: tweak, depth
precision. Head reviewed: `e030c740`. A fresh walk of the New session window (1440 and 390 px,
keyboard) found two of the LAD-180 design findings obsolete (the Model list's direction, the
focus after Where's switch, which is gone) and the rest still true. On a phone the window's
fields, notes' buttons and `+ Add kit` are now 44 px targets and a kit's × has a 44 px hit
area; a picked model's name stays whole, the server's mark giving way first; a silent server's
mark in the field carries the refusal's round `!`; a start refused for its model is said once.

## Rounds

1. Local, a full pass (spec, tests, comments, general) over `origin/main...038fc43a`, as
   `.mp-value` also touches Settings. Found F1 (important), F2–F4 (minor).
2. Local, precision, over the delta `038fc43a..e030c740`: F1 and F2 resolved, nothing new;
   checked that the test waits until each way of Where settles, that the `a_project` fixture
   runs before `server`, and that the bundle in `static` holds the new rule.
3. External 1, Claude Code GitHub Action, the whole pull request
   (https://github.com/ladohq/lado/pull/315#issuecomment-6893281600): nothing blocking, six
   notes E1–E6. It read every changed code and test file, not CHANGELOG, `ui.md` or openspec
   (checked locally in rounds 1–2). Answers:
   https://github.com/ladohq/lado/pull/315#issuecomment-6893327211

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | local: the 44 px targets test raced the server on Project…: it mostly measured "checking…", and failed on the 18 px link «Make one in Projects» when the answer came first; Project's select was never measured | fixed in `e030c740`: the test waits until each way of Where settles, makes a project for Project… and measures its select; the link inside a sentence is excluded from the 44 px rule (delta of `new-session-window`, `ui.md`, `SHORT_TARGETS`) |
| F2 | minor | local: the phone's 44 px rule stretched the folder set-up's «Include …» checkboxes to 16×44 | fixed in `81f9c8a9`: `[type="checkbox"]` excluded; `test_a_plain_folder_is_set_up_and_started` checks ≤ 20 px at 1440 and 390, seen red |
| F3 | minor | local: on a phone Kits has no vertical padding; with 3+ kits the second row of chips touches the top border | declined: one row stays 44 px; visual only |
| F4 | minor | local: Switch off's offers ≥ 44 px (AC-2) not covered by a test | declined: the same rule as the tested notes' buttons; a test needs a `--without` refusal |
| E1 | minor | external: the placeholder «<CLI>'s settings» after `display: contents` is no longer cut by the field | declined: every current CLI name fits at 390 px |
| E2 | minor | external: `.model-pick .srv.down { min-width: 43px }` a magic number | declined: the comment says what it is made of (the icon and the sign) |
| E3 | — | external: `flex-shrink: 1e12` and `1e6` checked only in Chromium | unverifiable: Firefox does not run in the container (no system libraries, no apt) |
| E4 | — | external: F3 fixed for free with `padding-block: 6px` | refuted: `+ Add kit` is a 44 px select in the same box, so one row would be 56 px |
| E5 | minor | external: the same as F4 | merged with F4 |
| E6 | minor | external: the ×'s hit area (`::after`, inset −6 px) reaches 6 px over the chip's version text | declined: the 44 px area is the design's (D2); the chip's text has no action of its own |

## Metrics

Rounds: 2 local, 1 external, 0 stand-ins. Findings: local 4 confirmed (1 important, 3 minor),
0 refuted; external 4 confirmed (E1, E2, E6, E5 merged with F4), 1 refuted, 1 unverifiable;
findings in code changed by the developer's cleanup: 0.

## Checks

- Round 2, on `e030c740`: `make lint` exit 0; `openspec validate new-session-phone-fit
  --strict` valid; trial archive with `openspec validate --specs --strict`: 85 passed;
  `uv run pytest -m ui -n auto tests/ui/test_launch.py tests/ui/test_launch_model.py` four
  times, 60 passed each; vitest `ModelPicker.test.tsx`, `Launch.test.tsx` (round 1, unchanged
  since): 293 passed.
- CI of PR #315 on `e030c740`: every job pass, `ci-ok` pass; the smoke skipped by CI's rules
  (the whole diff in the skip list); mergeStateStatus `CLEAN`.

## Residual risk

- E3: Firefox and Safari not checked; the UI tests run only in Chromium. By hand: open the
  window at 390 px with the default model «Локальная Qwen» on «LM Studio дома»; the name must
  show whole, without an ellipsis.
- `make test` and the integration tests not run locally (no Python changed); green in CI.
- Live tests not needed: `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
  `agent_env.py`, `tests/live/` unchanged.
- The external reviewer is a model of the same family.

Found on the way: none.
