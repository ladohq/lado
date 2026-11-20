Task: LAD-295

## Why

Symptom: the smoke test `tests/smoke/test_smoke.py::test_the_session_s_model_reaches_the_cli[kilo]`
failed in the cell `smoke macos-latest kilo` of PR #324 (run 44075941136, attempt 1, head
73e7b8f3) with `AssertionError: ['`kilo models` timed out after 15 s: LADO cannot check
smoke/smoke-model-2; a wrong name stops its agents at their first turn']`; the other 13 kilo
tests passed, and the rerun of the cell passed (the same test in 25 s from its start to its
end). The pull request did not touch the model check. In the first attempts of all CI runs of
the month before (2026-10-20 to 2026-11-20) it is the only smoke failure of kilo; the two other
macOS smoke failures were codex's, for other reasons.

Cause: LADO's behaviour is as specified, and the test's limit is too tight for its machine.
Before a session starts with a model, LADO runs the CLI's list command and gives it
`base.MODEL_LIST_TIMEOUT` (15 s); after that the command is killed and the session starts with
the warning that LADO cannot check the model (session-model, "A CLI's list of models is its own
and local"). The test asserts that kilo starts with no such warning. Kilo 7.8.8's `kilo models`
fetches its gateway's list of about 400 models from the network on every call, and in the smoke
each test gives it a fresh, empty home (its first run: database migration, project indexing).
Measured by the analyst in LADO's container (Linux): 1.6-1.7 s, cold or warm. Since LAD-280
(2026-11-14) a smoke cell runs its tests on three pytest-xdist workers, so on the macOS runner
three real CLIs start at once beside this call; the failure came three days later. A slow
network answer on a loaded runner is the suspected cause; which part of the call stalled is not
recorded (the evidence keeps the agent's files, not the list command's log).

For users the limit stays as it is (the human's decision at design, #7693): a user's check runs
one at a time on a CLI whose cache is filled, and a CLI over the limit still starts the session,
with the warning. A longer limit would make a hanging CLI hold the start and the launch window
that much longer.

Options weighed:

- A (taken): the smoke gives a CLI's list command 60 s (`base.MODEL_LIST_TIMEOUT` patched in the
  fixture every smoke test goes through), and the test keeps its strict assertion. A slow list
  passes; a CLI whose list never answers still fails the test, with the same warning, 45 s
  later. Long-term cost: one line in the fixture; the smoke no longer proves the users' 15 s
  on a CI runner, which no test claimed to (the unit test
  `test_a_list_command_over_its_time_gives_no_list` proves the timeout itself).
- B: the test accepts the timeout warning for kilo. The test would stay green if `kilo models`
  hung on every call, and the check that the session's model is in kilo's list would silently
  go away: against "No silent drops". Long-term cost: a smoke that can no longer catch a broken
  list command.
- C: raise `MODEL_LIST_TIMEOUT` for everyone (e.g. 30 s). Not chosen by the human: it changes
  what users wait for, on evidence from one CI flake.

## What Changes

- `tests/smoke/conftest.py`: the fixture `smoke_provider` sets `base.MODEL_LIST_TIMEOUT` to
  60 s for the test (`monkeypatch`), for every provider, with a comment naming why.
- `docs/testing.md`: the smoke paragraph says that the smoke gives a list command 60 s, not the
  users' 15 s, and why.
- A requirement in continuous-integration says the same.
- Neither a minor nor a patch of its own: tests and docs only, users see nothing, so no
  CHANGELOG.md line, and no API, schema, MCP, CLI or UI change.

## Scope

- `tests/smoke/conftest.py`, `docs/testing.md`. Nothing in `src/` or `web/`.

## Out of scope

- `src/lado/providers/base.py` (`MODEL_LIST_TIMEOUT` stays 15 s): the human's decision (#7693);
  the product behaves as its spec says when a list is slow.
- Accepting the warning in the test (option B): it would hide a list command that never
  answers.
- Stopping kilo's network fetch in the smoke: Kilo 7.8.8 names no switch for it that LADO
  could rely on, and the users' kilo fetches it too, so the smoke should run it as they do.
- Fewer smoke workers on macOS: it would slow every cell (LAD-280) for one rare flake.
- A rerun inside pytest: the settings forbid automatic retries in pytest.
- Other smoke flakes (codex on macOS): each is its own task.

## Acceptance criteria

- AC-1: Every smoke test runs with `base.MODEL_LIST_TIMEOUT == 60`; the assertion of
  `test_the_session_s_model_reaches_the_cli` is unchanged.
- AC-2: The limit is shown to reach the check: with the fixture's value set by hand to a value
  below kilo's time (0.5 s) the test fails with `timed out after 0.5 s`, and with 60 it passes
  (`uv run pytest -m smoke -n0 -k "session_s_model_reaches_the_cli and kilo"`). The build
  report quotes both; the probe is not committed.
- AC-3: `make test-smoke PROVIDER=kilo` passes locally, its exit status read (not piped).
- AC-4: `make lint`, `make test` and `openspec validate smoke-model-list-time --strict` pass;
  the pull request's CI is green, the cell `smoke macos-latest kilo` on its first attempt.

## Impact

- `tests/smoke/conftest.py`, `docs/testing.md`, the continuous-integration spec.
- Users: nothing changes.

## Decisions for the record

- Scale hotfix: a defect of a test with a clear symptom; review by precision.
- 60 s: four times the users' limit and about 35 times the call's time measured here, still
  well inside a test's own waits of 120 s; a hanging CLI costs one minute, not the cell.
- In the fixture `smoke_provider`, not in the one test: every smoke test that starts a session
  with a model or reads a model list goes through it, so no other test can flake the same way;
  one place for the smoke's value.
- `monkeypatch.setattr` on `base.MODEL_LIST_TIMEOUT`, not a new environment variable: the smoke
  runs `runtime.start_session` in pytest's own process, so the patch reaches it, and no product
  knob is added for a test ("Only what is used").
- Test layer: smoke (the real kilo CLI is the only thing that can be slow); no new test.
- Neutral core: the value applies to every provider's smoke (Codex's `codex debug models` and
  OpenCode's `opencode models` go through the same limit).
