Task: LAD-308

## Why

Symptom: on the release candidate 0.48.0rc1 (commit 39d18386), `live.yml` run 44731944817 has
the cells `live opencode` and `live kilo` red with `not passed (exit 0): 5 passed, 1 skipped`;
the cells of Claude Code and Codex are green with 6 passed. The skipped test is
`tests/live/test_live.py::test_an_agent_pushes_through_a_saved_git_server` (LAD-303). Its red
cells block the tag `v0.48.0rc1`.

Cause: the test is meant for Claude Code and Codex only, and says so by calling `pytest.skip`
in its body for every other provider. The fixture `live_provider` is parametrized over all four
providers, so the test is collected for OpenCode and Kilo too and skips there. A live cell
(`scripts/smoke_ci.py live`) passes only with a pass and no skip (continuous-integration, "A
live cell passes only with a pass and no skip"), because a skip there usually means a missing
environment (no CLI, no endpoint, no key, `LADO_LIVE_IMAGE` unset). The rule is right; the test
reports "not meant for this provider" as a skip, which the rule cannot tell from a missing
environment. Nothing in LADO's product code is wrong.

Options weighed:

- A (taken): the test narrows the fixture to the two providers it is meant for,
  `@pytest.mark.parametrize("live_provider", ["claude", "codex"], indirect=True)`, and its
  `pytest.skip` goes. The test then has no item for OpenCode and Kilo: `-k opencode` collects
  their five tests and no skip (checked by the analyst with `--collect-only`: 5 for opencode and
  kilo, 6 for codex). The cell's rule stays as strict as it is. Long-term cost: one decorator;
  a test that should later run for OpenCode or Kilo adds the name to the list.
- B: `smoke_ci.py` accepts a declared skip (a reason with a fixed prefix, or a marker it reads
  from pytest's report). The script would have to parse skip reasons and keep a second notion
  of which skips count, and a wrong prefix in a future test would quietly turn a missing
  environment into a pass: against "No silent drops". Long-term cost: a looser rule for every
  live, smoke and container cell, and one more thing to keep true.
- C: a general marker (`live_providers(...)`) read in `tests/live/conftest.py`'s collection
  hook. It does what A does through extra machinery for one test: against "Only what is used";
  worth it only when a second test needs it.

## What Changes

- `tests/live/test_live.py`: `test_an_agent_pushes_through_a_saved_git_server` runs only for
  Claude Code and Codex by an indirect parametrization of `live_provider`; the `pytest.skip`
  for other providers is removed.
- `docs/testing.md`: the live paragraph says that a test meant for some providers only is not
  collected for the others (a skip would make their cell red), as the push test is.
- The continuous-integration requirement "A live cell passes only with a pass and no skip"
  gains a scenario: a test meant for some providers is not collected for the others, and their
  cell passes.
- Neither a minor nor a patch of its own: tests and docs only, users see nothing, so no
  CHANGELOG.md line; the version stays 0.48.0rc1 (an allowed fix for the RC while main is
  frozen).

## Scope

- `tests/live/test_live.py`, `docs/testing.md`. Nothing in `src/`, `scripts/` or `web/`.

## Out of scope

- `scripts/smoke_ci.py`'s pass rule (option B): it stays "a pass and no skip" for every cell,
  so a missing endpoint, key or CLI still turns a cell red.
- A shared marker for provider-limited live tests (option C): one test needs it today.
- Making the push test work for OpenCode and Kilo: LAD-303 chose Claude Code and Codex for it;
  widening it is its own task.
- Tagging `v0.48.0rc1` and the runs on main after the merge: the supervisor's, by the release.

## Acceptance criteria

- AC-1: `uv run pytest -m live --collect-only -q -k <provider> tests/live/test_live.py`
  collects `test_an_agent_pushes_through_a_saved_git_server` for `claude` and `codex` and not
  for `opencode` and `kilo`; the test's body has no `pytest.skip`.
- AC-2: The test's assertions and steps for Claude Code and Codex are unchanged.
- AC-3: `scripts/smoke_ci.py`'s pass rule is unchanged (`passed()` and its unit tests in
  `tests/test_smoke_ci.py` untouched).
- AC-4: `make lint`, `make test` and `openspec validate live-push-test-only-where-it-runs
  --strict` pass; the pull request's CI is green.
- AC-5: After the merge, `live.yml` on main's head is green in all four cells (the supervisor's
  run before the tag; not a condition of the merge).

## Impact

- `tests/live/test_live.py`, `docs/testing.md`, the continuous-integration spec.
- Users: nothing changes.

## Decisions for the record

- Scale tweak (agreed with the human in the task): a test's known shape, tests and docs only;
  review by precision.
- Option A over B: the cell's strict rule is what caught the missing environments before; it
  stays one rule for all cells.
- Option A over C: one test, one decorator ("Only what is used").
- `indirect=True` on `live_provider`, not a new fixture: the CLI check, the endpoint check and
  the setup of the fixture stay the same for the two providers.
- Test layer: the change is to a live test; it is proved by pytest's collection (AC-1) locally,
  without a model, and by `live.yml` after the merge (AC-5). No new test: a unit test that
  greps live tests for `pytest.skip` would guard one line the live cell already guards.
- Neutral core: the test stays for two providers, as LAD-303 decided; the other two are said
  out loud by the parametrization instead of a skip.
