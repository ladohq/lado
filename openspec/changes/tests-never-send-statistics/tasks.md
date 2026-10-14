## 1. The guard

- [ ] 1.1 `tests/conftest.py`: an autouse fixture (after `lado_home`), e.g.
  `_no_statistics(request, lado_home)`: before the test, `telemetry.state().off_by ==
  "LADO_TELEMETRY=0"`, else fail with one line naming `LADO_TELEMETRY=0` and the conftest;
  after it, unless `"telemetry_on" in request.fixturenames`, fail when
  `lado_home/telemetry/sent.json` exists or `lado_home/telemetry/outbox/` holds a file,
  naming the path and `telemetry_on`. Import `lado.telemetry` inside the fixture (the
  conftest's top imports stay as they are). Check: `make test` green (AC-1, AC-4); by
  hand, the guard fails a scratch test that deletes `LADO_TELEMETRY`, stores the yes and
  writes `sent.json` without `telemetry_on`, and fails every test with the conftest line
  commented out (AC-2, AC-3); the scratch test is not committed.
- [ ] 1.2 `tests/test_isolation.py`: `lado telemetry status` run as a subprocess (the way
  the suite runs the CLI in one, `interpreter.run_module` or `sys.executable -m lado.cli`)
  prints `statistics: off: LADO_TELEMETRY=0 is set`. Check: `uv run pytest -n0
  tests/test_isolation.py` (AC-5).

## 2. The release candidate's checklist

- [ ] 2.1 `docs/release.md` section 4: the clean install's commands start with
  `LADO_TELEMETRY=0 LADO_HOME=$(mktemp -d) LADO_TMUX_SOCKET=lado-rc`, "with the same
  variables" kept for the start and stop, and one sentence: the scratch home is a new
  install to PostHog, so it never sends and `lado start` does not ask; the upgrade of the
  human's own LADO stays their install, counted once as before. Check: read through (AC-6).
- [ ] 2.2 `tests/test_telemetry.py`, next to `test_docs_list_every_field`: every line of
  `docs/release.md` with `LADO_HOME=$(mktemp -d)` has `LADO_TELEMETRY=0` in the same
  command (the same line, as the docs write it); the failure names the line. Check:
  `uv run pytest -n0 tests/test_telemetry.py` (AC-7).

## 3. Docs

- [ ] 3.1 `docs/telemetry.md`: a paragraph, LADO's own tests (every layer, live included)
  and the release checks never send: the suite runs with `LADO_TELEMETRY=0`, checked for
  every test, and the RC's scratch install too. Check: read through.
- [ ] 3.2 `AGENTS.md`, Commands (the tests' environment, the sentence on
  `LADO_TELEMETRY=0`): the autouse guard checks it before each test and, after one without
  `telemetry_on`, that nothing was sent or queued. Check: read through.

## 4. Regression

- [ ] 4.1 `make lint`, `make test`, `openspec validate tests-never-send-statistics
  --strict`, `openspec validate --specs --strict` (AC-8). The integration, UI and smoke
  layers get the guard through the conftest; CI runs them.
