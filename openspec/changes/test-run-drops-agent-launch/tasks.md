## 1. The test run's environment

- [x] 1.1 `tests/agent_helpers.py`: add a function (next to `no_maintenance_env`) that
  takes an environment and returns it without LADO's fixed names (the list now in
  `tests/conftest.py`, its comment kept), without `LADO_LAUNCH_VARS` (`agent_env.LAUNCH_VARS`)
  and every name it lists, but with `TMPDIR` as it was. Check: `make test`.
- [x] 1.2 Unit test of 1.1 (AC-2, AC-3) in the module that tests `agent_helpers` (a new
  `tests/test_agent_helpers.py` when there is none): an agent-like environment with
  `LADO_LAUNCH_VARS=CLAUDE_CODE_TMPDIR,LADO_AGENT,TMPDIR,LADO_MODEL_KEY_GW`, those set, plus
  `LADO_CONTAINER`, `TMUX` and an unrelated `FOO`: the result is `TMPDIR` and `FOO` only;
  without `LADO_LAUNCH_VARS`, only the fixed names go. Check: the test fails when 1.1 drops
  `TMPDIR` or keeps `CLAUDE_CODE_TMPDIR`.
- [x] 1.3 `tests/conftest.py`: replace its loop of `os.environ.pop` with the function of
  1.1 (clear and update `os.environ`, or pop what it leaves out); the comment says the
  launch's names go because the run's environment reaches the agents the tests start,
  and `TMPDIR` stays as the agent's own temporary folder. Check: `make test`.

## 2. Docs

- [x] 2.1 `docs/testing.md`, the sentence "`tests/conftest.py` clears …": add
  `LADO_ENV_DIR`, `LADO_LISTEN`, `LADO_PUBLIC_HOST` (already cleared, not named) and
  `LADO_LAUNCH_VARS` with every name it lists but `TMPDIR`. Check: read against conftest.

## 3. Checks

- [x] 3.1 In this agent's shell (`LADO_LAUNCH_VARS` set; say so in the build report):
  `uv run pytest -n0 tests/test_temp_dirs.py` and `make test` green without `env -u`
  (AC-1); `make lint`; `openspec validate test-run-drops-agent-launch --strict` and the
  trial archive with `--skip-specs`.
