## Context

Codex CLI 0.162.0 builds its config from layers: the agent's `$CODEX_HOME/config.toml`, then, in a
trusted folder, each `.codex/config.toml` from the project root down to the folder it runs in (the
nearest wins), then the command line (`-m`, `-c`). Checked by hand in throwaway homes with
`codex exec` against a closed local port, reading the `model:` line of its header:

| Agent config | Repository | Command line | Runs |
|---|---|---|---|
| `model = "luna-agent"`, repo trusted | `model = "terra-proj"` | none | `terra-proj` |
| same | same | `-m luna-flag` | `luna-flag` |
| same | `profile = "pp"`, `[profiles.pp] model = …` | `-m luna-flag` | `luna-flag`; profile ignored with a warning |
| same | `model_provider = "openai"`, `[model_providers.evil]` | `-m luna-flag` | provider stays the agent's; both keys ignored with a warning |
| same | `model = "terra-wt"` in a linked worktree | none | `terra-wt` (the worktree's own file) |
| same | `sub/.codex/config.toml` `model = "terra-sub"`, run in `sub` | none | `terra-sub` |
| repo `untrusted` | `model = "terra-main"` | none | `luna-agent` |

## Decisions

### D1. The model goes on the command line, from the config LADO wrote

`launch_command` adds `-m <model>` after `--no-daemon` when the agent's config holds a model after
the carried settings, `_choose_model` and `_on_server` have run: the value Codex would take from
that config by `_setting(config, "model")` (the chosen profile's, else the top level's). One
source: the argument is read from the config LADO writes, so the two cannot disagree, and a server
agent gets its server's model with no second path. The model stays in config.toml too: Codex's
`/model` and its own reads of the file still see it.

Reason: Codex's command line is the only layer above the repository's, and it is the way Claude
Code (`--model`) and the OpenCode family (`--model`) are already told their model.

### D2. The repository's model is read by Codex's lookup, only when nothing else names one

With no model in the agent's config and its folder trusted (`trust[1] == "trusted"` in
`launch_command`), LADO reads `model` from the nearest `.codex/config.toml` from the agent's folder
up to `_project_root(cwd)` that names a non-empty string, skipping the agent's own Codex home as
`_repo_hook_files` does. The folder is the agent's own checkout (a worktree's own file, as the
table shows), not the main checkout's. An unreadable or invalid file counts as naming nothing:
Codex itself warns about it. The launch's model is then
`state.Choice(<model>, state.CLI_DEFAULT, "the repository's .codex/config.toml")`.

Reason: the source `cli` already means "the CLI's own choice: its default or its own settings";
a new source token would be a field no other provider uses. The detail says where it came from.

### D3. No warning

A repository's model that differs from the agent's gives no warning or launch note.

Reason: the human's answer to #5408/#5419; the agent's page names the model it runs on.

### D4. Tests

- Unit (`tests/test_codex.py`): the argv and `Launch.model` for each scenario of the delta, with a
  repository `.codex/config.toml` in the test's repo; the existing argv assertions (`["codex",
  "--no-daemon", ...]`) gain `-m` only where their spec names a model.
- Smoke (`tests/smoke/test_smoke.py`, real Codex CLI, the fake endpoint): the session's model test
  for Codex gets a repository `.codex/config.toml` naming another model the endpoint serves, and
  asserts the endpoint was asked only for the session's model. It guards the CLI fact D1 rests on
  against a new Codex version. No integration test: `fake-codex` does not run Codex's launch, and
  everything LADO does here happens inside one process (`launch_command`); the runtime's recording
  of `Launch.model` is covered already.
