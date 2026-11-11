# Test audit: tools, baseline and policy (LAD-275, pull request 1)

Task: LAD-275. Change: `openspec/changes/test-audit-baseline/` (decisions D1–D11 in its
`design.md`). Research: session artifact `test-audit-research`, also attached to LAD-275.

## Goal

Fewer tests and less test time without losing what the suite catches. The task runs as several
pull requests, each a pass of the flow `task` over LAD-275:

1. **This pull request:** the tools, the baseline report with the numbers "before", the policy
   checklist, and the slow tests made fast. No test is deleted.
2. **Later pull requests, one category each:** change detectors, meta-tests, unit/integration
   duplicates, subset candidates, upper-layer duplicates. The human approves each batch's
   candidates from the report; each batch carries the mutation proof (D6). The last of them moves
   LAD-275 to review.

The task's goal, measured against this report by the last pull request: pytest tests −15% or
more; local `make test` −25% or more; runner-minutes of a CI run on main −10% or more; on every
module a batch touches, no mutant killed before survives after. CI's wall clock is not a goal: the
smoke on macOS (≈8 min, the real CLIs) and the UI shards (≈6 min) set it.

## Architecture

```
make test-audit ──> scripts/test_audit.py
                     ├─ coverage  --layer unit|integration|ui   pytest + pytest-cov + plugin (D3)
                     │     └─> <out>/coverage-<layer>.json      {test id: {file: [lines]}}
                     ├─ durations --layer ...                   pytest --durations=0 -q
                     │     └─> <out>/durations-<layer>.json
                     ├─ flaky                                   gh run list/view on main, 30 days
                     │     └─> <out>/flaky.json                 jobs green only on attempt > 1
                     ├─ subsets                                 coverage-*.json  (D4)
                     │     └─> <out>/subsets.json
                     ├─ pseudo                                  a copy of the repo, one function at a time (D5)
                     │     └─> <out>/pseudo.json
                     ├─ mutation <module>...   (by hand)        mutmut in <out>/mutmut/ (D6)
                     │     └─> <out>/mutation-<module>.json     {mutant: killed|survived|timeout|no tests}
                     ├─ prove <before> <after> (by hand)        exit 1 and the lost mutants, or the scores
                     └─ report                                  joins the JSON into report.md
```

- The plugin of D3 (`scripts/test_audit_plugin.py`, loaded with `-p` only by the audit) sets
  `LADO_AUDIT_TEST=<node id>` per test and a `COVERAGE_PROCESS_START` config whose static context
  reads it, so the processes LADO starts record lines under the test that started them.
- The copy for `pseudo` and `mutation` is a `git worktree add --detach` (or a plain copy of the
  tracked files) under `--out`; its `src/` comes first on `PYTHONPATH`, and the command checks
  that `lado.__file__` resolves into the copy before it mutates anything.
- Everything is standard library but the two dev dependencies; `gh` is needed only by `flaky`,
  which says so and skips when `gh` is missing or not logged in.

## The report

`docs/superpowers/reports/2026-11-11-test-audit-baseline.md`, written by the developer from
`report.md` and the reading of the upper layers:

1. **Numbers before:** tests per layer (pytest, vitest), lines of test code per layer, `make test`
   wall time, the five slowest per layer, CI's last 10 runs on main (clock and runner-minutes per
   job), jobs green only on a rerun in 30 days.
2. **Slow tests fixed in this pull request:** each test of 1 s or more before, its time after, or
   the reason it keeps its time.
3. **Mutation baseline:** the score of `runtime`, `hooks`, `state`, `runs`, `flows`, the run time
   of each, the survived mutants counted per function.
4. **Pseudo-tested functions** of the five modules, and those not covered at all.
5. **Candidates, one table per category,** each row a test, the reason, the proposed verdict by
   the checklist (keep / rewrite / delete / move down), and for a subset the covering test:
   - change detectors (exact phrases of prompts, skills, documents);
   - meta-tests (README, docs, CI workflows, scripts, the tests themselves);
   - unit/integration duplicates (one name in both, or the integration test's lines all run by
     unit tests);
   - subset candidates of each layer (D4);
   - the upper layers' map (D8): UI, smoke, live, container.
6. **vitest:** count, wall time of `make web`'s tests, the slowest files, change detectors found by
   reading `web/src/**/*.test.tsx` (exact UI strings that are not the product's contract).
7. **Dead code** (`uvx vulture src/lado --min-confidence 80`, not a dependency): a list only.
8. **Proposals for LAD-276 and later:** size markers with a time budget, provider contracts in
   place of part of smoke and live, mutation in review, Stryker for the web UI.
9. **The batches:** the order of the later pull requests with the number of tests each would
   delete and its touched modules.

## The checklist "Which tests we keep" (draft for `docs/testing.md`)

The human approved the policy in answer #6081; the developer writes it in `docs/testing.md` in
these words or close to them:

- **A test checks behaviour,** what a user, an agent or another program sees, not the way the code
  gets there.
- **An exact phrase is checked only when it is a contract:** a name or a marker another program
  reads (an MCP tool's name, a hook's event, a marker the CLI parses, a command line flag, a
  permission in a workflow), or a safety rule. Any other phrase of a prompt, a skill or a document
  is not tested word for word: test the behaviour it causes, or nothing.
- **A meta-test is kept when it guards a rule of `openspec/specs/`** (e.g. `ci-ok` needs every job,
  `continuous-integration`) or the security of a workflow; tests of README's or a document's
  headings and phrases are not kept.
- **One check, one layer:** the lowest that can catch the bug (Testing in AGENTS.md); an upper test
  keeps only what the lower layer cannot show, e.g. the delivery across processes.
- **A test that executes code must be able to fail on it:** a function no test fails for when its
  body is emptied is pseudo-tested; its test gets an assertion or goes.
- **No real waits:** a unit test does not sleep for a timeout; it shortens the timeout or waits for
  the event. A test of 1 s or more names why.
- **A deletion is proven:** mutmut on each touched module before and after, no killed mutant lost
  (`scripts/test_audit.py prove`); a test of no module rests on the rules above, named in the pull
  request.
- **Parametrize with purpose:** cases of one function differ in what they check, not only in data
  that runs the same lines.

## Error handling

- A command whose layer collects no tests or fails to run says so and exits non-zero; `report`
  marks the missing part instead of leaving a gap (no silent drops).
- `pseudo` and `mutation` refuse to start when the copy's `lado` is not the copy's (the check
  above), and remove nothing outside `--out`.
- `prove` exits 1 when a module of `after` is missing from `before` or the reverse, naming it.

## Testing

- `tests/test_test_audit.py`, unit: subsets with siblings, equal sets and empty tests; the body
  replacement of `pseudo` on a function, a method, a generator, a property; `prove`'s pass, its
  lost mutant, a module on one side only; the JSON of `flaky` from a recorded `gh` answer;
  `report` with a missing part.
- One integration test (`tests/integration/test_test_audit_coverage.py`, marker `integration`): the
  coverage of one fake-agent test records `lado.hooks.handle`'s lines under that test's id and no
  other's (requirement "Per-test coverage of the unit, integration and UI layers").
- One integration test that `pseudo` on a tiny repository copy leaves the working tree's `git
  status` empty, also when interrupted.
- The slow tests: each rewritten test passes alone (`-n0`) and in the suite; the regression run is
  `make test` and CI's `ci-ok` on the pull request.
