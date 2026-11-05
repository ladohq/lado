Task: LAD-208

## Why

A session's agents start on one model, and a worker can only follow it: the supervisor sees no
models and cannot name one, so "the supervisor on a cloud model, a worker on the human's server"
needs a second session. A worker whose model sits on a silent server is not refused either: it
fails at its first turn, after a worktree, a window and a task have been spent on it.

Root cause: `spawn_worker` takes the model only from the session (`model_settings.start_model`)
and makes the local checks only (`check_launch`); nothing tells an agent what models exist, as
`model_settings.choices` serves the UI alone.

Options weighed for how a name finds its CLI:

- A (taken): the name picks the worker's CLI. `list_models` shows every installed CLI, and whatever
  it shows can be named; the session's CLI goes first, then the others, several others are refused.
  Long-term cost: a worker may run on another CLI than its session's, which its card and
  `spawn_worker`'s result say, and a miss reads the other CLIs' lists.
- B: the session's CLI only, another CLI through an explicit `provider`. Stricter, but every
  external model of another CLI costs a refusal first, and the epic's main scenario is that case.

Options weighed for what is checked at a spawn:

- A (taken): `check_start`, the start's own check, for every worker with a model, given or not.
  One rule; a session with no model pays nothing.
- B: only a model given to `spawn_worker`. Cheaper for a session on a built-in model, but a worker
  on the session's silent server would still fail at its first turn, which is the defect.

Held against the coming stages: the local-models work reuses the same check; Claude Code and Codex
join by their provider's `runs_on_server` alone, and their refusal and `blocked` go away by
themselves; a later `spawn_worker(power=…)` resolves to the same `StartModel`.

## What Changes

- A new MCP tool `list_models(provider=None)`, the supervisor's: for each installed agent CLI, its
  built-in models, its external models with their servers, what a worker of it starts on with no
  `model`, why it has no full list, and why an external model cannot start yet. It asks no server.
- `spawn_worker(model=…)` starts a worker on a model by name, with its run too. With no `provider`
  the name picks the CLI: the session's first, then the only other that has it; a name of several
  other CLIs is refused naming them, a name of none is refused. With a `provider` the name is read
  for that CLI, and a name of another CLI is refused naming both. A name outside the lists of a CLI
  with no full list needs an explicit `provider`, and then starts with a warning, as `lado start`
  does.
- `model=""` is the CLI's own settings, past the session's model and any default, as `--model ''`.
- A worker's source is `supervisor`, in words `chosen by the supervisor`.
- Every spawn checks the model its worker starts on as a start does: its server by the probe within
  its timeout, a built-in model against its CLI's list; a refusal comes before a worktree or window
  exists. Claude Code and Codex on an external model are refused as at a start.
- The supervisor's text and the tools' descriptions say how to choose: leave `model` out unless the
  human or the task names one; after a refusal tell the human, never switch by itself; the choice
  holds for that one spawn. A kit still names no model.

## Out of scope

- `spawn_worker(power=…)` and the power table: moved to a new epic by the human.
- Effort: moved to the same epic.
- The launch window and Settings: nothing changes there; the agent's page shows the new source's
  words through the words the server already sends.
- Keeping a worker's model across a stop or within a run: the human's answer #3655. Agents' rows go
  at a stop, and a new record with its own rule is a task of its own if it is ever needed.
- The supervisor choosing a model by the weight of the work: that is what the power table is for.
- Claude Code and Codex on a server: later work; refused until then.
- Probing servers in `list_models`: it would cost the probe's timeout for each server on every
  call, and `spawn_worker` asks the one server that matters.

## Capabilities

### New Capabilities

- `worker-model`: `list_models`, `spawn_worker(model=…)`, how a name finds its CLI, the check at a
  spawn, the supervisor's rules of choice.

### Modified Capabilities

- `session-model`: a worker's `model` goes before the session's; another CLI's default holds only
  with no `model`.
- `agent-model`: the source `supervisor`.

## Impact

- Code, 5 files: `src/lado/state.py`, `model_settings.py`, `runtime.py`, `runs.py`,
  `mcp_server.py`. No schema change, no dependency, no change to `web/` or the server's API models.
- Docs: `docs/design/agents.md`, `docs/design/modules.md`, `docs/cli.md`, `CHANGELOG.md`.
- A minor bump (a new MCP tool), already due: `## 0.45.0 (unreleased)`, `### New`.
- A spawn with a model waits for the probe's timeout, or a list's, at worst; a session with no
  model and no default waits for nothing.
