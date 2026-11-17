# Test audit: research and staged plan

Started 2026-11-12 on the human's request: are all of LADO's tests useful, which ones can be
removed or merged, and how other projects answer the same question. The goal is fewer
tests that check as much: the number of tests, not their speed; a faster run is a side
effect. This file
is living: the research (sections 2-3) stays as written, the plan (section 4) and the log
(section 6) are updated after each stage with its status, its numbers and the decisions
taken. Each stage is its own pull request and leaves `make check` green.

1. [Where we start](#1-where-we-start)
2. [How other projects audit tests](#2-how-other-projects-audit-tests)
3. [The approach chosen for LADO](#3-the-approach-chosen-for-lado)
4. [The staged plan](#4-the-staged-plan)
5. [Rules for removing a test](#5-rules-for-removing-a-test)
6. [Results log](#6-results-log)
7. [Sources](#7-sources)

## 1. Where we start

Measured on main at `02767b42` (2026-11-12). The test counts are pytest's collection
(parametrized cases counted one by one), the vitest count is the number of `it(`/`test(`
calls.

| Layer | Tests | Lines of test code | Where it runs |
|---|---|---|---|
| Unit (`tests/`) | 6162 | ~68 700 | `make test`, CI on every push |
| Integration (`tests/integration/`) | 297 | ~10 300 | CI, 3 shards per Python |
| UI e2e (`tests/ui/`, Chromium) | 628 | ~17 100 | CI, 4 shards, 25 min limit each |
| vitest (`web/src/**/*.test.*`) | ~1660 | ~31 000 | `make web` |
| Container (`tests/container/`) | 61 | ~2 300 | CI, 2 shards per arch |
| Smoke (`tests/smoke/`) | 30 | ~1 300 | CI |
| Plugin (`tests/js/`) | 39 | ~550 | `make test-js` |
| Live (`tests/live/`) | 6 | ~1 100 | weekly and by hand |

The code under test is ~38 600 lines of Python (`src/`) and ~30 100 lines of TypeScript
(`web/src`, without tests and `api.gen.ts`): about **130 000 lines of tests for 69 000
lines of code**, close to two to one. There is no right ratio, but this one, reached in six
weeks and ~3600 commits written mostly by agents, makes overlap likely: an agent tends to
add a test for each fix and rarely removes the one it made redundant.

What stands out before any measurement:

- **Big files.** `test_runtime.py` (7458 lines), `test_cli.py` (3754), `test_state.py`
  (3202), `test_providers.py` (2562), `test_model_settings.py` (2395). `test_runtime.py`
  was also the test file changed most often in the last months (156 commits).
- **Tests of file texts.** 59 unit test files call `read_text()` and 51 name a document or
  a workflow file (`docs/`, `.md`, `.yml`): e.g. `test_docker.py` (94 tests),
  `test_install_sh.py` (81), `test_ci_workflow.py` (35). Some guard a real invariant (the
  200-line limit of AGENTS.md), others may only repeat the wording of a file and break on
  every edit of it.
- **The expensive layer is large.** 628 browser tests take 4 CI shards of up to 25 minutes.
  The web UI has ~1660 vitest tests besides; part of the browser layer likely checks what
  vitest already checks.
- **No history is kept.** CI keeps no junit reports, so we cannot tell which tests ever
  failed, which are flaky and how their duration changes.

## 2. How other projects audit tests

### 2.1 Coverage, per test

A coverage report says which lines run; with *dynamic contexts* (`coverage.py`,
`pytest --cov-context=test`) it also says **which tests** run each line. That gives two
kinds of candidates:

- a test whose lines and branches are all covered by other tests (no unique coverage);
- groups of tests with near-identical traces (likely copies of one another).

Coverage is a cheap filter, not a verdict. Running a line is not checking it: research on
real projects (Inozemtseva and Holmes, 2014) found that coverage is only weakly related to
how many faults a suite finds once the size of the suite is accounted for. A test with no
unique lines may still be the only one that checks a value; a test with many unique lines
may assert nothing. Coverage also finds the opposite problem: code no test runs.

For LADO, the UI and integration tests start `lado server`, `lado mcp` and hooks as
separate processes; their coverage needs `coverage.py`'s subprocess support
(`COVERAGE_PROCESS_START`). vitest has its own coverage (`@vitest/coverage-v8`).

### 2.2 Mutation testing

The standard answer to "does this test do its job". A tool makes small changes to the code
(a *mutant*: `<` becomes `<=`, a `return x` becomes `return None`, a condition is negated),
runs the tests against each, and reports which mutants **survived**: no test failed.

- A survivor marks code the tests run but do not check: a weak assertion, a missing case.
- The mutants each test kills show what it adds; a test that kills nothing no other test
  kills adds nothing to fault detection.

Google runs it on code review at scale (Petrović and Ivanković, 2018; Petrović et al.,
2021): not on the whole codebase, only on changed lines, with mutants that are known to be
noise filtered out, and found that engineers act on the survivors. The cost is the main
limit: every mutant is a test run, so one runs it per module, with fast unit tests, and
caches results. Tools: `mutmut` and `cosmic-ray` for Python, Stryker for TypeScript.

### 2.3 Test suite minimization

A classic research problem (Yoo and Harman's survey, 2012): find the smallest subset of a
suite that keeps the same requirements satisfied, usually branch coverage or killed
mutants. It is a set-cover problem, solved well enough greedily: take the test that covers
the most not-yet-covered items, repeat. The tests left out are candidates to remove or to
merge. The survey also warns that a suite minimized on coverage alone can lose fault
detection, which is why the requirement should include mutants.

### 2.4 History: failures, flakiness, churn

What the test results say over time:

- **Duration** (`pytest --durations`, junit reports): where the time goes. Usually a few
  percent of the tests take most of it, often through sleeps, timeouts and heavy fixtures.
- **Flakiness**: tests that fail and pass on the same commit cost trust and reruns (Luo et
  al., 2014; Google's account of flaky tests, 2016).
- **Never failed vs. always edited.** A test that never failed in months may be cheap
  insurance or may check nothing; a test edited in almost every change of its code is a
  *change-detector test*: it breaks on any edit, real bug or not, and its fixing becomes
  routine (Google Testing Blog, 2015). Both need the history CI does not keep yet.

### 2.5 The test pyramid, applied backwards

The pyramid (Cohn; Vocke's "Practical Test Pyramid", 2018; Software Engineering at Google,
chapters 11-14) says: many fast small tests, fewer large ones, and test each behaviour at
the lowest level that can catch its bugs. LADO's AGENTS.md has this rule for new tests.
Audits apply it to existing ones: for each large test (browser, integration), ask whether
a smaller test catches the same bug; if one exists, the large test goes; if not, it may
move down.

### 2.6 Test smells

Catalogues of bad test patterns (van Deursen et al., 2001; Meszaros, 2007; the tsDetect
study of Peruma et al., 2020) that a script or a reviewer finds without running anything:

- no assertion, or one that cannot fail (`assert x is not None` on a constructor);
- the test checks its own mocks rather than the code;
- the test repeats the implementation (computes the expected value the same way);
- the test copies a text (a document, a message) instead of checking a property of it;
- several tests that differ only in data, not merged with `parametrize`;
- sleeps and wide timeouts standing in for waiting on an event.

## 3. The approach chosen for LADO

No single method is enough; they work as a funnel:

1. **Measure first** (durations, per-test coverage, a history of CI results) to see where
   the cost and the overlap are, without changing a test.
2. **Cheap filters find candidates**: no unique coverage, smells, text-copying tests,
   browser tests with a vitest twin.
3. **Mutation testing decides** for the modules where it is affordable: a candidate is
   removed only if the module's killed mutants stay the same (section 5).
4. **One file or one topic per pull request**, so each change is small to review and easy
   to revert, and the numbers before and after go into the log (section 6).
5. **Guardrails** stop the suite from growing back the same way.

## 4. The staged plan

Status: stage 0 done (2026-11-13), stage 1 under way (section 6). Reordered after stage 0 on
the human's word (2026-11-13): every stage cuts the number of tests, starting where stage 0's
numbers already name the candidates; speed is no stage of its own. Reordered again the same
day: mutation testing first, module by module, because only it tells a copy from a test
that checks another result of the same path (stage 0 found both among identical
footprints); the tests that stay are then merged into tables (stage 2).

### Stage 0. Baseline measurements (no test changes)

**Why.** Every later decision needs numbers; without them we would remove tests by feel.

**What.**
- Durations of every layer: `pytest --durations=0 --junitxml` for unit, integration and UI;
  vitest's reporter for the web UI. Total time per layer, top 50 slowest tests.
- Per-test coverage: `pytest-cov` with `--cov-context=test` and branch coverage for unit
  and integration; UI tests with subprocess coverage of `lado server`; vitest coverage.
- A script (in `scripts/`, or kept out of the repo if it is one-off) that reads the
  coverage database and lists: tests with no unique line or branch, clusters of tests with
  near-identical traces, modules and functions no test runs.
- CI uploads junit reports as artifacts from now on, so that stage 1 onwards can read
  failures and flakiness over weeks.

**Result.** The numbers in section 6, a list of candidates per layer, the CI change.

**Risk.** None for the product; coverage slows the runs it measures, so it is not added to
`make check`.

**How to measure** (the numbers of section 6 come from these). Two coverage configs of
their own outside the repository: `$DIR/rc` for pytest's own processes, and `$DIR/sub.rc`
for every process they start (`lado mcp`, hooks, the session loop, `lado server`, the
fake agent, a script run as a command), which coverage.py's `.pth` hook reads at each
start where `COVERAGE_PROCESS_START` names it:

```ini
# $DIR/rc
[run]
branch = true
source_pkgs = lado
source = scripts
parallel = true
data_file = $DIR/.coverage
core = ctrace

# $DIR/sub.rc: the same, but
data_file = $DIR/sub/.coverage
sigterm = true
context = ${LADO_TEST_ID}
```

- `core = ctrace` (and `COVERAGE_CORE=ctrace`) is required: from Python 3.14 coverage.py's
  default core is `sysmon`, which records no per-test contexts.
- `context = ${LADO_TEST_ID}`: a subprocess's static context is the test that started it
  (tests/conftest.py puts the test's node id in the environment while it runs); without it
  everything the subprocesses ran counts for no test. `patch = subprocess` is not enough:
  it hands the subprocesses the parent's context, the empty one.
- `sigterm = true` keeps a process stopped by SIGTERM; one killed otherwise (tmux's
  kill-server) leaves an empty file, skipped.

Then:

```sh
COVERAGE_CORE=ctrace COVERAGE_PROCESS_START=$DIR/sub.rc uv run pytest -n auto \
  --cov --cov-config=$DIR/rc --cov-context=test --cov-report=   # -m integration, -m ui
cp $DIR/.coverage $DIR/sub/.coverage.main
uv run coverage combine --data-file=$DIR/sub/.coverage $DIR/sub
uv run python scripts/test_audit.py $DIR/sub/.coverage --functions
```

Durations: `pytest --durations=0 --junitxml=...`; vitest:
`npm install --no-save @vitest/coverage-v8@<vitest's version>`, then
`npx vitest run --coverage --reporter=junit --outputFile=...`. Before the UI layer, rebuild
the bundle (`cd web && npm run build`): `src/lado/server/static` from an older `web/src`
fails a third of the browser tests.

### Stage 1. Mutation testing, module by module

**Why.** Coverage says which tests run a line, not which of them would notice it broken:
stage 0's identical footprints are copies in some files and tests of different results in
others (the Codex config tests read different keys of one config). Mutation testing (2.2)
answers it: a test that catches no bug some other test does not catch is a copy, whatever
it runs.

**What.** `scripts/mutants.py run` on one module of `src/` (the module's docstring has the
mutants and how each one's tests are chosen), then `scripts/mutants.py removable` on its
test file: the tests that go one by one, the weakest first, with no killed mutant and no
branch losing its last test. Section 5 then applies to each: a test written for a bug
(its task in the tracker is a bug) stays, a test written with a feature goes on the
mutation data. Modules in the order of stage 0's overlap: `providers/codex.py` first, then
`runtime.py`, `state.py`, `model_settings.py`, `cli.py`. After the removal, every mutant a
removed test killed is run again against the tests that remain.

**Result.** Per module: mutants, killed, survived; tests of the file before and after; the
tests kept for a bug; the recheck.

**Cost.** A mutant in a function's body runs a few tests, seconds; one at import time (a
constant) runs every test of the module, minutes. `providers/codex.py` (967 mutants) took
about four hours on four to six jobs. A module most of the suite runs needs `--judge` and
`--enough` (part 2), and the modules its test file covers most are run with the same judge.

### Stage 2. Tables of the checks that stay

**Why.** Stage 0 found 201 groups of unit test functions (514 functions) that take exactly
the same branches. After stage 1 those left check different results; many still differ only
in data and read best as one table.

**What.** Group by group, after the module's stage 1: tests that differ only in their input
and expected result become one `parametrize`d test; tests that check different things on
the same path stay as they are. The count of test functions drops; the checks do not.

**Result.** Per pull request: test functions and lines before and after, branch coverage
and killed mutants before and after (neither may drop).

### Stage 3. Tests of files that are not Python

**Why.** 408 unit test functions run no code of `src/lado` or `scripts/` of their own: they
check the Dockerfile, the installers, the workflows and documents, often by their exact
text. Such tests break on every edit of the file and rarely find a bug: they are change
detectors (2.4). Mutation testing cannot judge them: they run no code.

**What.** File by file, biggest first (`test_docker.py` 88, `test_install_sh.py` 80,
`test_ci_workflow.py` 36, `test_windows_shell_workflow.py` 32, `test_smoke_ci.py` 25, ...).
Sort each test into:
- **keep**: it guards an invariant (AGENTS.md's 200 lines, a CI step that must exist, a
  security setting of the image, a link that must resolve);
- **merge or rewrite**: the invariant is real but checked through exact text or spread
  over several tests; one test checks the property (parse the YAML, check the key, not the
  line);
- **remove**: it only repeats the file.

**Result.** Per file: the count of each kind, tests before and after; a rule for
docs/testing.md on what such tests may check.

### Stage 4. The big unit files

**Why.** The five largest files hold a third of the unit test code; they are where copies
and near-copies collect, and stage 1 reaches them module by module.

**What.** What stage 1 and 2 leave in `test_runtime.py` (416 of 489 functions with no
unique branch), `test_state.py`, `test_model_settings.py`, `test_providers.py`,
`test_cli.py`: the tests of several modules at once, which one module's mutants do not
judge. Run `scripts/mutants.py` on each module they reach, join the kill matrices, then
`removable`.

**Result.** Per file: tests and lines before and after, branch coverage and killed mutants
before and after (both must not drop).

### Stage 5. The browser layer and the pyramid

**Why.** 628 browser tests beside 1 914 vitest tests of the same components; a browser test
that checks what vitest already does is a copy at the highest price.

**What.** Map the 628 UI tests to the vitest tests of the same components. A browser test
that only checks the rendering or the logic of one component, already checked by vitest,
is removed; one that checks what vitest does not is moved to vitest where a browser is not
needed. The browser keeps whole journeys across the server and the UI: launching a
session, chat, artifacts, flows, logins. The same question for integration tests with a
unit twin.

**Result.** UI tests and CI time before and after; the list of journeys kept.

### Stage 6. Guardrails

**Why.** Without rules the suite grows back the same way.

**What.**
- docs/testing.md: when a new test is not needed (an existing one already fails on the
  bug), `parametrize` over copies, remove the test a change makes redundant, what tests of
  file texts may check (stage 2).
- A count of the tests per layer in CI's summary, so that growth shows in every run.
- Optionally, mutation testing of the changed modules (nightly or on demand), if stage 1
  shows it is affordable.

**Result.** The rules merged; the count in CI.

## 5. Rules for removing a test

A test is removed only when all of these hold:

1. Another test fails on the same bug: shown by per-test coverage (the lines and branches
   are covered elsewhere) and, where mutation testing ran, by the module's killed mutants
   staying the same without it.
2. It does not guard a reported bug that the remaining tests would miss; check `git log`
   of the test for a task id (LAD-...) and read the task. A test whose task is a bug
   stays even when mutation testing finds it a copy: its mutants are a sample, the bug was
   real. A test written with a feature has no such claim.
3. It does not check a property stated in docs/design or openspec/specs that no other test
   checks.
4. Its subject is not code the mutants cannot change finely: SQL in a string (a schema, a
   migration step, a constraint, a trigger) is mutated only as a whole string, which breaks
   everything at once; a wrong default or a missing `REFERENCES` is never made. Tests of
   such code stay whatever the mutation data says.
5. Its subject is not the layout: a browser test of sizes, positions, scrolling, the
   width of the window or computed styles stays whatever the mutation data says. Stryker
   does not mutate CSS and vitest runs in jsdom, which lays nothing out, so neither can
   show that another test fails on a layout bug. The same holds for what only a real
   browser does (a selection, the focus moving as an element hides).
6. The pull request lists each removed test with its reason, and the numbers before and
   after go into section 6.

When unsure, keep the test, mark it in the log and come back with mutation data.

## 6. Results log

One entry per stage: date, pull request, what was done, numbers before and after, the
decisions taken, what changed in the plan.

### Stage 0, part 1 (2026-11-12, branch `chore/test-audit-stage-0`)

Measured on a MacBook Air (8 CPU, macOS, Python 3.14), main at `02767b42`.

**Done.**
- CI keeps each unit, integration and UI cell's junit report for 90 days, also of a red
  run (artifacts `junit-unit-*`, `junit-integration-*`, `junit-ui-*`).
- `scripts/test_audit.py`: the numbers below from a coverage database measured per test;
  `pytest-cov` in the dev dependencies.

**Durations** (`-n auto`, 8 workers):

| Layer | Tests | Wall time | Sum of the tests' times | Where the time goes |
|---|---|---|---|---|
| Unit | 6162 | 2 min 57 s | 1 269 s | spread: top 50 tests 12%, top 300 33%; 1863 tests under 10 ms |
| Integration | 297 | 4 min 43 s | 2 152 s | top 10 15%, top 30 31%; the slowest 69 s (a secret canary) |
| UI | 628 | 14 min 46 s | 7 030 s | median 10.3 s a test, top 100 only 28%: each test's own setup costs, not a few slow ones |

The slowest unit tests: one of 20 s (`test_providers::test_a_claude_session_start_keeps_the_alias_s_source`),
`test_install_sh` 129 s in all. The costliest UI files: `test_phone` (76 tests, 965 s),
`test_session_head` (663 s), `test_launch` (656 s), `test_narrow_layout` (43 tests, 499 s):
the phone and narrow layouts alone are ~1 500 s.

**Unit coverage per test** (branches, the cases of a parametrized test as one test):

| | Value |
|---|---|
| Coverage of `src/lado` (lines and branches) | 96%; lowest `terminal.py` 55%, `server/run.py` 81%, `images.py` 81% |
| Test functions | 4 361 (6 167 cases) |
| Branches run | 26 364 |
| A greedy cover of every branch | 1 205 functions (28%) |
| Functions with no branch no other runs | 3 502 (80%) |
| Groups of identical footprints | 187 groups, 1 055 functions |

How to read it:
- The suite covers the code densely and overlaps itself heavily: a quarter of the test
  functions run every branch the whole suite runs. Running a branch is not checking it, so
  this is where the overlap is, not how much can go; mutation testing (stage 3) decides.
- One "identical" group is 581 functions that run almost nothing of `src/lado`: the tests
  of `scripts/`, workflows, the Dockerfile and the installers (`test_docker` 94,
  `test_install_sh` 81, `test_rc_check` 69, `test_smoke_ci` 48, `test_ci_workflow` 36,
  `test_windows_shell_workflow` 34, ...). Coverage of `lado` cannot judge them; they are
  stage 2's.
- The other 186 groups (474 functions) are the first real candidates: tests that take the
  very same branches, e.g. `test_codex.py` (12 functions in one group, 8 in two others),
  `test_cli.py::test_source_commands_are_not_under_kits` and 7 more.
- Most functions with no unique branch are in the big files (stage 4): `test_runtime.py`
  405 of 480, `test_state.py` 194 of 204, `test_model_settings.py` 173 of 198,
  `test_providers.py` 153 of 179, `test_cli.py` 125 of 219, `test_codex.py` 123 of 155.

**What the measurements found besides.**
- Locally (macOS 27, Python 3.14) 15 tests failed on main, every time, that pass in CI,
  which ran on Ubuntu with Python 3.10 and 3.13 only. Fixed in PR #295 (branch
  `fix/python-3.14-and-macos-tests`): a real bug of `clone.check_target` on Python 3.14
  (`Path.exists()` no longer raises for a folder that cannot be read, 2 tests); a test that
  read the developer's `~/.local/state/opencode` (every unit test now has an
  `XDG_STATE_HOME` of its own); a test that did not pin its platform; 2 tests of names that
  are no UTF-8, which APFS refuses (skipped there); the 5 tests of
  `test_leftover_processes`: macOS 27 shows no process's environment, so the leftover
  check found nothing, silently (now said once per run, and those tests skip). CI's unit
  tests run on 3.10 and 3.14 since. Not fixed: 4 UI layout tests that expect exact text
  widths fail on macOS fonts, serially too (stage 5).
- Load makes tests flaky: of the 20 UI tests that failed with 8 workers, 16 passed serially;
  under coverage 1 more unit and 3 more integration tests failed;
  `test_session_loop::test_the_loop_types_a_swallowed_message_again` and
  `test_model_servers::test_a_post_that_never_answers_is_neither_proven_nor_missing` fail
  now and then under load and pass alone. CI's 2 UI workers are not a whim.
- Coverage costs ~75% more time (unit: 5 min 10 s instead of 2 min 57 s) and a 163 MB
  database.

### Stage 0, part 2 (2026-11-13): the subprocesses, the UI, vitest, `scripts/`

Part 1's numbers missed what tests run in other processes: those ran under the empty
context and counted for no test. Measured again with the subprocesses' context set to their
test (`context = ${LADO_TEST_ID}`, the method above), `scripts/` included. Coverage of
Python per test, by test function:

| Layer | Functions | Coverage of `src/lado` (+ `scripts/`) | Branches run | Greedy cover | No unique branch | Identical groups |
|---|---|---|---|---|---|---|
| Unit | 4 374 | 95% | 33 956 | 1 307 (30%) | 3 434 (79%) | 202 groups, 922 functions |
| Integration | 286 | 65% | 25 398 | 144 (50%) | 159 (56%) | 8 groups, 22 functions |
| UI (server side only) | 491 | 57% | 23 049 | 111 (23%) | 414 (84%) | 36 groups, 109 functions |

vitest: 1 914 tests, all passed, 4 min 31 s of tests in 1 min 51 s; coverage of `web/src`
96% of statements, 92% of branches (lowest `SelectionBar.tsx` 58%, `waiting.ts` 63%).
`Launch.test.tsx` alone takes 107 s of the 270 (40%). v8 coverage gives no per-test
contexts, so vitest's overlap is not measured.

How to read it:
- **Unit holds the overlap.** With the subprocesses counted the numbers hardly move (30%
  of the functions run every branch; 79% run none of their own). The biggest files are
  where it is: `test_runtime.py` 416 of 489 functions with no unique branch,
  `test_state.py` 194 of 204, `test_model_settings.py` 173 of 198, `test_providers.py`
  153 of 179, `test_cli.py` 125 of 219, `test_codex.py` 123 of 155. Stage 4's order holds.
- **Integration earns its keep.** Half its functions take a branch no other does, and only
  22 functions share a footprint. Its candidates are few: `test_session_loop.py` (14 of
  15 with no unique branch), `test_agents.py` (20 of 30).
- **The UI numbers are about the server only.** A browser test checks mostly React code,
  which Python coverage does not see; 84% with no unique server branch says the server
  side of the UI tests overlaps, not that the tests do. Comparing UI tests needs coverage
  of the bundle in the browser (an instrumented build), stage 5's to decide.
- **408 unit functions run no code of `src/lado` or `scripts/` of their own** (one
  identical group): they check files that are not Python. `test_docker.py` 88,
  `test_install_sh.py` 80, `test_ci_workflow.py` 36, `test_windows_shell_workflow.py` 32,
  `test_smoke_ci.py` 25, `test_install_ps1.py` 15, `test_release_workflow.py` 15,
  `test_workflow_security.py` 12, ... Stage 2's list.
- **The other 201 identical groups (514 functions)** are stage 1's and 4's candidates: e.g.
  `test_codex.py` (12 functions in one group, 8 in two others), `test_cli.py` (8),
  `test_agent_env.py` (7).
- **Code no test runs**: `terminal.py` 55%, `server/run.py` 81%, `images.py` 81% in unit;
  `scripts/secret_dots_font.py` 0%, `smoke_ci.py` 60%, `release_check.py` 61%.
- Under coverage with 8 workers 42 UI tests failed (586 passed): the UI layer is the most
  sensitive to load.

**Open after stage 0.**
- The UI tests' coverage of the bundle in the browser, per test (stage 5).
- vitest per test: v8 gives none; if stage 5 needs it, one run per test file.
- The junit history from CI: from the merge of this branch on; stage 1 reads it when weeks
  have passed.

### Stage 1, part 1 (2026-11-13, branch `chore/test-audit-stage-1`): `providers/codex.py`

**Mutants.** `scripts/mutants.py run src/lado/providers/codex.py` with the unit coverage of
stage 0: 967 mutants; 811 killed, 116 survived, 24 timeouts, 3 errors (the module's own
Python version check, which no import survives), 13 on lines no test runs. Killed of killed
and survived: 87%.

**Removable.** Of the 155 test functions of `tests/test_codex.py`, 2 kill no mutant;
`removable` lists 68 that can go one by one. Rule 2 (section 5) keeps 15 of them, each
written for a bug in the tracker:

- LAD-263 (the repo's `.codex/config.toml` silently overrode the model): 7 tests;
- LAD-152 with LAD-166 (Codex asked to trust the folder at each resume): 5;
- LAD-151 (the sandbox in the container): 2;
- LAD-167 (Codex hung on "Waiting for agents"): 1.

The other tests of the list reference only feature tasks (LAD-230, LAD-166, LAD-169,
LAD-174, LAD-19) or no task. **53 test functions removed** (and `USER_CONFIG`, no longer
used); the list is in the pull request. `tests/test_codex.py`: 155 → 102 test functions,
1 832 → 1 367 lines. Unit tests: 6 130 passed.

Most of those removed are variations of one scenario that a stronger test beside them
checks too: 14 of reading Codex's errors and its journal (one status after another, where a
table test checks them all), 8 of the login and the key, 8 of the trust of a repo, a
worktree, their subfolders and the repo's hooks, 5 of the carried and the session's model;
the other 18 of the launch and of a model server's list.

**Rechecks.**
- Every mutant a removed test killed (381 mutants) was run again against the tests that
  remain: all killed.
- The 46 mutants the remaining tests do not kill were run against the removed tests alone:
  none killed. Removing them loses nothing; these are the module's real gaps (below).

**A false survivor, and what it changed.** The first runs of the prototype gave 72
removable, not 68. A later run of the 168 import-time mutants found 61 that the first run
had killed "surviving", the later ones nearly all: its tests passed without loading the
mutant, from about the 50th mutant on (a temporary copy of `src/` cleaned mid-run, or a
stale `.pyc`; not settled). Taking that run over the first lost four tests' only kills;
joining the runs instead (`removable` joins the killers of every run) keeps them:
`test_a_model_at_capacity_is_temporary`, `test_a_server_error_is_temporary`,
`test_the_agent_s_list_adds_no_tool_or_parameter_of_openai_s`,
`test_the_user_s_model_settings_are_carried_and_nothing_else`. Since then
`scripts/mutants.py` deletes the module's `.pyc` before each mutant, and a run that
compiled none is an error, never a survivor.

**Gaps found** (mutants no test kills, a list for new tests, not for this stage): the names
of the hook events and of their keys (`PreToolUse`, `pre_compact`, ...), the
`model_catalog_json`, `model_context_window` and `model_auto_compact_token_limit` keys, the
escapes of a TOML string, the labels of the sandbox modes, the default context limit 2 500.

**Time.** About four hours of runs on four to six jobs (an import-time mutant runs some 425
tests), the rechecks two more. The next modules start with `scripts/mutants.py`.

### Stage 1, part 2 (2026-11-15, branch `chore/test-audit-stage-1-runtime`): `runtime.py`

**What made it affordable.** `runtime.py` is run by most of the suite: an import-time
mutant runs some 3 100 tests, a prompt text's mutant that nothing kills about 1 000 s. A
plain run was estimated at days. Two options of `scripts/mutants.py run` answer only what
`removable` on one test file needs:

- `--judge tests/test_runtime.py`: the file's tests run first; the other files' tests run
  only when one of the file's tests killed the mutant, up to the first that fails (is
  there another killer). A mutant none of the file's tests runs is "skipped", one none of
  them kills "untouched"; neither keeps a test of the file.
- `--enough 3`: the file's tests stop at three killers. `removable` keeps one of the
  killers it knows; a killer it does not know only makes it keep more tests, never fewer.

The whole module then took about four hours on six jobs.

**Mutants.** 1 754: 1 259 killed, 10 survived, 204 untouched, 241 skipped, 4 timeouts,
11 errors, 25 on lines no test runs.

**Other modules.** A test of `test_runtime.py` runs more than `runtime.py`, and may be the
last killer of a mutant elsewhere. The five modules where `test_runtime.py` is a large part
of the covering tests were run with the same judge: `hooks.py` (181 mutants, 100 killed by
a test of the file), `providers/kilo.py` (29, 8), `providers/opencode.py` (55, 9),
`providers/opencode_family.py` (283, 38), `artifacts.py` (409, 45). Together with
`runtime.py` they move `removable` from 344 to 335. The first run of `artifacts.py` had
106 mutants "not imported" from the middle of the run on, with the disk 97% full; run
again with space freed, none.

**Removable.** Of the 489 test functions of `tests/test_runtime.py` (on main 85dafa79),
9 kill no mutant; `removable` over the six matrices lists 335. Rule 2 keeps 56 of them:
those of the bug tasks LAD-212, 227, 172, 167, 247, 141, 153, and those of tasks that read
both ways (LAD-274, 5, 199, 163, 176, 106, 89; LAD-166 counts as a feature, as in part 1).
Main had meanwhile changed one more test of the list for LAD-105, after the mutation data:
kept as well. **281 test functions removed**, and 19 helpers no test used any more:
`tests/test_runtime.py` on main 504 → 223 test functions, about 3 700 lines fewer.

**Rechecks.**
- Every mutant a removed test killed (969, in all six modules) was run again against its
  remaining killers: 963 killed. The other six, the media types of `artifacts.py`
  (`text/csv` ... `image/jpeg`), were import-time mutants whose "killers" were tests of
  finishing a worker; run again against the removed tests on the old tree, none kills
  them. A test that failed by chance under load, out of the 638 an import-time mutant
  runs, counted as a kill; the recheck is what catches it.
- Main changed `runtime.py` and `hooks.py` after the mutation data (LAD-105, 170, 173,
  234). The branch coverage of the whole unit suite on main and on the branch, compared:
  no branch of `src/` that main's tests run is left unrun (one line of `cli.py` differs,
  the warning of a missing web UI bundle, which depends on the working copy, not on the
  tests). Unit tests: 5 848 passed (6 200 on main).

**Time.** `runtime.py` about four hours, the five other modules about five, the recheck
about two, on six jobs.

### Stage 1, part 3 (2026-11-15, branch `chore/test-audit-stage-1-state`): `state.py`

**Coverage** measured again on main 0be093d1 (5 848 unit tests). 2 837 tests run
`state.py`, 206 of them in `tests/test_state.py` (7%); in no other module is that file a
large part of the covering tests, so no other module was mutated; the whole suite's branch
coverage is compared instead.

**Mutants.** `run --judge tests/test_state.py --enough 3`: 1 698 mutants; 1 199 killed by
a test of the file, 164 untouched, 285 skipped, 10 on lines no test runs, 40 errors. The
errors are mutants that break the import of `state.py` (a key of a dict renamed: a
`KeyError` at import), so pytest collects nothing: every test kills them, they keep none.
About 80 minutes on six jobs.

**Removable.** Of the 210 test functions, 40 kill no mutant as far as the run knows (with
`--enough 3` only the first three killers in the file are recorded); `removable` lists 173.
Kept: 40 for rule 2 (bug tasks LAD-44, 129, 131, 141, 156, 172, 85; tasks that read both
ways LAD-27, 199, 234) and 39 for rule 4, the tests of the SQL of migration steps and the
schema (`test_version_N_...`, `test_the_migration_gives_...`, `test_schema_N_...`, the
foreign key, the journal); 9 are in both. **103 test functions removed**, and 9 helpers no
test used any more: `tests/test_state.py` 210 → 107 test functions, about 1 300 lines fewer.

**Rechecks.**
- Every mutant a removed test killed (845) was run again against its remaining killers:
  all killed.
- The branch coverage of the whole unit suite on main and on the branch: no branch of
  `src/` left unrun (the same line of `cli.py` as in part 2 differs, the working copy's
  web UI bundle). Unit tests: 5 717 passed (5 848 on main).

### Stage 1, part 4 (2026-11-15, branch `chore/test-audit-stage-1-model-settings`): `model_settings.py`

**Coverage** measured again on main b0cbbde3 (5 717 unit tests). 1 262 tests run
`model_settings.py`, 197 of them in `tests/test_model_settings.py`; the file is also 29% of
the tests of `model_servers.py` and 13% of those of `project_secrets.py`, so the three
were mutated with the same judge (`--judge tests/test_model_settings.py --enough 3`).

**Mutants.** `model_settings.py` 635 (572 killed by a test of the file, 41 untouched, 2
skipped, 2 timeouts, 18 on lines no test runs); `model_servers.py` 412 (246, 60, 95
skipped, 9 uncovered, 2 errors: a provider's label renamed breaks the import);
`project_secrets.py` 104 (24, 21, 58 skipped, 1 uncovered). About 80 minutes on six jobs.

**Removable.** Of the 198 test functions, 16 kill no mutant the run recorded; `removable`
over the three matrices lists 139. Rule 2 keeps 17: the bug tasks LAD-185 (the hint of
`model-server remove` named one model) and LAD-186 (LiteLLM probed as Anthropic-compatible),
and LAD-184 and LAD-240, which read both ways. No SQL here, so rule 4 keeps none. The
others reference feature steps of the models epic (LAD-180, 182, 183, 187, 200, 208, 211,
217, 220, 230). **122 test functions removed** and 2 helpers no test used any more:
`tests/test_model_settings.py` 198 → 76 test functions, about 1 170 lines fewer.

**Rechecks.**
- Every mutant a removed test killed (579) was run again against its remaining killers:
  573 killed. The other six are in the threads and requests of `model_servers.py`'s probe
  (`_ask`, the join of the answers), whose "killers" were tests of unrelated commands;
  run against all their killers on the old tree, none kills them: chance failures of tests
  with a fake HTTP server under load, as the media types of part 2.
- The branch coverage of the whole unit suite on main and on the branch: no branch of
  `src/` left unrun by the removal. Two lines differ: `cli.py`'s bundle warning (the
  working copy) and `tmux.py` 143-144, run by `test_tmux.py`, which this change does not
  touch and which runs them when run again. Unit tests: 5 575 passed (5 717 on main).

### Stage 1, part 5 (2026-11-15, branch `chore/test-audit-stage-1-cli`): `cli.py`

**Coverage** measured again on main 6ab2d1b4. `tests/test_cli.py` runs `cli.py` and,
through the commands, eight more modules, so all nine were mutated with the same judge
(`--judge tests/test_cli.py --enough 3`): `cli.py`, `clone.py`, `marketplaces.py`,
`log.py`, `gitcache.py`, `self_update.py`, `providers/kilo.py`, `runs.py`, `flows.py`.

**Mutants.** 4 087 in all: 1 875 killed by a test of the file, 866 untouched by it, 1 209
skipped, 112 on lines no test runs, 24 timeouts, 1 error; no survivor. `cli.py` alone:
2 078 (1 238 killed). The tests of `cli.py` start processes, so a mutant takes about 45 s
and one of the argument parser up to 150 s: about seven hours on six jobs, the slowest
module so far. The one error (`cli.py` 139, the attach test negated) attaches to tmux and
crashes the pytest workers; the remaining tests of the file still fail on it.

**Removable.** Of the 225 test functions, 32 kill no mutant the run recorded; `removable`
over the nine matrices lists 86. Rule 2 keeps 20: the bug tasks LAD-105 (a kit checked
only after the folder was made), LAD-181 (a secret printed by argparse's error) and
LAD-141, and LAD-5, 27, 106, 139, 163, 176 and 239, which read both ways. Rule 4 keeps the
three tests of a database on an older schema. The others reference feature tasks
(projects and their secrets, kits, `lado new`, the hints of `start`, `ls`, `answer`) or
none. **63 test functions removed** and 2 helpers no test used any more:
`tests/test_cli.py` 225 → 162 test functions, about 780 lines fewer.

**Rechecks.**
- Every mutant a removed test killed (343) was run again against its remaining killers:
  all 343 killed.
- The branch coverage of the whole unit suite on main and on the branch: no branch of
  `src/` left unrun by the removal. Two files differ, neither touched: `tmux.py` 122,
  143-144 (run by `test_tmux.py` when run alone) and `model_servers.py` 655, the branch of
  an `OSError` with a message, which a fake server's refused connection reaches by chance.
  Unit tests: 5 506 passed (5 576 on main).

### Stage 5 (2026-11-17, branch `chore/test-audit-stage-5`): the browser tests

**Coverage.** The 633 browser test cases ran with V8's precise coverage of the bundle in
Chromium (a pytest plugin starting it over CDP on each page, the bundle's source map
mapping it back to `web/src`) and with coverage of the server's subprocesses: 20 757 lines
of `web/src` run, each test's lines recorded. 627 passed, 6 failed (two of
`test_narrow_layout.py`, one of `test_providers_section.py`, three of `test_team_head.py`
on this machine); a failing test stays. vitest, with V8 coverage: 1 916 tests, 97.2% of
the statements of `web/src`.

**What vitest misses.** Stryker (vitest runner, per-test coverage, static mutants
skipped) over `web/src`: 26 597 mutants, 15 420 killed, 64 timeouts, 15 errors, 4 390
survived, 854 on lines no vitest test runs, 726 static. The run was stopped at 81%,
slowed by components whose mutants run hundreds of tests; the 5 128 mutants it did not
reach count as missed by vitest. So about one mutant in four is missed, and every browser
test runs some such line: coverage alone removes none.

**Selection.**
- Kept by the data, 288: every test that is one of at most five browser tests running a
  line where vitest misses a mutant, the failing ones, then the fewest more so that each
  such line stays run by three browser tests and each server line no unit test runs by
  one.
- Kept by rule 5 (layout), 265 of the 345 others: they measure boxes, scroll, the window's
  width or computed styles, directly or through a helper (`box`, `no_sideways_scroll`, a
  device's size).
- Kept by rule 2, 60: the bug tasks LAD-70, 78, 85, 109, 122, 126, 207, 226, 254, 271
  and 281, and LAD-5, 48, 163, 193, 194, 199, 218, 224 and 239, which read both ways.
- A sample of what vitest misses decided the remaining 28. 250 mutants of the lines they
  run (150 of lines at most five of them run, 100 of the rest), each built into the bundle
  and run against these tests until the first failure: 205 survived them all. The 45 they
  killed were run against the kept browser tests of the same line: 42 killed. The three
  left (`live.ts` 510, `Chat.tsx` 278 and 359) only
  `test_team_head.py::test_opening_the_title_field_leaves_the_team_as_it_stands` killed,
  so it stays (2 cases), though it fails now and then on this machine without a mutant
  and these kills may be such failures. The real browser's selection keeps
  `test_selection.py::test_a_triple_click_on_a_messages_last_paragraph_shows_the_bar`
  (2 cases) and a resize moving the focus keeps
  `test_team_head.py::test_a_focused_agent_that_goes_behind_the_button_leaves_the_focus_on_it`.

**16 test functions removed (16 cases)**, and the flow `DEMO` of `test_layout.py` no test
used any more: `test_chat.py` 1, `test_layout.py` 1, `test_live_updates.py` 2,
`test_main_screen.py` 4, `test_needs_you.py` 1, `test_selection.py` 2,
`test_share_access.py` 1, `test_stopped_session.py` 1, `test_team_head.py` 2,
`test_terminal_panel.py` 1. Browser test cases 633 → 617.

**Conclusion.** Removal hardly shortens the browser layer: what it checks is mostly layout
or bugs, which nothing else can. Its time goes into the fixtures (a server, a repo and a
session per test); making them cheaper is a separate task. Moving tests to vitest was not
tried: the tests kept by the data are the ones vitest's own mutants say it lacks.

### Stage 5, part 2 (2026-11-17, branch `chore/test-audit-stage-5-fixtures`): the fixtures

**Measured.** All 619 browser tests with a pytest plugin that times each phase, each
fixture's setup and the calls under them (the helpers of `tests/`, LADO's runtime, the
server's start and stop, subprocesses, sleeps, Playwright's actions and expects): 49.7 min
of test time, 16:45 on three workers (5 failed, the layout tests that fail on this
machine's fonts on main too).

| Where the time goes | Minutes | Share |
|---|---|---|
| `lado server` started and stopped for each test | 14.4 | 29% |
| A session of the fake agent made ready (`running_session`, `gated_session` and the like), 477 tests | about 17 | about 34% |
| Screenshots (`shot`) | 0.9 | 2% |
| The rest, mostly the checks in the browser | about 17 | about 35% |

- The server: 0.86 s to start and 0.55 s to stop under the run's load, 0.45 s and 0.25 s
  alone; half of the start is importing FastAPI. Polling for it costs nearly nothing.
- A session: `running_session` 1.4 s, `gated_session` 2.3 s, almost all of it waiting for
  the agent to be idle. The agent is idle once its session-start hook ran, and that hook
  waits for the launch's `lado mcp` to list its tools: `import lado.mcp_server` takes
  0.4-0.55 s, 0.35-0.48 s of it the MCP SDK.
- The browser itself is cheap: the `page` fixture 0.5 min in all.

**Tried.**
- A gate's state written straight into the database instead of a live session: the state
  differs from a live agent's (its messages typed and never confirmed, so the gate's
  recommendation stays asked); 141 tests saw it. Making it the same means running the
  agent's protocol (its prompt-submit and turn-end hooks) inside the test: a second fake
  agent, dropped.
- The integration tests' loop interval (0.25 s instead of 2 s) for the browser tests:
  `stop_session` 0.97 → 0.2 min, but the whole run 49.7 → 52.3 min, the loops' passes
  loading the machine; dropped.
- Waits are no reserve: `wait_for` polls every 0.02 s.

**Conclusion.** No cheap way to speed up the browser tests' fixtures: what costs is the
real processes, and the one way around the server's start (a server shared by tests)
breaks their isolation. The one safe reserve is the start of `lado mcp`, which delays
every agent's start for users too: task LAD-294, a product change, outside this audit.
The plugin and the data: outside the repository.

## 7. Sources

- coverage.py, Measurement contexts: https://coverage.readthedocs.io/en/latest/contexts.html
- coverage.py, Measuring subprocesses: https://coverage.readthedocs.io/en/latest/subprocess.html
- pytest-cov, Contexts: https://pytest-cov.readthedocs.io/en/latest/contexts.html
- Vitest, Coverage: https://vitest.dev/guide/coverage
- mutmut: https://github.com/boxed/mutmut
- Cosmic Ray: https://github.com/sixty-north/cosmic-ray
- Stryker Mutator (JavaScript/TypeScript): https://stryker-mutator.io
- L. Inozemtseva, R. Holmes, "Coverage Is Not Strongly Correlated with Test Suite
  Effectiveness", ICSE 2014.
- G. Petrović, M. Ivanković, "State of Mutation Testing at Google", ICSE-SEIP 2018.
- G. Petrović, M. Ivanković, G. Fraser, R. Just, "Practical Mutation Testing at Scale:
  A view from Google", IEEE TSE 2021 (arXiv:2102.11378).
- S. Yoo, M. Harman, "Regression Testing Minimization, Selection and Prioritization:
  A Survey", Software Testing, Verification and Reliability, 2012.
- Q. Luo, F. Hariri, L. Eloussi, D. Marinov, "An Empirical Analysis of Flaky Tests",
  FSE 2014.
- J. Micco, "Flaky Tests at Google and How We Mitigate Them", Google Testing Blog, 2016:
  https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html
- "Change-Detector Tests Considered Harmful", Google Testing Blog, 2015:
  https://testing.googleblog.com/2015/01/testing-on-toilet-change-detector-tests.html
- H. Vocke, "The Practical Test Pyramid", martinfowler.com, 2018:
  https://martinfowler.com/articles/practical-test-pyramid.html
- T. Winters, T. Manshreck, H. Wright, "Software Engineering at Google", O'Reilly 2020,
  chapters 11-14 (testing): https://abseil.io/resources/swe-book
- A. van Deursen, L. Moonen, A. van den Bergh, G. Kok, "Refactoring Test Code", XP 2001.
- G. Meszaros, "xUnit Test Patterns: Refactoring Test Code", Addison-Wesley 2007.
- A. Peruma et al., "tsDetect: An Open Source Test Smells Detection Tool", ESEC/FSE 2020.
