## 1. The doctor tests

- [x] 1.1 `tests/test_doctor.py`, `test_lado_check_says_a_newer_version_is_available`:
  expect `check.detail == update.shown(__version__)`;
  `test_lado_check_of_the_latest_version_and_with_the_check_off`: build both expected
  details from `update.shown(__version__)`. Check: `uv run pytest -n0 tests/test_doctor.py`
  passes (AC-1).

## 2. The system panel test

- [x] 2.1 `tests/ui/test_system_panel.py`: replace
  `test_a_final_release_is_not_offered_a_newer_release_candidate` by a test (renamed, e.g.
  `test_an_up_to_date_final_release_shows_no_update`) that drops the assert on
  `update.prerelease(__version__)`, publishes only `__version__` before the server's first
  look, and routes `/api/system` (`version`) and `/api/update` (`current`, `prerelease:
  False`, `latest`) to one final version, the rest of each answer the server's own, as
  `test_a_release_candidate_and_a_newer_one_on_offer_are_marked` does; a comment says
  that the server's offer rule is tested in `tests/test_server_system.py`. It checks
  "Up to date", no Update region, no `.pill`, "Running", and takes its shot. Drop the
  `update` import if nothing else uses it. Check: `uv run pytest -m ui
  tests/ui/test_system_panel.py` passes (AC-2).

## 3. Both kinds of version

- [x] 3.1 By hand, not committed: `uv version 0.37.0`, then `uv run pytest -n0
  tests/test_doctor.py`, `uv run pytest -m ui tests/ui/test_system_panel.py` and
  `make test`; all pass; then `git checkout -- pyproject.toml uv.lock` and `uv sync`, and
  `uv run lado --version` says 0.37.0rc1 again. The build report quotes the counts (AC-3).
- [x] 3.2 On 0.37.0rc1: `make lint`, `make test` and `uv run pytest -m integration -n
  auto` pass (each to a log outside the tree, exit status read); the build report gives
  the counts (AC-4).
