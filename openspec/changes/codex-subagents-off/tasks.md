## 1. The failing tests

- [ ] 1.1 `tests/test_codex.py`, `test_the_agent_does_not_update_itself_nor_start_its_own_agents`:
  also `config["features"]["multi_agent_v2"] is False` and `config["agents"] == {"enabled":
  False}`; its docstring names the two versions and the model's metadata (proposal, Why).
  Fails before 2.1. Run: `uv run pytest -n0 tests/test_codex.py`.
- [ ] 1.2 `tests/test_codex.py`, the Codex supervisor's first input (around
  `argv[-1] == f"[from lado] {runtime.FIRST_INPUT}"`): also pin the text, the argv ends with
  `[from lado] session started; nothing to do yet: end this turn, the next message starts a
  new one`; and a unit test that `FIRST_INPUT` has no word `wait`. Fails before 2.2.
- [ ] 1.3 `tests/fake_endpoint.py`: keep the tool names of each request beside its method
  and path (each tool's `name`, a namespace's tools as `<namespace>.<name>`, from `tools` and
  from `input` items of type `additional_tools`, where Codex 0.162 puts them for newer
  models); the log file's JSON line gets them too. Standard library only, as now.
- [ ] 1.4 `tests/smoke/test_smoke.py`, a Codex-only test (marker `smoke`, provider
  `codex`), scenario "A model whose metadata turns the subagents on": the smoke home's
  config.toml with `model = "gpt-5.6-sol"`; first the control, a plain `codex exec "hi"` on
  that home, whose request carries `collaboration.wait_agent` (else the test fails with a
  line saying the model no longer brings Codex's subagents: re-check the cause, D4); then a
  LADO session of provider `codex`: once its first input is delivered, its request carries
  tools (`exec_command` or `functions.exec`) and no `collaboration` namespace, no
  `spawn_agent`, no `wait_agent`. Fails before 2.1. Run: `make test-smoke PROVIDER=codex`
  (CI runs it on Linux and macOS).
- [ ] 1.5 `tests/live/test_codex_login.py`, scenario "The human's first message after the
  start": a new session without `prompt`; the supervisor's start turn ends (idle); the human
  writes "hi" (`runtime.write_as_human`); the supervisor replies to the human with
  `send_message` and goes idle; the supervisor's Codex rollout (`sessions/` of its home) has
  no call of `spawn_agent` or `wait_agent`. Written, not run without the human's ChatGPT
  login: the build report says so; the human runs it before the merge.

## 2. The fix

- [ ] 2.1 `src/lado/providers/codex.py`, `launch_command`: `features.multi_agent_v2 = False`
  and `agents = {"enabled": False}` beside `multi_agent`; the comment says the model's
  metadata turns version 2 on, `agents.enabled` is the switch that wins over it, and
  `multi_agent_v2` is checked before it (D1, D2). 1.1 and 1.4 pass.
- [ ] 2.2 `src/lado/runtime.py`, `FIRST_INPUT` = `session started; nothing to do yet: end this
  turn, the next message starts a new one`; its comment says it must end the turn, not ask
  to wait (D3). 1.2 passes; `tests/test_runtime.py` and the smoke tests that compare with
  `runtime.FIRST_INPUT` still pass.

## 3. Docs

- [ ] 3.1 `docs/design/agents.md`: the background paragraph ("LADO switches its subagents
  off") and the first-input paragraph name the keys (`features.multi_agent`,
  `features.multi_agent_v2`, `agents.enabled`), why all three (the model's metadata), and that
  the first input asks the agent to end its turn.
- [ ] 3.2 `docs/design/modules.md`, Codex CLI: "subagents (`features.multi_agent`)" becomes
  both versions with the three keys.
- [ ] 3.3 `docs/testing.md`, the smoke: the endpoint keeps each request's tool names; the
  Codex test of the subagent tools and its control.
- [ ] 3.4 CHANGELOG.md, `## 0.44.0 (unreleased)`, `### Fixed`: **A Codex agent no longer hangs
  on "Waiting for agents".** Newer OpenAI models brought Codex's own subagents back; the
  supervisor waited for them and the human's messages were not delivered.

## 4. Checks

- [ ] 4.1 `make lint`, `make test`, `openspec validate codex-subagents-off --strict`,
  `openspec validate --specs --strict`; `make test-smoke PROVIDER=codex` locally (Codex
  0.162.0 is in the container) or by CI on the pull request.
- [ ] 4.2 The live test of 1.5 by the human with a ChatGPT login, before the merge; and the
  manual check: a new Codex session, "hi" gets an answer.
