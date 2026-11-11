The steps in full: `docs/superpowers/plans/2026-11-11-test-audit-baseline.md` (Task N there is
section N here).

## 1. The trial of mutmut and the dependencies

- [ ] 1.1 `pytest-cov` and `mutmut` in the `dev` group (`uv add --dev`), `uv.lock` updated; `make
  test` green.
- [ ] 1.2 mutmut on `src/lado/text.py` with the unit tests in a scratch copy gives a score, and a
  mutant `tests/test_text.py` must kill is reported killed. Otherwise stop and report `redesign`
  with the log (design.md, Risks).

## 2. Coverage per test, across processes

- [ ] 2.1 `scripts/test_audit_plugin.py` and `scripts/test_audit.py coverage --layer
  unit|integration|ui` (D3); `coverage-<layer>.json` under `--out`. Check:
  `uv run pytest -m integration tests/integration/test_test_audit_coverage.py -n0` (a hook's lines
  under its test's id only) and the unit test of `load_coverage`.

## 3. Durations and flakiness

- [ ] 3.1 `durations` and `flaky` (D1, D2), `gh` faked in the unit tests, `gh` missing is a skip
  that says so. Check: `uv run pytest tests/test_test_audit.py -n0 -k "durations or flaky"`.

## 4. Subsets and pseudo-tested functions

- [ ] 4.1 `subsets` (D4): candidates, siblings not compared, equal sets once, empty records apart.
  Check: `uv run pytest tests/test_test_audit.py -n0 -k subset`.
- [ ] 4.2 `pseudo` (D5) in a `git worktree` copy under `--out`, the guard on `lado.__file__`, a
  per-function timeout, the file restored after each function. Check: `uv run pytest -m integration
  tests/integration/test_test_audit_copy.py -n0` (clean tree, also after SIGINT; a function no test
  checks listed) and the unit tests of `empty_body`.

## 5. The mutation baseline and the proof

- [ ] 5.1 `mutation <module>...` (D6) with mutmut's copy under `--out`, and `prove` (no killed
  mutant lost; a module on one side only, or a mutant missing after, fails; a deleted test of no
  module named as resting on the checklist, D7). Check: `uv run pytest tests/test_test_audit.py
  -n0 -k prove`.

## 6. `make test-audit` and the report command

- [ ] 6.1 The Makefile target with help text, under the check lock, not in `make check`; `report`
  marks a missing part. Check: `uv run pytest tests/test_test_audit.py -n0 -k "report or make"`.

## 7. The slow tests

- [ ] 7.1 `tests/test_providers.py::test_a_claude_session_start_keeps_the_alias_s_source` under
  1 s (the `MCP_READY` event recorded or `hooks.MCP_READY_TIMEOUT` shortened), same assertion.
- [ ] 7.2 Each other unit test of 1 s or more in the baseline sped up the same way (D9), or its
  reason noted for the report; `src/` only to turn a local timeout into a constant or keyword
  argument with the same default. Check: each file alone with `-n0`, then `make test`, with the
  durations before and after.

## 8. The baseline measurements

- [ ] 8.1 `make test-audit` on the branch after 7; `mutation runtime hooks state runs flows` with
  each module's time (over two hours: stopped and named, design.md Risks); vitest counts and file
  times; `uvx vulture src/lado --min-confidence 80`. Raw data outside the tree.

## 9. The report, the checklist, the docs

- [ ] 9.1 `docs/superpowers/reports/2026-11-11-test-audit-baseline.md` in the nine sections of the
  design doc, every candidate with a verdict by the checklist, the batches in order.
- [ ] 9.2 `docs/testing.md`: "Test audit" (the commands, `--out`, proving a batch) and "Which tests
  we keep" (the design doc's checklist); AGENTS.md: one line for `make test-audit` and the script in
  Layout's `scripts/`. Check: `uv run pytest tests/test_agents_md.py -n0`.
- [ ] 9.3 No CHANGELOG item, no version change (D11).

## 10. The regression run

- [ ] 10.1 `make lint`, `make test` (numbers), the two new integration files with
  `-m integration`, `openspec validate test-audit-baseline --strict` and the trial archive; `ci-ok`
  green on the pull request. The merge waits for the tag `v0.46.1` (D11).
