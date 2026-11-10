Task: LAD-263

## Why

Found in the manual check of 0.45.0rc2 (finding 3), and so since 0.44.0: `lado start --provider codex
--model gpt-5.6-luna` in a repository whose `.codex/config.toml` has `model = "gpt-5.6-terra"` starts
Codex on terra. LADO records `gpt-5.6-luna` from `session`, the first hook turns it into
`gpt-5.6-terra · changed in the agent CLI`, and nothing at the start says so: a silent drop of the
model the human chose.

Cause, checked with Codex CLI 0.162.0 (`codex exec`, its header's `model:` line): LADO writes the
agent's model only into the agent's own config.toml (`_choose_model`,
`src/lado/providers/codex.py:473-474`). LADO trusts the repository (`codex.py:457-460`), so Codex also
loads the repository's `.codex/config.toml` (the nearest one from the agent's folder up to the
project root, in a linked worktree the worktree's own), and that layer wins over the agent's
config.toml. A model on the command line (`-m`) wins over both. Codex ignores a project's
`model_provider`, `model_providers`, `profile` and `profiles` ("Ignored unsupported project-local
config keys"), so the repository cannot take an agent off its model server, but its `model` can
send an unknown model name to that server. Claude Code and the OpenCode family already get the model
on their command line (`--model`), so a project file does not change it there; Codex is the only CLI
LADO tells its model through the config file alone.

Options weighed:

- A (taken): the model LADO's settings give a Codex agent goes on Codex's command line as well,
  `-m <model>`, whenever the agent's config carries one: LADO's choice (the session's, the default
  of Settings, the supervisor's, a model server's), else the model carried from the user's own Codex
  config. Long-term cost: one argument, the same way Claude Code and the OpenCode family are told
  their model; the rest of the repository's Codex config (its hooks, MCP servers, sandbox settings)
  keeps working.
- B: mark the repository `untrusted` in the agent's config, so Codex reads no project file at all
  (checked: the model then comes from the agent's config). It also switches off the repository's
  hooks, which LADO takes on purpose (agent-start-screens, "A Codex agent takes its repository's
  hooks without asking"), and the rest of what the team put in the file. Rejected by the human.
- C: keep the project's model and warn at the start. The human's choice is then still not what
  runs, and every start of every agent in such a repository warns. Rejected by the human.

## What Changes

- A Codex agent whose config carries a model (LADO's choice, else the user's carried one) is
  started with `-m <model>` on Codex's command line: it runs on that model whatever the
  repository's `.codex/config.toml` names.
- A Codex agent with no model from LADO and none from the user's Codex config runs on the model of
  the repository's `.codex/config.toml` when it names one, as before; LADO now records it at the
  launch with the source `cli` and the detail `the repository's .codex/config.toml`, so its page
  reads `gpt-5.6-terra · CLI default, the repository's .codex/config.toml` from the start instead
  of an empty model and later `changed in the agent CLI`.
- No warning or launch note: the agent runs on, and shows, the model it was given.

## Scope

- `src/lado/providers/codex.py`: `launch_command` (the argument, the launch's model) and a reader of
  the repository's model by Codex's lookup; the module's docstring or comments say what was checked
  by hand.
- Tests: unit (`tests/test_codex.py`), smoke (`tests/smoke/test_smoke.py`, real Codex CLI).
- `docs/design/agents.md` where a Codex agent's model is described;
  CHANGELOG.md, a Fixed line.

## Out of scope

- The reasoning effort: the repository's `model_reasoning_effort` also wins over the effort carried
  from the user's config, and LADO shows the carried one. The human leaves the effort for a later
  task (answer to #5419).
- Ignoring the repository's Codex config as a whole (option B): it would switch off the
  repository's hooks and the rest of the team's settings.
- Claude Code and the OpenCode family: they already get the model on the command line (`--model`),
  which wins over a project's settings; nothing changes for them.
- A note at the start when the repository names another model (option C): the agent shows the model
  it runs on, as Claude Code and OpenCode agents do without a note.
- An agent whose model is changed in its TUI (`/model`): already recorded as `changed in the agent
  CLI`, unchanged.

## Impact

- No CLI, MCP or API change, no schema change. A fix: patch, `## 0.45.1 (unreleased)`.
- Codex's argv gains `-m <model>` for every agent with a model; the model's name is no secret on the
  command line (Claude Code's `--model` puts it there already).
