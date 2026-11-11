# Test audit baseline Implementation Plan

**Goal:** Tools that show what each LADO test checks and whether it can fail, the baseline report
with the numbers "before", the policy checklist, and the slow tests made fast; no test deleted.

**Architecture:** One script `scripts/test_audit.py` with subcommands that write JSON to an
output folder outside the tree, and a pytest plugin `scripts/test_audit_plugin.py` that attributes
coverage to the test that ran it, also in child processes. Mutation runs in a copy of the
repository. The report and the checklist are written from the JSON by hand where reading is
needed (the upper layers).

**Tech Stack:** Python 3.10+, pytest, pytest-xdist, pytest-cov 7.x (coverage 7.x), mutmut 3.x,
`gh`, `git worktree`.

**Spec:** `docs/superpowers/specs/2026-11-11-test-audit-baseline-design.md`, the change
`openspec/changes/test-audit-baseline/` (proposal, `design.md` D1–D11, delta
`specs/test-audit/spec.md`).

## Global Constraints

- Dev dependencies only: `pytest-cov`, `mutmut` in `[dependency-groups] dev`; nothing in
  `[project] dependencies`.
- Everything the audit writes goes under `--out` (default `<tempfile.gettempdir()>/lado-test-audit`);
  the working tree's `git status` stays empty.
- `make test-audit` is not part of `make check`; CI's workflows do not change.
- No test is deleted in this pull request; a slow test keeps its check.
- `src/` changes only to turn a local timeout into a module constant or keyword argument with the
  same default; no behaviour change, no CHANGELOG item, no version bump.
- Commit messages: a plain English sentence ending in `(LAD-275)`.
- Merge only after the tag `v0.46.1` exists (D11).

## Review Focus

- A child process started by a test (hook, `lado mcp`, the UI server) writes its lines under the
  test's id, not under an empty context — Task 2's integration test.
- A test that times out or hangs under `pseudo` does not stop the audit or leave the copy mutated
  for the next function — Task 4's timeout test.
- `pseudo` or `mutation` started from a copy whose `lado` resolves to the working tree refuses to
  start — Task 4's guard test.
- `prove` given results of different modules, or a mutant renamed between runs, fails loudly
  instead of passing — Task 5's tests.
- `flaky` without `gh` or without a login says so and skips; `report` marks the part missing —
  Task 3's tests.

---

## Requirements → tests

| Requirement (delta `test-audit`) | Test | Layer |
|---|---|---|
| The audit runs apart from the working tree and the checks | `tests/integration/test_test_audit_copy.py::test_pseudo_leaves_the_working_tree_clean`, `::test_an_interrupted_pseudo_leaves_it_clean`; `tests/test_test_audit.py::test_make_check_runs_no_audit` | integration, unit |
| Per-test coverage of the unit, integration and UI layers | `tests/integration/test_test_audit_coverage.py::test_a_hook_s_lines_belong_to_its_test` | integration |
| Subset candidates | `tests/test_test_audit.py::test_a_test_inside_another_is_a_candidate`, `::test_cases_of_one_function_are_not_compared`, `::test_equal_sets_are_listed_once` | unit |
| Pseudo-tested functions of the core | `tests/test_test_audit.py::test_body_replacement_*` (function, method, generator, property); `tests/integration/test_test_audit_copy.py::test_pseudo_finds_a_function_no_test_checks` | unit, integration |
| The mutation proof of a deletion | `tests/test_test_audit.py::test_prove_*` (passes, lost mutant, module on one side, test of no module) | unit |
| Durations and flakiness per layer | `tests/test_test_audit.py::test_durations_lists_tests_of_a_second_or_more`, `::test_flaky_reads_reruns_from_gh` | unit |

End-to-end: the developer runs `make test-audit` once on the branch and the mutation baseline of
the five modules; the report is their output. Regression run: `make lint`, `make test`, the changed
integration files with `-m integration`, and CI's `ci-ok` on the pull request.

---

### Task 1: The trial of mutmut and the dependencies

**Files:**
- Modify: `pyproject.toml` (`[dependency-groups] dev`, a `[tool.mutmut]` section if mutmut needs
  one), `uv.lock`

- [ ] **Step 1:** `uv add --dev pytest-cov mutmut`; `uv sync`.
- [ ] **Step 2:** In a scratch copy of the repository (`git worktree add --detach <tmp>/trial`),
  run mutmut on `src/lado/text.py` with the unit tests; record the time, the number of mutants
  and the score.
- [ ] **Step 3:** Check the score is real: one mutant that `tests/test_text.py` must kill (e.g.
  a changed comparison in `text.py`) is reported killed.
- [ ] **Step 4:** When mutmut cannot run or gives no score (its copy breaks `conftest.py`'s
  isolation, the trampolines fail on our imports), stop: report `redesign` with the log (design.md,
  Risks). No other mutation tool in its place.
- [ ] **Step 5:** `make test` still green with the new packages; commit `pyproject.toml uv.lock`:
  "Add pytest-cov and mutmut as dev tools for the test audit (LAD-275)".

### Task 2: Coverage per test, across processes

**Files:**
- Create: `scripts/test_audit.py` (subcommand `coverage`), `scripts/test_audit_plugin.py`
- Test: `tests/integration/test_test_audit_coverage.py`, `tests/test_test_audit.py`

**Interfaces:**
- Produces: `coverage --layer {unit,integration,ui} --out DIR` writes `DIR/coverage-<layer>.json`:
  `{"<node id>": {"src/lado/hooks.py": [51, 52, ...], ...}}`, paths relative to the repository.
- Produces: `load_coverage(path) -> dict[str, dict[str, set[int]]]`.

- [ ] **Step 1:** Write the integration test: run `coverage --layer integration` limited
  (`-- -k <one fake-agent test>`) on two tests; assert `src/lado/hooks.py` lines of `handle` are
  under the first test's id and the second's record has none of them unless it ran hooks too.
- [ ] **Step 2:** Run it: FAIL (no script).
- [ ] **Step 3:** Implement the plugin (D3): an autouse hook per test sets
  `os.environ["LADO_AUDIT_TEST"] = item.nodeid` and `coverage`'s dynamic context in process; the
  script writes a coverage config into `--out` with `parallel = true`, `context =
  ${LADO_AUDIT_TEST}`, `source = src/lado, scripts`, and starts pytest with
  `COVERAGE_PROCESS_START` set and a `.pth`-free start (`coverage`'s `patch = subprocess` in
  coverage 7.x, or `sitecustomize` in a folder on `PYTHONPATH` under `--out`); afterwards it
  combines and exports per-context lines with `coverage.CoverageData`.
- [ ] **Step 4:** Run the test: PASS. Add a unit test of `load_coverage` on a small JSON.
- [ ] **Step 5:** Commit "Record which lines each test runs, in its child processes too (LAD-275)".

### Task 3: Durations and flakiness

**Files:**
- Modify: `scripts/test_audit.py` (`durations`, `flaky`)
- Test: `tests/test_test_audit.py`

**Interfaces:**
- Produces: `durations --layer L` → `DIR/durations-<L>.json` `{"wall": s, "tests": {id: s}}`
  from `pytest --durations=0 -q -n auto` parsed; `flaky` → `DIR/flaky.json` `{"runs": [{id,
  clock_s, runner_min, jobs: {name: s}}], "reruns": [{run, job, attempt}]}` from `gh run list
  --workflow ci.yml --branch main` (30 days) and `gh run view <id> --attempt N --json jobs`.

- [ ] **Step 1:** Unit tests with a recorded pytest output and recorded `gh` JSON (a fake `gh` on
  `PATH`, as `tests/test_ci_rerun.py` fakes commands): the tests of 1 s or more, the wall time, a
  job green only on attempt 2; `gh` missing → the command prints `flaky: gh is not available` and
  exits 0 with `{"skipped": "..."}`.
- [ ] **Step 2:** Run: FAIL. **Step 3:** Implement. **Step 4:** Run: PASS.
- [ ] **Step 5:** Commit "Measure test durations and CI's reruns for the test audit (LAD-275)".

### Task 4: Subsets and pseudo-tested functions

**Files:**
- Modify: `scripts/test_audit.py` (`subsets`, `pseudo`)
- Test: `tests/test_test_audit.py`, `tests/integration/test_test_audit_copy.py`

**Interfaces:**
- Consumes: `load_coverage` (Task 2).
- Produces: `subset_candidates(cov) -> list[tuple[str, str]]` (candidate, covering test);
  `empty_body(source: str, qualname: str) -> str`; `pseudo --modules runtime,hooks,state,runs,flows`
  → `DIR/pseudo.json` `{"pseudo": {func: [tests]}, "not_covered": [func]}`.

- [ ] **Step 1:** Unit tests of `subset_candidates`:

```python
def test_a_test_inside_another_is_a_candidate():
    cov = {"t.py::a": {"src/lado/runs.py": set(range(10, 21))},
           "t.py::b": {"src/lado/runs.py": set(range(1, 41))}}
    assert subset_candidates(cov) == [("t.py::a", "t.py::b")]

def test_cases_of_one_function_are_not_compared():
    lines = {"src/lado/runs.py": {1, 2}}
    assert subset_candidates({"t.py::f[x]": lines, "t.py::f[y]": dict(lines)}) == []

def test_equal_sets_are_listed_once():
    lines = {"src/lado/runs.py": {1, 2}}
    assert len(subset_candidates({"t.py::a": lines, "t.py::b": dict(lines)})) == 1
```

  A test with an empty record is not a candidate (it runs nothing of ours; the report lists it as
  "runs no code" instead).
- [ ] **Step 2:** Unit tests of `empty_body` with `ast`: a function becomes `return None`, a method
  too, a generator `return` + unreachable `yield`, a property's getter; the rest of the file is
  byte-identical (`ast.get_source_segment` and line offsets, not `ast.unparse` of the whole file).
- [ ] **Step 3:** Integration tests on a tiny repository made in `tmp_path` (a package `lado` with
  two functions, one checked by a test and one only executed): `pseudo` lists the second; the
  working tree's `git status --porcelain` is empty; a test that hangs is ended by a per-function
  timeout (60 s default, `--timeout`) and counted as killed; a SIGINT in the middle leaves the tree
  clean; a copy whose `lado.__file__` is not inside it makes `pseudo` exit 2 before any mutation.
- [ ] **Step 4:** Run: FAIL. **Step 5:** Implement: the copy by `git worktree add --detach
  <out>/copy`, `PYTHONPATH=<copy>/src`, per function the tests of its contexts with `-x -n auto
  -p no:cacheprovider`, the file restored from git after each function. **Step 6:** Run: PASS.
- [ ] **Step 7:** Commit "Find subset candidates and pseudo-tested functions (LAD-275)".

### Task 5: The mutation baseline and the proof

**Files:**
- Modify: `scripts/test_audit.py` (`mutation`, `prove`)
- Test: `tests/test_test_audit.py`

**Interfaces:**
- Produces: `mutation <module>...` → `DIR/mutation-<module>.json` `{"module", "seconds",
  "mutants": {name: "killed"|"survived"|"timeout"|"no tests"}}`; `score(result) -> float` (D6:
  (killed + timeout) / all mutants, "no tests" counting as survived);
  `prove(before: dict, after: dict) -> list[str]` (lost mutants, empty when proven); CLI exit 1
  on a lost mutant or a module on one side only.

- [ ] **Step 1:** Unit tests:

```python
def test_prove_passes_when_every_killed_mutant_stays_killed():
    before = {"module": "runs", "mutants": {"m1": "killed", "m2": "survived"}}
    after = {"module": "runs", "mutants": {"m1": "timeout", "m2": "survived"}}
    assert prove(before, after) == []

def test_prove_names_a_lost_mutant():
    before = {"module": "runs", "mutants": {"m1": "killed"}}
    after = {"module": "runs", "mutants": {"m1": "survived"}}
    assert prove(before, after) == ["runs: m1 killed before, survived after"]

def test_prove_refuses_other_modules():
    with pytest.raises(ValueError, match="runs.*flows"):
        prove({"module": "runs", "mutants": {}}, {"module": "flows", "mutants": {}})
```

  And: a mutant present before and missing after (code changed) is reported, not passed.
  And `prove --deleted <ids>` with coverage JSON names each deleted test that ran no line of
  `src/lado/` or `scripts/` as "rests on the checklist".
- [ ] **Step 2:** Run: FAIL. **Step 3:** Implement on mutmut's results (`mutmut results`, or its
  meta files in `mutants/`), with mutmut's copy under `--out`. **Step 4:** Run: PASS.
- [ ] **Step 5:** Commit "Prove that a batch of deleted tests loses no killed mutant (LAD-275)".

### Task 6: `make test-audit` and the report command

**Files:**
- Modify: `Makefile` (target `test-audit`, with `##` help), `scripts/test_audit.py` (`report`)
- Test: `tests/test_test_audit.py`

- [ ] **Step 1:** Unit tests: `report` joins the JSON of Tasks 2–5 into Markdown sections 1–5 of
  the design doc; a missing file shows as "not measured: <command>"; and `make check`'s recipe
  (read from the Makefile with `make -n check`) runs no `test_audit`.
- [ ] **Step 2:** FAIL → implement → PASS. The target runs `coverage` for unit, integration and ui,
  `durations` for the three, `flaky`, `subsets`, `pseudo`, `report`, under the check lock
  (`scripts/check_lock.py`, as `make test`).
- [ ] **Step 3:** Commit "Add make test-audit (LAD-275)".

### Task 7: The slow tests

**Files:**
- Modify: `tests/test_providers.py:126` and each unit test of 1 s or more in the baseline
  (`tests/test_loop.py`, `tests/test_telemetry.py`, `tests/test_server_model_settings.py`,
  `tests/test_model_settings.py`, `tests/test_doctor.py`, `tests/test_feed.py`,
  `tests/test_server_system.py`, `tests/test_uninstall.py`, `tests/test_server_launch.py`,
  `tests/test_project_secrets_store.py`, `tests/test_install_sh.py` as found); `src/lado/*` only per
  D9.

- [ ] **Step 1:** Record `durations --layer unit` before (Task 3) into the report's data.
- [ ] **Step 2:** The 20 s test: `hooks.handle` waits `MCP_READY_TIMEOUT` in `_wait_for_mcp`
  because no `MCP_READY` event exists for the agent. Record the event in the test
  (`state` has the call `lado.mcp_server` uses) or monkeypatch `hooks.MCP_READY_TIMEOUT` to 0.05;
  the assertion on `(agent.model, agent.model_source)` stays. Run it alone `-n0`: under 1 s.
- [ ] **Step 3:** Each other test of 1 s or more: find the wait (`--durations` plus `cProfile` as
  for Step 2), shorten it the same way, run alone and in its file. A test whose time is the point
  (a shell installer that waits by design) keeps it; note the reason for the report.
- [ ] **Step 4:** `make test` green; record `durations --layer unit` after.
- [ ] **Step 5:** Commit per file or group: "Stop the <file> tests waiting for real timeouts
  (LAD-275)".

### Task 8: The baseline measurements

- [ ] **Step 1:** `make test-audit OUT=<tmp>/lado-test-audit` on the branch after Task 7.
- [ ] **Step 2:** `scripts/test_audit.py mutation runtime hooks state runs flows`; record the time
  of each. A module over two hours: stop it, report its time, and measure the functions the report
  names for the first batches (design.md, Risks).
- [ ] **Step 3:** vitest: `cd web && npx vitest run --reporter=json` for count and file times; read
  `web/src/**/*.test.tsx` for exact UI strings that are not a contract.
- [ ] **Step 4:** `uvx vulture src/lado --min-confidence 80` (not a dependency) for the dead-code
  list.
- [ ] **Step 5:** Keep the raw JSON outside the tree; nothing to commit in this task.

### Task 9: The report, the checklist, the docs

**Files:**
- Create: `docs/superpowers/reports/2026-11-11-test-audit-baseline.md`
- Modify: `docs/testing.md` (sections "Test audit" and "Which tests we keep"), `AGENTS.md`
  (Commands: one line for `make test-audit`; Layout: `scripts/` names the audit), `docs/design/modules.md`
  only if it lists `scripts/`

- [ ] **Step 1:** The report in the nine sections of the design doc, from Task 8's data and the
  reading of smoke, live, container and UI tests (D8); each candidate with a verdict by the
  checklist; section 9 the batches in order with counts and touched modules.
- [ ] **Step 2:** The checklist in `docs/testing.md` from the design doc's draft; "Test audit"
  says the commands, `--out`, how to prove a batch (before on the target, after on the branch,
  `prove`), and that mutation runs by hand.
- [ ] **Step 3:** `uv run pytest tests/test_agents_md.py -n0` (AGENTS.md stays under 200 lines);
  `openspec validate test-audit-baseline --strict`; the trial archive of the settings' Checks.
- [ ] **Step 4:** Commit "Write the test audit's baseline report and the checklist of tests we keep
  (LAD-275)".

### Task 10: The regression run

- [ ] `make lint`; `make test` (report the numbers); `uv run pytest -m integration -n auto
  tests/integration/test_test_audit_coverage.py tests/integration/test_test_audit_copy.py`; push
  and wait for `ci-ok`. No merge before `v0.46.1` (D11).
