# LAD-280 smoke-parallel-workers: review report

Pull request #300 `fix/lad-280-smoke-parallel` → `main`. Scale: tweak, depth precision. Head
reviewed: `d725b024`. A smoke cell (`scripts/smoke_ci.py run`) runs its tests on three
pytest-xdist workers with work stealing (`-n 3 --dist worksteal`) on Linux, macOS and the
Windows probe's WSL part; `make test-smoke` stays serial. The macOS cells, which set a pull
request's wait for CI (LAD-252), went from 396-424 s of test step to 126-262 s at the median.

## Rounds

1. Local, precision (`origin/main..7a485817`: spec, tests, comments, general), and external 1,
   Claude Code GitHub Action. No blockers; no state shared between xdist workers; the pass
   rule reads xdist's output correctly. Converged with four minor findings declined.
2. Back from the merge gate: the human asked to fix F1 and F2. Local, precision
   (`7a485817..d725b024`: `fbf19c17` and the merge of `main` with LAD-279 and LAD-281, no
   conflicts). No new findings. No external round: the tweak's cap of 1 was used, the delta is
   text only.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | `docs/testing.md` and the script's docstring said the step lasts about the longest test (~155 s); measured, claude's median is 262 s | fixed in `fbf19c17`: the longest test plus each worker's cold CLI start, 252-284 s against 409 s |
| F2 | minor | the proposal's AC-3 called 396-424 s `main`'s fastest steps, against its own table (kilo 251, codex 260) | fixed in `fbf19c17`: 396-424 s is claude's and opencode's step by LAD-252, kilo and codex named apart; the human's threshold unchanged |
| F3 | minor | external: a paragraph of `docs/testing.md` wrapped unevenly | fixed in `fbf19c17` |
| F4 | minor | external: the spec's scenario "Run by hand" (`make test-smoke` with `-n0`) has no test | declined: the Makefile did not change and matches the spec |
| F5 | — | external: state of the real CLIs outside a test's home under three workers | residual risk: no shared writable path found; five green CI runs |
| F6 | — | the Windows probe runs the same `smoke_ci.py run` | checked: probe 43622342944, WSL smoke on three workers 4/4 green |

## Spec check

- ADDED "A smoke cell runs its tests on three workers": `smoke_ci.run` hands `cell` the
  command of the requirement, pinned by `tests/test_smoke_ci.py`; `make test-smoke` keeps `-n0`.
- AC-1 to AC-4 met; AC-3 as the human set it on 2026-11-14 (medians 262 / 251 / 208 / 136 s,
  maximum 373 s). `ci.yml` untouched.

## Found on the way

None.

## Checks

On `d725b024`:
- `make lint`: clean.
- `uv run pytest tests/test_smoke_ci.py tests/test_ci_workflow.py tests/test_agents_md.py -n
  auto`: 139 passed.
- `openspec validate smoke-parallel-workers --strict` valid; specs 83/83. The developer:
  `make test` 6118 passed, 7 skipped, 1 failed (`test_temp_dirs[shell]`, red on `main` too).
- CI run 43622349434: success; macOS smoke step claude 262, opencode 250, kilo 126, codex
  141 s.
- Windows probe 43622342944: success.
- Flakes that passed on a rerun of the failed jobs:
  `test_session_start::test_an_approved_proposal_starts_an_independent_session_with_the_brief`
  (integration 3.10/1) and
  `test_flow_runs::test_the_humans_files_with_a_gates_answer_reach_the_next_steps_worker`
  (probe, WSL); unrelated to the change.

Not run locally: the smoke tests (they need the real CLIs; CI ran them). No change to
`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or `tests/live/`.

## Residual risk

The smoke's stability on macOS's three cores rests on CI runs only (five green; opencode's
step spread 137-373 s across runners).
