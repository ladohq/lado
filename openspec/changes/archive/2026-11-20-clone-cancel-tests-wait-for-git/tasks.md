## 1. The helper

- [x] 1.1 `tests/agent_helpers.py`: `ended(pid, timeout=10)`, polling `gone(pid)` every 0.05 s
  until it is true (returns True) or the timeout passes (returns False) (AC-1).
- [x] 1.2 A unit test of `ended` (in the unit tests of the helpers, or `tests/test_clone.py`
  beside its users): a `sleep` killed a moment after the call gives True; a `sleep 60` with
  `timeout=0.3` gives False, then is killed and reaped (AC-3).

## 2. The checks

- [x] 2.1 The 12 checks `gone(call["pid"]) and gone(call["child"])` in
  `tests/integration/test_clone_start.py`, `tests/integration/test_project_repositories.py`,
  `tests/test_clone.py` and `tests/test_server_clones.py` use `ended`; imports that no longer
  need `gone` drop it; `grep -rn 'gone(call\["pid"\])' tests` finds nothing (AC-2).

## 3. Checks

- [x] 3.1 `tests/integration/test_clone_start.py` 30 times in a row under load, each run's exit
  status read (AC-4); the build report gives the count and how the load was made.
- [x] 3.2 `make lint`, `make test`, and
  `uv run pytest -m integration -n auto tests/integration/test_clone_start.py tests/integration/test_project_repositories.py`
  pass (AC-4).
- [x] 3.3 `openspec validate clone-cancel-tests-wait-for-git --strict` passes.
