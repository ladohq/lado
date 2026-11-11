Task: LAD-275

## Why

LADO has 7 234 pytest tests (unit 6 162, integration 297, UI 628, the rest smoke, live and
container) and about 1 660 vitest tests; the Python test code is about 2.5 times the size of the
program's (96 000 lines against 39 000). Nobody can say which test checks what, or whether a test
would catch a bug: there is no per-test coverage and no mutation testing, so the question "is this
test needed" is answered by eye. The research behind the task (session artifact
`test-audit-research`, also attached to LAD-275) found about 30 files (≈8 500 lines) that test
documents, CI and scripts rather than the program; many tests that compare exact phrases of
prompts and documents ("change detectors"); partial duplicates between unit and integration; and
tests that wait for real timeouts, `tests/test_providers.py::test_a_claude_session_start_keeps_the_alias_s_source`
20 s for a body of seven lines.

Root cause: the suite grew one test per change with no measure of what a test adds, and the rule
"the lowest layer that can catch the bug" (AGENTS.md, Testing) has no tool that shows where a
check already exists. Deleting by coverage alone is unsafe: Shi et al. (ISSTA 2018) found that
coverage-only reduction missed up to 52% of real broken builds. So each deletion needs proof that
the suite still kills the same mutants.

Options weighed:

- A (taken, the human's answers #6081, #6085): measure first, then delete in batches. This pull
  request brings the tools (per-test coverage, mutmut, the report's scripts), the baseline report
  with the numbers "before", the policy checklist, and speeds up the tests that wait for real
  timeouts; it deletes nothing. Later pull requests of the same task (each a pass of the flow
  `task` over LAD-275) delete or move tests one category at a time, each with the mutation proof,
  on candidates the human approves from the report. Long-term cost: two dev dependencies and one
  script of a few hundred lines, which LAD-276 (kit test-audit) packages from what worked.
- B: one pull request that measures and deletes everything. Thousands of deletions in one diff
  cannot be reviewed, and the human would decide on candidates before the measurement exists.
  Rejected.
- C: delete by reading, without tools. It repeats the cause (decisions by eye) and leaves LAD-276
  nothing proven to package. Rejected.

## What Changes

- Dev dependencies `pytest-cov` and `mutmut` (pyproject.toml's `dev` group, uv.lock).
- `scripts/test_audit.py` (new): the audit's commands: per-test coverage of the unit, integration
  and UI layers (in-process and in the processes a test starts); durations and flakiness per
  layer, locally and from CI's history; subset candidates; pseudo-tested functions of the core
  (extreme mutation); the mutation baseline of a module and the proof that a batch of deletions
  lost no killed mutant. `make test-audit` runs it; it is not part of `make check` or CI.
- Unit tests of the script's logic (`tests/test_test_audit.py`).
- The baseline report `docs/superpowers/reports/2026-11-11-test-audit-baseline.md`: the numbers
  "before", the candidates per category with a proposed verdict each, the duplicates map of the
  UI, smoke, live and container layers, the vitest measurements, and the proposals left to
  LAD-276.
- `docs/testing.md`: a section "Test audit" (the tools and how to prove a deletion) and the
  checklist "Which tests we keep", the policy that later batches and LAD-276 follow.
- The tests that wait for real timeouts of 1 s or more get a short timeout or an event instead;
  the first is the 20 s test, which waits for `hooks._wait_for_mcp`'s `MCP_READY_TIMEOUT`.
- Capability `test-audit` (new): what the tools measure and when a deletion counts as proven.
- No CHANGELOG item and no version change: users of LADO see nothing; `src/` changes only where a
  timeout must become a parameter to be shortened in a test, without a change of behaviour.

## Scope

- Python tests of every layer: measured; the unit, integration and UI layers per test, the smoke,
  live and container layers by reading (they need real CLIs or Docker).
- vitest: durations and the inventory of change detectors in the report only.
- This pull request deletes no test; a slow test is rewritten to the same check, faster.
- Merge after the final 0.46.1 (`v0.46.1` tagged): main is frozen at 0.46.1rc1, and a final that
  differs from its RC in tests, scripts, docs or pyproject.toml is refused (docs/release.md,
  sections 3 and 6); the build, review and CI go on before it (the human's answer #6085).

## Out of scope

- Deleting tests: the later pull requests of LAD-275, one category each, after the human approves
  the candidates of this report.
- Deletions of vitest tests: no mutation proof for TypeScript without Stryker; Stryker is
  LAD-276's or a task of its own to decide on this report.
- Size markers with a time budget per test, provider contracts instead of part of smoke and live,
  mutation testing in CI: proposals in the report, decided in LAD-276 or tasks of their own.
- Removing dead code found by vulture: a section of the report only; removing code is not a test
  audit.
- Speeding up CI's wall clock: it is set by the smoke on macOS (≈8 min, the real CLIs) and the UI
  shards (≈6 min), which the audit does not touch; the target is the runners' minutes and the local
  `make test`.

## Impact

- Developers: `make test-audit` and the checklist; `uv sync` installs two more dev packages.
- CI: unchanged in this pull request.
- The task's goal, reached by its last pull request and measured against this report: pytest tests
  −15% or more, local `make test` −25% or more, the runners' minutes of a CI run on main −10% or
  more, and on every module a batch touches no mutant killed before survives after.
- The release: this pull request waits for `v0.46.1`.
