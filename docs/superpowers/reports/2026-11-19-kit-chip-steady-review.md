# LAD-298 kit-chip-steady: review report

Pull request #344 `hotfix/lad-298-kit-chip-steady` → `main`. Scale: hotfix, a precision
review. Head reviewed: `97b4f635`. While the New session window asks for the kit list of a
new place, Kits keeps showing the chips by the last kit list it got (version, an invalid
kit's strike-through and problem, `+ Add kit`'s kits), so a chip's × no longer jumps when
Where changes; a failed ask drops that list. The phone UI test presses the × relative to
the button instead of page coordinates measured earlier.

## Rounds

1. Local, precision over `3e886a20..35844d51` and a check against the spec: both scenarios
   covered by code and tests, decisions D1–D3 kept, no scope creep. External 1, Claude
   Code GitHub Action (requested 20:45:11Z, finished 20:45:59Z): read the code, tests,
   CHANGELOG and `ui.md`, not openspec; no blocker. At `merge_ok` the human chose to fix F1
   by dropping the last list on a failed ask.
2. Local, precision on the delta `35844d51..97b4f635` (the fix of F1). No external round:
   the hotfix cap (1) was used in round 1.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | a failed ask of the next place's kit list left the chips and `+ Add kit` on the previous place's list beside the error; the spec and `ui.md` kept the list only while asking | fixed in `97b4f635` by the human's choice: a failed ask drops the last list; a vitest case, seen red on the old `Launch.tsx`; a new spec scenario |
| F2 | — | the test's mock of `GET /api/kits` is rewritten and not restored | refuted: `answers = {}` in `beforeEach` |

## Metrics

- Rounds: 2 local, 1 external, 0 stand-ins.
- Confirmed: 1 (F1, found both locally and externally).
- Refuted: external 1 (F2).
- Findings in code changed by the developer's cleanup lens: 0.

## Checks

- Round 2 at `97b4f635`: vitest `src/Launch.test.tsx` 245 passed; `make lint` clean;
  `uv run pytest -m ui tests/ui/test_launch.py -n 2` 48 passed; `openspec validate
  kit-chip-steady --strict` valid, the trial archive and `openspec validate --specs
  --strict` 87 passed. The new test failed on `Launch.tsx` of `35844d51`
  (`expected 'default 0.1.0×' to be 'default×'`).
- CI at `97b4f635`: 19 pass, `ci-ok` green; smoke skipped by the skip list.
- Not run locally: the full unit suite, integration, smoke and container (CI ran them).

## Found on the way

Nothing.

## Residual risk

- That the old phone test fails without the window's fix depends on the machine's load and
  was not shown; a press at 45×16 (past the hit area) was shown to fail.
- Round 2's delta was not read by the external reviewer.
- No change to `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
  `tests/live/`.
