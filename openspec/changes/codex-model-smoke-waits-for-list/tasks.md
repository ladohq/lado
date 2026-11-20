## 1. The test

- [x] 1.1 By hand, before the fix: in `test_model_of_a_codex_agent_on_a_server_shows_its_model_alone`,
  print `CODEX_MODEL in screen` and `"On Шлюз" in screen` for `tmux.capture(SESSION, "supervisor")`
  just before `/model` is sent, and run
  `uv run pytest -m smoke -n0 -s "tests/smoke/test_smoke.py::test_model_of_a_codex_agent_on_a_server_shows_its_model_alone[codex]"`:
  `True` and `False` (AC-2). Quote the output in the build report, then remove the probe.
- [x] 1.2 `tests/smoke/test_smoke.py`: the wait after `/model` checks `"On Шлюз"` instead of
  `CODEX_MODEL`; the assertions after it stay (AC-1).
- [x] 1.3 The test alone 10 times in a row (the command of 1.1 without `-s`, in a shell loop that
  stops on the first failure), then `make test-smoke PROVIDER=codex`, each run's exit status read
  (not piped); all pass (AC-3). The build report gives the counts.

## 2. Checks

- [x] 2.1 `make lint` passes (AC-4).
- [x] 2.2 `openspec validate codex-model-smoke-waits-for-list --strict` passes.
- [x] 2.3 On the pull request, the `smoke macos-latest codex` cell is green, then rerun alone 3
  times (`gh run rerun <run id> --job <job id>`), each green (AC-4). The build report names the
  runs.
