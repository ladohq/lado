# LAD-252 ci-speedup-check: review report

Pull request #297 `fix/lad-252-ci-speedup-check` → `main`. Scale: tweak, depth precision. Head
reviewed: `2b89baf5`. A measurement of CI before and after its speedup of 2026-11-09 (LAD-248,
LAD-249, the GitHub Team plan, LAD-236): the script `docs/research/ci-speedup-check/measure.py`
(standard library, `gh` read-only) and the report `docs/research/ci-speedup-check.md`. Documents
only; no delta (`--skip-specs`).

## Rounds

1. Local, precision (`origin/main...bfd58964`). The diff read against the change's proposal and
   design, with git and GitHub; `measure.py` rerun on the window "after", its output equal to the
   report's line for line. Findings F1-F3; F4 refuted; F5 unverifiable.
2. Local, precision, on the delta `bfd58964..2b89baf5`, and external 1, Claude Code GitHub
   Action: F1-F3 fixed, no new local finding; the external round gave E1-E6. It read both risky
   files (`measure.py` and the report), not the openspec files.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | the report's CI history was wrong: PR numbers and merge times of LAD-248 (PR #263, 11:00 UTC), LAD-249 (PR #262, 12:25 UTC) and LAD-236 (13:04 UTC), and why the "before" runs were left out | fixed in `2b89baf5` and in the Russian artifact |
| F2 | minor | the Team conclusion said "0 % below 40 running"; 7 jobs (0.4 %) waited at 0-9 running | fixed in `2b89baf5` |
| F3 | minor | the smoke line did not name Codex (LAD-230) nor explain the step's growth date | fixed in `2b89baf5` |
| F4 | — | suspected: UI cells ended at 30 min under a 25 min limit | refuted: the check-run annotations say "exceeded the maximum execution time of 25m0s" |
| F5 | — | the comment on LAD-252 and the tasks LAD-279..281 | unverifiable by the reviewer (no tracker); residual risk |
| E1 | — | external: pull requests with the smoke skipped also skip other heavy jobs | refuted: in `ci.yml` only `smoke` has the condition |
| E2 | minor | external: the Docker cache's 14-16 s gain is a before/after difference, not cache against no cache | declined: the method is design D5; as an upper bound the conclusion "does not pay" holds |
| E3 | — | external: counting "20 or more running" mixes macOS with the Linux limit | refuted: GitHub's overall limit counts macOS jobs too |
| E4 | minor | external: explain the 30.0 min of a cell under a 25 min limit | declined: the line is right (F4) |
| E5 | — | external: `measure.py`'s retries stop on a secondary rate limit | refuted: the message contains "rate limit", so it retries |
| E6 | minor | external: with `--cache-dir` an empty log after 404/410 is cached for good | declined: a research script run by hand on closed windows |

## Found on the way

None.

## Checks

On `2b89baf5`:
- `measure.py` rerun on the window "after": output equal to the report's; "before" compared with
  the developer's raw output only.
- CI: 38 checks green, `ci-ok` success, the smoke skipped (only `docs/` and `openspec/` in the
  diff); the pull request `CLEAN`.

Not run: `make test` locally (no code in the diff; CI ran it); the window "before" again. No change
to `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or `tests/live/`.
