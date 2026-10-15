# LAD-78 waiting-card-focus-ring: review report

Pull request #75 `fix/lad-78-waiting-card-focus-ring` → `main`. Scale: tweak, reviewed for
precision (not widened: only CSS, UI tests and docs changed, no logic or data). Head
reviewed last: `e3c005f` (= the remote head). `providers/`, `hooks.py`, `mcp_server.py`,
`runtime.py`, `agent_env.py` and `tests/live/` did not change, so live tests are not
needed before the merge.

## Rounds

- **Round 1, local** (precision over `main...d4fc2d1`): F1 (important), F2 and F3
  (minor, declined). Sent back to the developer.
- **Round 2, local** (precision over the delta `d4fc2d1..e3c005f`): F1 resolved, no new
  findings.
- **Round 1, external** (Claude Code GitHub Action over `main..e3c005f`, request
  21:58:38Z, "Claude finished" 22:01:22Z): nothing blocking; it confirmed the fix of F1,
  agreed with declining F2 and F3, and found F4 and F5 (minor). The external reviewer is
  of the same model family, so its "nothing blocking" weighs less.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (diff) | `.answer textarea`'s `scroll-margin` fell back to `0px` outside `.waiting-card`, where `--ring-room` was set: on the Flows tab (`.list-main` scrolls) a growing gate's comment lost the bottom of its ring | confirmed (reproduced: 3.5 px cut on `d4fc2d1`) | important | fixed in `e3c005f`: `--ring-room` on `:root`, no fallback; `test_gates.py::test_a_gates_long_comment_on_the_flows_tab_shows_its_ring_whole` red on `d4fc2d1`, green after |
| F2 | 1 | local | the ring of `.waiting-gate.marked`, drawn around the list itself, now stands 7 px from the content at the top and left (was 3) | confirmed | minor | declined at the merge gate: the content does not move, the ring is even (7/7/7/9) and not cut |
| F3 | 1 | local (spec) | no test of its own for the Skip field's ring | confirmed | minor | declined: the same `.waiting-field:focus` rule as the own answer, which AC-3's test covers |
| F4 | ext 1 | external | `MEASURE_RING` reads only the first shadow of a `box-shadow` list | confirmed | minor | declined: no such ring exists now |
| F5 | ext 1 | external | the comment over `:root { --ring-room }` says "the outline below" where `:focus-visible` is meant | confirmed | minor | declined: the meaning holds |

Metrics: 2 local rounds, 1 external, 0 substitutes. Local confirmed 3 (1 important, 2
minor), refuted 0; external confirmed 2 (minor), refuted 0. Findings in code changed by
the developer's cleanup: 0.

## Checks

- On `e3c005f`: `uv run pytest -m ui tests/ui/test_chat.py tests/ui/test_gates.py
  tests/ui/test_flows_tab.py -n 4`, 36 passed; `make lint` green; `openspec validate
  --specs --strict` and `openspec validate waiting-card-focus-ring --strict` valid.
- CI on `e3c005f`: `ci-ok`, unit (3.10, 3.13), integration (6 shards), js, ui (2 shards),
  container (amd64, arm64) green; the smoke skipped by the skip list (all files in it).
- The developer: `make test` 3314 passed, `make web` 825 passed.

## Residual risk (not checked)

- Checked in Chromium only (Playwright); `scroll-margin` and the negative margin were not
  looked at in Safari or Firefox.
- Other scrolling boxes of the UI are out of scope; no cut there was reported.
