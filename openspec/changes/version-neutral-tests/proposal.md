Task: LAD-40

## Why

Symptom: CI is red on the release candidate's commit 2440f02 "Release candidate
0.37.0rc1" (run 38388111584): three tests fail, and they would fail on every release
candidate, so 0.37.0rc2 cannot be cut.

- `tests/test_doctor.py::test_lado_check_says_a_newer_version_is_available` and
  `::test_lado_check_of_the_latest_version_and_with_the_check_off`: they expect the LADO
  check's detail to start with the bare `__version__`, but `doctor.check_lado` shows the
  version through `update.shown`, which is `0.37.0rc1 (pre-release)` for a release
  candidate (requirement "A pre-release says so" of `release-candidates`).
- `tests/ui/test_system_panel.py::test_a_final_release_is_not_offered_a_newer_release_candidate`:
  it asserts `not update.prerelease(__version__)`, i.e. that the working copy is a final
  release, and then relies on the UI server (another process, running the working copy's
  version) not offering the published `99.0.0rc1`; on a release candidate the server
  offers it, as it must.

Cause: the tests were written when every commit of main carried a final version; the
release candidate process (`docs/release.md`) put a pre-release version on main, and these
three tests read the working copy's version as if it were a final one. LADO itself behaves
as its specs say; only the tests are wrong.

No other test makes that assumption: the CI run failed only these three (unit, UI; the
integration step was skipped after the unit step failed), and the integration tests that
use `__version__` (`tests/integration/test_update_process.py`,
`tests/integration/test_server_process.py`) pass on 0.37.0rc1 locally (16 passed).

## What Changes

- `tests/test_doctor.py`: the two tests expect `update.shown(__version__)` where they
  expect the bare version, so they hold for a final release and a release candidate alike.
- `tests/ui/test_system_panel.py`: the test that needs a final release no longer depends on
  the working copy's version. It publishes only the working copy's own version (so the
  server's real answer is "up to date" on either kind of version) and, as its neighbour
  `test_a_release_candidate_and_a_newer_one_on_offer_are_marked` does, rewrites the
  server's `/api/system` and `/api/update` answers to a final release's (`current`,
  `prerelease`, `latest`, and `version`). It checks what the UI shows for an up-to-date
  final release: "Up to date", no Update block, no pill. It is renamed to say that. The
  rule "a final release is not offered a newer release candidate" stays tested where the
  server decides it: `tests/test_update.py` and
  `tests/test_server_system.py::test_update_says_which_versions_are_pre_releases`
  (`0.36.0` with `0.37.0rc1` published: nothing available).

## Scope

The three tests. Nothing in `src/` or `web/`.

## Out of scope

- A way to set the UI server's version from a test (an environment variable read by
  `lado.__version__`): test-only code in the product, which AGENTS.md's "Only what is
  used" rules out; the neighbour test's route rewrite already does the job.
- Skipping the UI test on a pre-release: the test would not run during any release
  candidate, exactly when the release is checked.
- The two doctor tests patching `lado.__version__` to a fixed final version: they would no
  longer check the working copy's own line, and `test_lado_check_says_this_lado_is_a_pre_release`
  already covers the pre-release wording with a fixed version.
- A CHANGELOG.md line or a version bump: nothing users see changes; the fix ships as
  0.37.0rc2, which a separate release task cuts.

## Acceptance criteria

- AC-1: The two doctor tests expect `update.shown(__version__)` and pass on 0.37.0rc1.
- AC-2: The UI test no longer asserts anything about the working copy's version; it
  rewrites `/api/system` and `/api/update` to a final release that is up to date and
  checks "Up to date", no Update block and no pill; it passes on 0.37.0rc1.
- AC-3: With the version set to 0.37.0 by hand for the check (`uv version 0.37.0`, not
  committed, undone after), the three tests pass too, and so does the whole unit suite.
- AC-4: `make lint`, `make test`, `uv run pytest -m ui tests/ui/test_system_panel.py`
  and `uv run pytest -m integration -n auto` pass on 0.37.0rc1; CI is green.

## Impact

- `tests/test_doctor.py`, `tests/ui/test_system_panel.py` only.
- No API, schema, MCP, CLI or UI change; no CHANGELOG.md line and no version bump (a fix
  for the release candidate 0.37.0rc1, released as 0.37.0rc2 by a separate task).

## Decisions for the record

- Scale tweak: a test-only change of known shape; review by precision.
- Root cause: the tests read the working copy's version as a final one; fixed in the
  tests, LADO is right.
- The doctor tests use `update.shown`, the one function that formats a version as shown,
  rather than a second copy of its rule.
- The UI test rewrites the server's answers as its neighbour does, and publishes only the
  working copy's version so the real answer under the rewrite is "up to date" on either
  kind of version; the rule itself stays at the API layer, where the server decides it.
- The UI test is renamed (e.g. `test_an_up_to_date_final_release_shows_no_update`), as it
  no longer proves which releases the server offers.
- The integration step was skipped in CI's run; the run of the whole integration suite on
  0.37.0rc1 is part of AC-4.
- Test layers: unit (doctor) and UI e2e (system panel), the tests themselves; no new test.
- No delta spec: no behaviour rule changes; the change is archived with `--skip-specs`.
- Version: no bump (test-only fix inside 0.37.0's release candidates).
