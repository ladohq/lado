## 1. The model on Codex's command line

- [ ] 1.1 `tests/test_codex.py` (unit): failing tests first, each with a repository
  `.codex/config.toml` naming `model = "gpt-5.6-terra"` in the test's repo: the session's model
  `gpt-5.6-luna` gives argv `["codex", "--no-daemon", "-m", "gpt-5.6-luna", ...]` and
  `Launch.model` `gpt-5.6-luna` from `session`; a carried user model (top level, and of the chosen
  profile) gives `-m <it>` and `cli-config`; a model server's model gives `-m <server model>`; no
  model anywhere gives no `-m`. Existing argv assertions gain `-m` only where a model is set
  (requirement "A Codex agent runs on its model whatever its repository's Codex config names";
  AC-1, AC-2, AC-3).
- [ ] 1.2 `src/lado/providers/codex.py` `launch_command`: `-m <model>` right after `--no-daemon`
  from `_setting(config, "model")` after `_choose_model` and `_on_server` (design D1); a comment
  says the repository's `.codex/config.toml` wins over the agent's config.toml and `-m` over both,
  checked by hand with Codex CLI 0.162.0. Tests of 1.1 pass.

## 2. The repository's model when nothing else names one

- [ ] 2.1 `tests/test_codex.py` (unit): failing tests first: no model from LADO or the user and the
  repository's `model = "gpt-5.6-terra"` gives `Launch.model` `gpt-5.6-terra`, source `cli`, detail
  `the repository's .codex/config.toml`, and no `-m`; a nearer `sub/.codex/config.toml` wins for an
  agent in `sub`; a worker's worktree reads its own file; an `untrusted` entry in the user's config,
  an invalid TOML file and a file without `model` give `Launch.model` None
  (requirement "A Codex agent on its repository's model shows it from the start"; AC-4, AC-5).
- [ ] 2.2 `src/lado/providers/codex.py`: a reader of the repository's model by Codex's lookup
  (design D2, sharing the folder walk with `_repo_hook_files` where it fits), used in
  `launch_command` only when the config names no model and the folder is trusted. Tests of 2.1
  pass.

## 3. End to end with the real CLI

- [ ] 3.1 `tests/smoke/test_smoke.py` `test_the_session_s_model_reaches_the_cli`, Codex only: the
  smoke repo gets `.codex/config.toml` with `model = "smoke-model"` (a model the endpoint serves)
  before the start; the test asserts the endpoint is asked for `smoke-model-2` and never for
  `smoke-model` (design D4; AC-1). Written and run with `make test-smoke PROVIDER=codex` when Codex
  CLI is installed here; otherwise the build report says "written, not run" and CI's smoke runs it.

## 4. Docs and the regression run

- [ ] 4.1 `src/lado/providers/codex.py`'s docstring or comments, and `docs/design/agents.md` where a Codex agent's model is described
  (its model paragraph, lines 221-232: `Codex \`model\` at the top level and in the carried profile`): the model goes on the command
  line too, and why; the repository's model is shown when nothing else names one.
- [ ] 4.2 CHANGELOG.md: `## 0.45.1 (unreleased)` on top, under Fixed a line: a Codex agent runs on
  the model chosen in LADO or in your Codex config, even when the repository's `.codex/config.toml`
  names another (LAD-263).
- [ ] 4.3 The settings' Checks: `make lint`, `make test`, `openspec validate
  codex-model-over-repository-config --strict`, the trial archive in a copy, and
  `openspec validate --specs --strict`; all green, test counts as numbers in the build report.
