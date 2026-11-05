# A worker on a model by name: design

The supervisor sees what the session's machine can run and starts a worker on it by name; a model
that cannot run refuses the spawn before anything exists. The rules are in
`openspec/changes/worker-model/`; this document holds why the pieces fit.

## The problem

`spawn_worker` reads the model from the session alone and checks only what needs no network. Two
results: the case the concept wants (a supervisor on a cloud model, a worker on the human's server)
needs another session, and a worker on a silent server costs a worktree, a window and a task, then
fails at its first turn.

## The shape

```
spawn_worker(model, provider)                 list_models(provider)
        │                                             │
 runtime._worker_start                         runtime.list_models
        │                                             │
 model_settings.worker_start                   model_settings.cli_models
   _name_cli → the CLI                           choices → the CLI's models
   session_row → start_model                     start_model → starts_on
        │                                        check_launch → blocked
 model_settings.check_start, agent_servers
        │
 the launch, as today
```

Nothing new reads a name or computes a list: `_name_cli` only picks which CLI's reading to use, and
`cli_models` only shapes `choices`. The launch is untouched: `StartModel` reaches `_spec` and the
providers as it does at a start, with another `source`.

## How it holds against the principles

- **Neutral core.** All of it sits above `providers/` and uses `model_list`, `runs_on_server` and
  `launch_name`. It works with all four CLIs; on Claude Code and Codex external models are refused
  and marked `blocked` by the rule that refuses them at a start, until they run on a server.
- **One source of truth.** The worker's model is not stored apart from the agent's record; the
  session's table does not change; the models come from `choices`.
- **No silent drops.** A refusal for each miss; a free name warns; the supervisor must not swap a
  refused model by itself, and the card says who chose.
- **Only what is used.** No `power`, no effort, no memory of a choice, no probing in `list_models`.

## What a supervisor does

1. By default nothing changes: it leaves `model` out.
2. The human asks for a worker on the home server: `list_models`, then `spawn_worker(model="Локальная
   Qwen")`. The name picks OpenCode, and the result's `warnings` say anything the launch warns of.
3. The server is off: the tool fails with the reason. The supervisor tells the human and asks.
4. The session's own server is off: every worker with no `model` fails the same way. The refusal
   offers `list_models` and `model=""`; the human decides.

## Tests by layer

| Requirement | Layer | Why there |
|---|---|---|
| The CLI of a name, each refusal, a free name, `model=""` | unit | pure logic over lists and lado.db |
| `list_models`' shape, no request to a server | unit | fake lists, `tests/fake_model_server.py` |
| A spawn checks; nothing left after a refusal; a run's step still waits | unit, integration | the order against git and tmux crosses processes |
| The worker starts on the model, on another CLI, in a run, through `lado mcp` | integration | MCP, hooks, tmux |
| The key's canary | integration | environments and files of real processes |
| The tool for the supervisor only; the texts | unit | `tests/test_mcp_server.py` |
| The source's words | unit | `tests/test_state.py`; `web/` shows the server's words, so no UI test |

No smoke or live test is added: the launch of each CLI on a model is covered by the last change.
The human's manual check covers a real supervisor on a real server.
