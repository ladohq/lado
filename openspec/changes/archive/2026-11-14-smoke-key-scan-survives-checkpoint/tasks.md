## 1. The scan

- [x] 1.1 Add to `tests/agent_helpers.py` a helper that asserts a secret is in none of a
  LADO home's database files: it reads `lado.db-wal`, `lado.db-shm`, then `lado.db`; a
  `FileNotFoundError` on a side file skips it (no existence check before the read), a
  missing `lado.db` fails; a hit fails naming the file (AC-1, AC-2). Check: 1.2.
- [x] 1.2 Unit tests in `tests/test_agent_helpers.py` (layer: unit, plain files in
  `tmp_path`): no side files and a clean `lado.db` passes; a missing `lado.db` fails; the
  secret in `lado.db-wal`, in `lado.db-shm` or in `lado.db` fails naming that file (AC-2).
  Check: `uv run pytest tests/test_agent_helpers.py -n0`.
- [x] 1.3 `check_refusal` in `tests/smoke/test_smoke.py` calls the helper in place of its
  `glob("lado.db*")` loop (AC-1). Check: `uv run pytest -m smoke --collect-only
  tests/smoke/test_smoke.py` collects; a grep finds no `glob("lado.db*")` in `tests/`.

## 2. Checks

- [x] 2.1 `make lint` and `make test` pass (AC-3);
  `openspec validate smoke-key-scan-survives-checkpoint --strict` passes.
- [x] 2.2 The pull request's CI is green, with the smoke cells of kilo, opencode and claude
  that run `check_refusal` (AC-4); the smoke runs because the diff touches `tests/` outside
  ci.yml's skip list. A smoke cell red on this test again: the build report names the run.
