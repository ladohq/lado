# LAD-50 tests-never-send-statistics: review report

Pull request #31 `fix/lad-50-tests-never-send-statistics` → `main`. Scale: tweak, patch
(tests and docs only), review depth precision. Head reviewed last: `db42715` (= the remote
head); the archive commit follows it. No API, MCP, CLI or schema change, no CHANGELOG.md
line. `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and
`tests/live/` are untouched, but the guard in `tests/conftest.py` applies to the live
tests too.

## Rounds

- **Round 1** (`origin/main..db42715`, the whole pull request): local precision pass over
  the spec, the tests and the docs. External round 1 by the Claude Code Action (request at
  06:11:55 UTC, "Claude finished" at 06:12:11 UTC; it read the diff and ran no tests): no
  blocker, no important finding. The external round cap for a tweak (1) is used.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local + external | the guard's after-test check reads only the `lado_home` fixture's folder, not a `LADO_HOME` the test switches to itself with `monkeypatch.setenv` (8 tests in `test_uninstall.py`, `test_lazy_imports.py`, `test_telemetry.py`) | confirmed | minor | declined: none of those tests sends or queues today; the fix is one line (also read `os.environ["LADO_HOME"]` at teardown) |
| F2 | 1 | local + external | `docs/release.md:82` is 132 characters long, not wrapped as its neighbours | confirmed | minor | declined: style only |
| E1 | 1 | external | check that `telemetry_endpoint` depends on `telemetry_on` | refuted | — | `telemetry_endpoint(telemetry_on, monkeypatch)` and `not_chosen(telemetry_on)`; `request.fixturenames` holds transitive fixtures |
| E2 | 1 | external | move `from pathlib import Path` out of the test's body | refuted | — | the file's own style (`test_docs_list_every_field` does the same) |

| Source | Confirmed | Refuted |
|---|---|---|
| local | 2 (F1, F2) | 0 |
| external, Claude Code Action | 2 (F1, F2, both also local) | 2 (E1, E2) |

## Where live and smoke tests keep LADO_HOME

The same folder the guard reads: `real_clis.isolated` depends on `lado_home` and changes
only `LADO_TMUX_SOCKET`; the smoke conftest changes `HOME`, `XDG_*`, `CLAUDE_CONFIG_DIR`
and the endpoint's keys, the live conftest the CLIs' endpoint configs and
`XDG_STATE_HOME`; none changes `LADO_HOME`, and agents inherit the test's environment
(`LADO_AGENT_ENV=inherit`).

## Spec check

- "Tests never send" (modified): the autouse `_no_statistics` in `tests/conftest.py`
  (before: `off_by == "LADO_TELEMETRY=0"`; after: `telemetry/sent.json`,
  `telemetry/outbox/*` unless `telemetry_on`); the subprocess test of `lado telemetry
  status` in `tests/test_isolation.py`. The guard was shown able to fail with a scratch
  pytest plugin, no repository change: without `LADO_TELEMETRY` an error at setup naming
  `LADO_TELEMETRY=0`; a written `sent.json` or an outbox file an error at teardown naming
  the file.
- "The release candidate's scratch install never sends" (added): docs/release.md
  section 4 sets `LADO_TELEMETRY=0` with every `LADO_HOME=$(mktemp -d)`; the docs test in
  `tests/test_telemetry.py` keeps it (it asserts it found such lines). The "does not ask"
  scenario holds by `State.ask`, false while `off_by` is set.
- Every task of `tasks.md` checked; nothing beyond the scope.

## Checks

- Reviewer on `db42715`: `make lint` clean; `tests/test_isolation.py`,
  `tests/test_telemetry.py`, `tests/test_cli_telemetry.py` 90 passed; `openspec validate
  tests-never-send-statistics --strict` and `openspec validate --specs --strict` passed.
- Developer: `make test` 2814 passed (one timing flake passed on its rerun).
- CI on `db42715` green: check (3.10, 3.13), js, ui, smoke × 8.

## Found on the way

None.

## Not checked

- The live tests: they need real models and run at a release; the guard reaches them
  through the root conftest, with the same home.
- Smoke and UI only in CI (green).
- F1: the guard does not see a home that 8 tests switch to themselves.
