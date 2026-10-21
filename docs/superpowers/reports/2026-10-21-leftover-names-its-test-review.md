# LAD-121 leftover-names-its-test: review report

Pull request #130 `fix/lad-121-leftover-names-its-test` → `main`. Scale: tweak, reviewed by
precision: the diff touches `tests/`, `docs/testing.md`, BACKLOG.md and the openspec change,
not `src/`, so no breadth pass. Head reviewed: `7e1f7f1` (= the remote head).
`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/`
did not change, so no live tests were needed.

## Rounds

- **Round 1, local** (precision, `18cd77d..197af35`, the whole pull request): the diff by
  hand against the `test-processes` delta and decisions D1–D5, the architecture against
  AGENTS.md (`src/` untouched, no second source of truth, a process without the mark is
  still named and still fails the run). F1.
- **Round 1, external** (Claude Code GitHub Action; request 18:15:31Z, comment
  6323227046, "Claude finished" 18:16:22Z): no blockers; E1 confirmed, E2 refuted. It is
  of the same model family, so its "nothing more" weighs less.
- **Round 2, local** (`197af35..7e1f7f1`, a return from `merge`: the archive was refused,
  as the modified requirement grew past openspec's 500 characters). The `LADO_TEST_ID`
  rule moved to a requirement of its own, "Each test marks the processes it starts"; no
  code or test changed. A trial archive in a copy of `openspec/` passed with
  `openspec validate --specs --strict` 43 of 43. F3. No external round: the cap of 1 was
  used.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (spec) | on macOS a node id with a space (a parametrized test) is cut at the first space: `ps -E` joins the environment with spaces (`tests/leftovers.py:56-59`) | confirmed | minor | declined: on Linux the environment comes from `/proc`, NUL-separated, and the name is exact; the cut name still finds the test |
| E1 | 1 | external | `os.environ.pop("LADO_TEST_ID", None)` after a test erases a value set before the run (`tests/conftest.py:78`) | confirmed | minor | declined: only the outer pytest of the integration test sets it for the inner run, which overwrites it per test anyway |
| E2 | 1 | external | `timeout=120` in the integration test is generous | refuted: a ceiling, not a wait; the run takes seconds | — | dropped |
| F3 | 2 | local (tests) | the scenarios "a process started in setup or teardown" and "no mark between tests" have no test of their own | confirmed | minor | declined: a `try/finally` wrapper around the whole `pytest_runtest_protocol` covers them by construction; a test would need another scratch pytest run |

Metrics: 2 local rounds, 1 external, 0 substitutes. Confirmed 3 (local 2, external 1), all
minor, all declined; refuted 1 (external). Findings in code changed by the developer's
cleanup: 0.

## Checks

- Round 1, head `197af35`: `make lint` green; `make test` exit 0, 3615 passed, 1 skipped
  (59.44 s), no "processes left by the test run";
  `uv run pytest -m integration -n auto tests/integration/test_leftover_processes.py`
  8 passed. Able to fail: without the fake git's `kill/wait` the run fails naming
  `sleep 60, started in tests/test_clone.py::test_a_target_filled_during_the_clone`.
- Round 2, head `7e1f7f1`: `openspec validate leftover-names-its-test --strict` valid;
  `openspec validate --specs --strict` 43 of 43 before and after the trial archive.
- CI on `7e1f7f1`: `ci-ok` green (unit 3.10/3.13, integration, js, ui, container, smoke
  ubuntu/macOS).

## Not checked

- F1's cut on macOS was not reproduced (no macOS in the container); concluded from code.
- F3's scenarios rest on the wrapper's construction, not on a test.
- Full integration, UI and smoke runs were not run locally; CI ran them green.

## Found on the way

None.
