## Context

The whole design, with the report's shape and the policy checklist, is in
`docs/superpowers/specs/2026-11-11-test-audit-baseline-design.md`; the plan with the tests per
requirement in `docs/superpowers/plans/2026-11-11-test-audit-baseline.md`. This file holds the
technical decisions.

Facts measured on main 02767b42 (2026-11-11): `make test` 6 155 passed, 7 skipped in 65 s on 16
workers; the slowest unit test 20.1 s
(`tests/test_providers.py::test_a_claude_session_start_keeps_the_alias_s_source`: `hooks.handle`
waits the whole `MCP_READY_TIMEOUT` in `_wait_for_mcp`, 819 sleeps), then 4.7 s, 3.9 s, 2.7 s and
about twenty of 1–2 s. CI run 43090128867 on main: 8 min 34 s by the clock, 125 runner-minutes;
smoke macOS 8 min, UI shards 5–6 min, integration 4.5–6 min, unit 3.5 min, container 4–5 min,
`web` 2 min. mutmut 3.8.1 and pytest-cov 7.1.0 (coverage 7.17) are the current releases.

## Decisions

**D1. Two dev dependencies, no more.** `pytest-cov` gives per-test contexts (`--cov-context=test`)
and `mutmut` the mutation score; both only in the `dev` group. No pytest-randomly or
pytest-flakefinder: flakiness comes from CI's history of reruns (the review traps already rerun
red jobs) and from three local repeats of a layer, which need no package. Standard library for the
rest (AGENTS.md, Rules).

**D2. One script, `scripts/test_audit.py`, with subcommands.** `coverage`, `durations`, `flaky`,
`subsets`, `pseudo`, `mutation`, `prove`, `report`; each writes JSON to `--out` and `report` joins
them into Markdown. `scripts/` already holds the repository's tools as single files
(`check_groups.py`, `smoke_ci.py`); a package of modules is for LAD-276 to decide. `make
test-audit` runs `coverage`, `durations`, `subsets`, `pseudo` and `report`; `mutation` and `prove`
take module names and run by hand, as they take long. Not in `make check` and not in CI: the
audit measures, it gates nothing yet (proposal, Out of scope).

**D3. Coverage in the processes a test starts, by a static context from the environment.**
pytest-cov's test context exists only in pytest's own process, and its subprocess support is gone
since 7.0. The audit loads a plugin of its own (`-p`, only in its runs) that, per test, sets an
environment variable with the test's node id and lets coverage start in every Python process
through `COVERAGE_PROCESS_START` with a config whose static `context` reads that variable; the
child processes LADO starts (`interpreter.run_module`, the hooks, `lado mcp`, the server) inherit
it. Data files are combined at the end. Per-test attribution then holds across processes
(requirement "Per-test coverage of the unit, integration and UI layers"). The UI layer's server runs the same
way. Smoke, live and container are mapped by reading (D8).

**D4. Subsets per single test, siblings excluded.** A test is a candidate when its line set is a
subset of one other test's of the same layer; a union of several tests is not searched (the search
is exponential and Shi et al. show even single subsets are unsafe without mutants). Cases of one
parametrized function are not compared with each other: they run the same lines with other data,
which is the point of them. Equal sets list one pair once.

**D5. Pseudo-tested functions by our own extreme mutation.** For each function of the five core
modules: in a copy of the repository the body becomes `return None` (a generator: `return` then an
unreachable `yield`; `__init__` and properties alike), and only the tests whose context executed
the function run, `-x`, with `-n auto`. mutmut has no such operator; Descartes (Java) is the
method, written here from its description. A function no test executed is listed apart as not
covered.

**D6. mutmut on the unit layer, one module at a time, the strict proof.** `mutation <module>` runs
mutmut on that module with the unit tests (`-m 'not integration ...'`, as the default addopts) in
mutmut's own copy (`mutants/`, under `--out`, never the working tree). The integration and UI
layers are too slow per mutant; a mutant only they kill shows as survived, the same before and
after, so the comparison stays fair. `prove <before.json> <after.json>` passes only when no mutant
killed before survives after; equal scores with different mutants are not enough. The score is
killed / (killed + survived), a timeout counting as killed and a mutant without tests as survived.
Baseline in this pull request: the five core modules; each later batch measures its own touched
modules before (on its target) and after.

Changed in the build (the first baseline run lost eight hours of results): the modules run one
after another in one copy (`mutmut run 'lado.<module>.*'`, mutmut's two passes paid once), each
module's result written as soon as it is done and kept by a rerun at the same HEAD; an interrupted
module is written with `"stopped"`, its mutants not checked left out of the score. mutmut limits a
mutant's CPU time only, and a test waiting on a timeout of its own spends none (up to 2 146 s for
one mutant of `state.py`): under a mutant, a test still running after `--test-seconds` (60) ends
with mutmut's exit code for a timeout (`scripts/test_audit_deadline.py`), which counts as killed,
before as after a batch.

**D7. "Touched module" from the coverage, not from imports.** The modules of a batch are those
with a line that any deleted test executed (D3's records). A deleted test that executed none (a
test of README or a workflow file) rests on the checklist's rule, and the proof names it so.

**D8. The upper layers by a table, filled by reading.** For each test of smoke, live and container,
and for each UI test whose recorded lines (D3) are all executed by the unit or integration layer,
the report gives one row: what it checks, the lower test that checks the same (or none), and the
proposed verdict. Smoke, live and container need real CLIs or Docker and are not run by the audit.

**D9. The slow tests get the same check, faster.** A test that waits for a real timeout gets a
short one through the module's constant (monkeypatch, as other tests already do) or waits for the
event itself. Where a timeout is a local inside a function, it becomes a module constant or a
keyword argument with the same default: no behaviour change, no CHANGELOG item. The first case is
the 20 s test: its fixture records the `MCP_READY` event, or the test shortens
`hooks.MCP_READY_TIMEOUT`, whichever keeps what it checks (the model and its source). Every unit
test of 1 s or more in the baseline is sped up or named in the report with the reason it needs the
time (a shell script of `docker/` that waits by design).

**D10. The checklist lives in `docs/testing.md`.** One source of truth that agents already read
(AGENTS.md, Read more), and that LAD-276 packages; the report links to it and does not copy it. The
report itself goes to `docs/superpowers/reports/`, the archive's place for reports; the raw JSON
stays under `--out`, not committed.

**D11. No version change, merge after v0.46.1.** Dev dependencies, scripts, tests and docs: users
see nothing, so no CHANGELOG item and no bump. main is frozen at 0.46.1rc1, and
`scripts/release_check.py` refuses a final that differs from its RC in any of these files
(docs/release.md, section 6); the integrator merges only after the tag `v0.46.1` exists, merging
the new main in first (the human's answer #6085).

## Risks / Trade-offs

- **mutmut may not run on our suite** (its trampolines in a copy, our `conftest.py` isolation,
  tests that start `lado` as a subprocess, which would import the unmutated package). The first
  task of the plan is a trial on `lado/text.py`; when mutmut cannot give a score there, the
  developer reports `redesign` with the evidence, and the design changes the tool; no silent switch
  to another method.
- **Time.** mutmut on `runtime.py` (3 600 lines) may take hours. The baseline records each
  module's time; a module over two hours is reported with its time and measured on the functions
  the first batches touch, which the report names.
- **The goal's numbers are reached later.** This pull request deletes nothing; the counts fall
  only from batch 2 on. The report sets the baseline they are measured against.
