## 1. The push test

- [x] 1.1 `tests/live/test_live.py`: `test_an_agent_pushes_through_a_saved_git_server` gets
  `@pytest.mark.parametrize("live_provider", ["claude", "codex"], indirect=True)`, and the
  `if live_provider not in ("claude", "codex"): pytest.skip(...)` goes; the rest of the test
  stays as it is (AC-2). Check: `uv run pytest -m live --collect-only -q -k <p>
  tests/live/test_live.py` for each of `claude`, `codex`, `opencode`, `kilo`: the push test is
  listed for the first two only (5 tests for opencode and kilo, 6 for claude and codex);
  quote the four counts in the build report (AC-1).

## 2. Docs

- [x] 2.1 `docs/testing.md`, the live paragraph of the test layers (item 6) or the live
  workflow's paragraph: a live test meant for some providers only narrows `live_provider`
  by an indirect parametrization, so the others do not collect it, since a skip makes their
  cell red; the push test is the one so. Check: read it.

## 3. Regression run

- [x] 3.1 `make lint`, `make test`, `openspec validate live-push-test-only-where-it-runs
  --strict`, the trial archive; `scripts/smoke_ci.py` and `tests/test_smoke_ci.py` unchanged
  (`git diff origin/main --stat`) (AC-3); CI of the pull request green (AC-4). The live run on
  main after the merge is the supervisor's (AC-5).
