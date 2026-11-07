## 1. The bridge reaches a remote endpoint

- [ ] 1.1 `tests/test_local_models.py` (unit, first, red): the bridge's config for an endpoint
  holds its base URL and `os.environ/LADO_LIVE_API_KEY`, not the value; LM Studio's keeps its
  `/v1` and `api_key: none`; `codex_bridged()` is true only with an endpoint and the switch.
- [ ] 1.2 `tests/local_models.py`, `tests/live/conftest.py`: `Bridge.start`'s full upstream and
  `key_variable`, the switch, the fixture's upstream, the `ENDPOINT` branch of `live_provider`
  (design.md D6, D7), the conftest's docstring.

## 2. The live cell

- [ ] 2.1 `tests/test_smoke_ci.py` (unit, first, red): `live` runs the pytest command of design.md
  D4; a summary with a skip is red; the key's value is gone from every file under `<out>`, the log
  and the evidence included, on a pass and on a failure; no key set leaves the files as they are;
  an unknown provider, and `claude`, exit 2.
- [ ] 2.2 `scripts/smoke_ci.py`: `install` split out of `run`, `live`, `redact`, its docstring and
  USAGE (D4, D5).

## 3. The workflow

- [ ] 3.1 `tests/test_live_workflow.py` (unit, first, red): the triggers are exactly `schedule` and
  `workflow_dispatch`; the matrix is codex, opencode, kilo on ubuntu; the job names environment
  `live`; the secret stands only in the test step's `env`; `permissions` is `contents: read`;
  checkout has `persist-credentials: false`; concurrency does not cancel; no other workflow names
  `live` or the secret; `ci.yml` has no live job.
- [ ] 3.2 `.github/workflows/live.yml` (D1 to D3, D5), actions pinned as ci.yml's;
  `tests/test_workflow_security.py`'s list of workflows gains it. Model and switch by D8's first
  guess until task 4 fixes them.

## 4. The trial (needs the human's yes and key; design.md D9, D10)

- [ ] 4.1 Ask the human, through the supervisor, for the yes and the trial's key. No paid request
  before it.
- [ ] 4.2 Run the order of D10; write the report as artifact `trial-report` and to
  `docs/superpowers/reports/2026-11-07-cloud-live-tests-trial.md`: providers and scenarios, model,
  direct or bridge, cost of a run, passes out of three, each failure's cause. The key in no file.
- [ ] 4.3 `live.yml` gets the model and `LADO_LIVE_CODEX_BRIDGE` the trial settled; the workflow's
  test still passes.

## 5. Documents

- [ ] 5.1 docs/testing.md: the live section, "never a paid model", "Live tests are not in CI",
  layer 6, the new variable, `live.yml`, the environment and the cost. AGENTS.md's Testing,
  layer 6. `tests/test_agents_md.py` passes.
- [ ] 5.2 `openspec validate cloud-live-tests --strict`, `openspec validate --specs --strict` and
  the trial archive of `.lado/sdlc.md`'s Checks.
