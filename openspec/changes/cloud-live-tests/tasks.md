## 1. The trial, first (needs the human's yes and key; design.md D6, D9, D10)

- [ ] 1.1 Ask the human, through the supervisor, for the yes and the trial's key. No paid request
  before it. No code of this change is needed for the trial.
- [ ] 1.2 Codex direct on `qwen/qwen3.7-flash`, then on `openai/gpt-5-nano`. Both fail: stop, ask
  the human through the supervisor (bridge to OpenRouter or a direct OpenAI key), report
  `redesign` with the answer; nothing below is done.
- [ ] 1.3 Claude Code with the variables of design.md D15 on `anthropic/claude-haiku-5.5`, then on
  `qwen/qwen3.7-flash`. Both fail: stop, ask the human through the supervisor.
- [ ] 1.4 OpenCode and Kilo, then three full runs of the chosen setup. Red on both models: stop,
  report `redesign`.
- [ ] 1.5 The report as artifact `trial-report` and in
  `docs/superpowers/reports/2026-11-07-cloud-live-tests-trial.md`: providers and scenarios, model,
  cost of a run, passes out of three, each failure's cause. The key in no file.

## 2. One setup for four providers

- [ ] 2.1 `tests/test_live_models.py` (unit, first, red; renamed from `tests/test_local_models.py`):
  no endpoint is a problem naming the three variables; the key's and the model's as before;
  `SETUPS` has every provider of LADO; Claude Code's entry gives the base URL without `/v1`, the
  token, the models; the LM Studio and bridge tests are gone.
- [ ] 2.2 `tests/live_models.py` (renamed), `tests/live/conftest.py`, `tests/live/test_live.py`,
  `tests/real_clis.py`: the removal of design.md D7, `SETUPS` (D14), Claude Code's entry and
  `check_models` (D15), the docstrings.

## 3. The live cell

- [ ] 3.1 `tests/test_smoke_ci.py` (unit, first, red): `live` runs the command of D4; `<out>` is
  empty while the tests run and after a crash; the key's value is gone from what reaches `<out>`
  on a pass and on a failure, the log and the evidence included; a skip is red; an unknown provider
  exits 2.
- [ ] 3.2 `scripts/smoke_ci.py`: `install` split out of `run`, `live`, `redact`, docstring, USAGE
  (D4, D5).

## 4. The workflow

- [ ] 4.1 `tests/test_live_workflow.py` (unit, first, red): the triggers are exactly `schedule` and
  `workflow_dispatch`; the matrix's providers are `PINS`, each with a model; environment `live`; the secret only in the test step's `env`;
  `permissions` is `contents: read`; `persist-credentials: false`; concurrency does not cancel; no
  other workflow names `live` or the secret.
- [ ] 4.2 `.github/workflows/live.yml` (D1 to D3) with the trial's models, actions pinned as
  ci.yml's; `tests/test_workflow_security.py`'s list gains it.

## 5. Documents

- [ ] 5.1 docs/testing.md: the live section without LM Studio, what a skip means, no default
  endpoint, the rule on paid models, `live.yml`, the environment, the cost, layer 6. AGENTS.md's
  Testing, layer 6. The rule "Claude Code only with the human's yes" goes from both. docs/release.md, section 2,
  step 3 (D13). The gap of D16 in docs/testing.md. BACKLOG.md's two entries on LM
  Studio's flakes: a line that LM Studio left the live tests. `tests/test_agents_md.py` passes.
- [ ] 5.2 `make lint`, `make test`, `openspec validate cloud-live-tests --strict`,
  `openspec validate --specs --strict` and the trial archive of `.lado/sdlc.md`'s Checks.
