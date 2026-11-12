# Test audit: research and staged plan

Started 2026-11-12 on the human's request: are all of LADO's tests useful, which ones can be
removed, merged or made cheaper, and how other projects answer the same question. This file
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

Status: stage 0 in progress (durations, CI reports, unit coverage done; the coverage of
the integration and UI layers' subprocesses and of vitest open, see section 6); the others
wait for its numbers.

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

**How to measure** (the numbers of section 6 come from these). A coverage config of its own
outside the repository, e.g. `$DIR/rc`:

```ini
[run]
branch = true
source_pkgs = lado
parallel = true
data_file = $DIR/.coverage
patch = subprocess
core = ctrace
```

`core = ctrace` (or `COVERAGE_CORE=ctrace`) is required: from Python 3.14 coverage.py's
default core is `sysmon`, which records no per-test contexts. Then
`COVERAGE_CORE=ctrace uv run pytest -n auto --cov --cov-config=$DIR/rc --cov-context=test
--cov-report=` (with `-m integration` for that layer), and
`uv run python scripts/test_audit.py $DIR/.coverage --functions`. Durations:
`pytest --durations=0 --junitxml=...`. Before the UI layer, rebuild the bundle
(`cd web && npm run build`): `src/lado/server/static` from an older `web/src` fails a
third of the browser tests.

### Stage 1. Quick wins: speed and empty tests

**Why.** The slowest few percent of the tests usually take most of the time; making them
fast helps every run of every agent at once.

**What.**
- The top 20 slowest tests from stage 0: replace sleeps with waiting on an event, narrow
  timeouts, share heavy setup (`scope="module"`/`"session"` fixtures) where tests stay
  independent.
- Tests without assertions or with assertions that cannot fail, and tests with no unique
  coverage: review each; remove those that check nothing another test does not.

**Result.** Time per layer before and after; the list of removed tests with a reason each.

### Stage 2. Tests of file texts

**Why.** Tests that copy the wording of a document or a workflow file break on every edit
of it and rarely find a bug: they are change detectors (2.4).

**What.** Go through the ~51 unit test files that read documents, workflows, Dockerfiles
and installers. Sort each test into:
- **keep**: it guards an invariant (AGENTS.md's 200 lines, a CI step that must exist, a
  security setting of the image, a link that must resolve);
- **rewrite**: the invariant is real but checked through exact text; check the property
  instead (parse the YAML, check the key, not the line);
- **remove**: it only repeats the file.

**Result.** The count of each kind; a rule for docs/testing.md on what such tests may check.

### Stage 3. Mutation testing pilot

**Why.** To learn what mutation testing costs here and what it finds before relying on it
in stages 4-5.

**What.** `mutmut` on one or two modules of pure logic with fast unit tests (candidates:
`text.py`, `flows.py`). Record: run time, the number of mutants, the share killed, the
survivors worth a test, the tests that kill nothing unique. Decide whether to use it in
stage 4, and how (per file, on changed lines, nightly).

**Result.** The pilot's numbers and the decision, in section 6. New tests only for
survivors that show a real gap.

### Stage 4. Consolidating the big unit files, one per pull request

**Why.** The five largest files hold a third of the unit test code; they are where copies
and near-copies collect.

**What.** In order: `test_runtime.py`, `test_cli.py`, `test_state.py`, `test_providers.py`,
`test_model_settings.py`. For each: merge tests that differ only in data into
`parametrize`, remove the tests that stage 0 and, where affordable, mutation testing
show to add nothing (section 5), move shared setup to fixtures, split the file by topic if
it helps navigation.

**Result.** Per file: tests and lines before and after, branch coverage and killed mutants
before and after (both must not drop).

### Stage 5. The browser layer and the pyramid

**Why.** The browser tests are the most expensive layer (4 shards of up to 25 minutes).

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
- A time budget per layer in CI that warns when it is exceeded.
- Optionally, mutation testing of the changed modules (nightly or on demand), if stage 3
  shows it is affordable.

**Result.** The rules merged; the budget in CI.

## 5. Rules for removing a test

A test is removed only when all of these hold:

1. Another test fails on the same bug: shown by per-test coverage (the lines and branches
   are covered elsewhere) and, where mutation testing ran, by the module's killed mutants
   staying the same without it.
2. It does not guard a reported bug that the remaining tests would miss; check `git log`
   of the test for a task id (LAD-...) and read the task.
3. It does not check a property stated in docs/design or openspec/specs that no other test
   checks.
4. The pull request lists each removed test with its reason, and the numbers before and
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

**Open in stage 0.**
- The integration layer's coverage: only 5 639 lines ran in pytest's own process; `lado
  mcp`, hooks and the session loop run in agents' processes whose environment comes from
  the login shell, so coverage's variables never reach them. Its numbers (79% no unique
  line) say nothing yet. Needs the coverage variables passed into the agents' environment
  for the measurement.
- The UI layer's coverage (`lado server` as a subprocess) and vitest's
  (`@vitest/coverage-v8`).
- `scripts/` and the test helpers are not measured (`source_pkgs = lado`).

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
