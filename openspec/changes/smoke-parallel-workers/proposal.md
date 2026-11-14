Task: LAD-280

## Why

The macOS smoke cells set a pull request's wait for CI: they end 69 % of green pull
request runs at 7.3-7.5 minutes, while a pull request that skips the smoke waits 6.7
minutes at the median (`docs/research/ci-speedup-check.md`, LAD-252). Their test step grew
from 82-88 s to 396-424 s on 2026-11-08 with the smoke tests of LAD-217, LAD-220 and
LAD-230.

Root cause, from the step logs' timestamps per test (push run 43399183470 on `main`,
2026-11-13):

- `claude` (401 s on macOS): two cases of
  `test_a_provider_s_refusal_ends_a_claude_agent_s_turn_within_its_repeats` take 237 s,
  `[401]` 155 s and `[429]` 82 s: Claude Code's own backoff between the up to 7 repeats
  LADO allows it. Linux takes as long (158 s, 83 s); it is the CLI's wait, not the system.
  The other 19 tests take 4-12 s each.
- `opencode` (~420 s) and `kilo`: no long test; each of 14 tests takes about twice as long
  on macOS as on Linux (20-44 s against 11-24 s), the CLI's start.
- The first test of each macOS cell takes 59-85 s (the CLI's first run on the machine).

The cell runs its tests one at a time (`pytest -n0`) although each smoke test is already
isolated: its own `HOME`, `XDG_*`, CLI config folder, `LADO_HOME`, tmux server and fake
server on a free port. Most of the step is waiting, not CPU.

Options considered:

1. **Parallel workers in each cell** (chosen): `-n 3 --dist worksteal`. Same cells, same
   runners, the same tests on every pull request. Expected step: claude about 3 minutes
   (bound by the 155 s case), opencode about 3-3.5. Long-term cost: a smoke failure under
   load is possible on macOS's 3 cores; the tests' waits (120 s for an idle supervisor)
   are far above today's slowest start (85 s).
2. A second macOS cell per provider: 4 more macOS jobs per run. GitHub's macOS supply is
   the scarce one (5 concurrent by its table; macOS cells are the ones cancelled with "not
   acquired by Runner"; macOS queue p90 ~220 s), so the queue would eat the gain.
3. Claude's refusal cases on Linux only: −237 s on claude macOS, but macOS loses the
   check and opencode's 420 s stays.

## What Changes

- A smoke cell (`scripts/smoke_ci.py run`) runs its tests on 3 pytest-xdist workers with
  work stealing: `uv run pytest -m smoke -n 3 --dist worksteal -v -k <provider>`, on Linux
  and macOS alike, and in the Windows probe's WSL part, which runs the same command.
- `make test-smoke` stays serial (`-n0`): a person runs it to debug one CLI.
- The cell's pass rule, log, evidence and artifact are unchanged.
- `docs/testing.md` and `smoke_ci.py`'s docstring say the new command;
  `tests/test_smoke_ci.py` pins it.

## Scope

In: the smoke cell's pytest command, its unit test, the docs that state it, the
continuous-integration spec.

Out of scope:

- `.github/workflows/ci.yml`: unchanged (no new cells, no matrix change); LAD-279 edits
  the same file.
- Shortening Claude Code's backoff or LADO's `CLAUDE_CODE_MAX_RETRIES` of 7: that is the
  product's setting the test checks, not a test cost.
- Moving tests between systems (option 3) or adding macOS cells (option 2): see Why.
- The live cells (`smoke_ci.py live`) and the container cells: not on the critical path;
  the live cell talks to a paid model and stays serial.
- The integration cells' growth of about a minute (LAD-252): not on the critical path.

## Acceptance

- AC-1: `scripts/smoke_ci.py run <provider>` runs `uv run pytest -m smoke -n 3 --dist
  worksteal -v -k <provider>`; a unit test pins the command; the pass rule is unchanged.
- AC-2: three CI runs of the branch in a row run every smoke cell green (8 cells each),
  with the same number of tests passed per cell as on `main` (claude 21, codex 16,
  opencode 14, kilo 14) and no skip.
- AC-3: in those runs, the test step of each macOS smoke cell takes at most 3.5 minutes.
- AC-4: `make test-smoke` still runs serially; `docs/testing.md` and the script's
  docstring state both commands.

## Impact

- `scripts/smoke_ci.py`, `tests/test_smoke_ci.py`, `docs/testing.md`.
- No change users of LADO see: no CHANGELOG line, no version bump of its own (CI only).
