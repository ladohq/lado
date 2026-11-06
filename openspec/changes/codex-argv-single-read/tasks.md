## 1. The fix

- [ ] 1.1 `tests/container/test_codex_sandbox.py`: `codex_pid` becomes `codex_args(container,
  session, window, timeout=60) -> list[str]`. It polls as now, splits each read on `"\0"`, and
  returns that list when it holds `--no-daemon` and does not hold `lado.agent_env`; the
  timeout's message keeps the last read. The docstring says why the argv is read once: a
  process's cmdline reads empty, with exit 0, while it execs (LAD-214).
- [ ] 1.2 The test takes `args = codex_args(container, "cx", "supervisor")`, with no second
  `cat`, and asserts `("-a", "on-request")` and `("--sandbox", "danger-full-access")` in
  `pairs = list(zip(args, args[1:]))`, each with `args` as the message.
- [ ] 1.3 `grep -n "cmdline" tests/container/test_codex_sandbox.py` shows one read, in
  `codex_args`.

## 2. Checks

- [ ] 2.1 `make lint` green.
- [ ] 2.2 `uv run pytest -m container --collect-only tests/container/test_codex_sandbox.py`
  collects the test (no Docker in the agents' container; do not claim it ran).
- [ ] 2.3 CI's container cells, amd64 and arm64, pass this test on the pull request; name the
  run in `build-report`.

## 3. Backlog

- [ ] 3.1 `BACKLOG.md`, in a commit of its own: CI's container job does not upload
  `/tmp/lado-live-evidence`, so a failed container test's evidence is lost with the runner
  (found on LAD-214).
