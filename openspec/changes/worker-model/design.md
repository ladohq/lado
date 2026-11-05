## Context

From the last change the epic branch has `model_settings.start_model`, `session_row`,
`check_default`, `check_launch`, `check_start`, `agent_servers`, `StartModel`, `Refused`,
`choices`, `Provider.model_list`, `runs_on_server`, and in `runtime` the start's `_start_model` and
`ModelRefused`. `runtime.spawn_worker` calls `start_model`, `check_launch` and `agent_servers`.

The human's decisions: D39 of the epic (by name, a kit names no model), D44 (a session's model is
where an agent starts, not a limit), the answer 3a of #3279 (a spawn checks the server as a start
does), and #3655, all four as recommended. The plan with each task's tests:
`docs/superpowers/plans/2026-11-05-worker-model.md`.

## Goals / Non-Goals

Goals: the supervisor sees what can run and names it; no silent swap; a worker on a silent server
never starts. Non-goals: the proposal's Out of scope.

## Decisions

### D1. One reading of a name

`model_settings.worker_start(name, given, session_cli, env, listing)` returns the worker's
`(Provider, StartModel)`. It only picks the CLI (`_name_cli`, D2) and then goes the session's way:
`session_row(name, cli, env(cli), listing)`, `PowerTable.of(row)`, `start_model(table, cli)`, with
`dataclasses.replace(start, source=state.SUPERVISOR_CHOICE)` when a model was named. So `check_default`
stays the one reading of a typed name: the saved-and-built-in clash, a hidden character, an entry
removed meanwhile are refused by the code that refuses them at a start.

### D2. The CLI of a name

`_name_cli(name, given, session_cli, env, listing)`, `owns(p)` being: the name is `p`'s saved model,
alias or listed model.

| `provider` | Found | Result |
|---|---|---|
| given | `owns(given)`, or `given` has no full list and no other CLI owns it | `given`; a free name warns (D3) |
| given | another CLI owns it | Refused: `<name> is a model of <other>, not of <given>` |
| given | nobody | `check_default`'s own refusal: `<name> is not in <given>'s list…` |
| none | `owns(session_cli)` | the session's CLI |
| none | exactly one other | that CLI |
| none | several others | Refused: `<name> is a model of <A> and <B>; give provider`, in the order of `providers.names()` |
| none | nobody | Refused: `<name> is in no agent CLI's list of models; list_models shows them`, with `; <title> gives no full list: provider="<cli>" starts it with a warning` for a session's CLI with none |

A saved model of another CLI uses the existing `_not_its_model` line. Other CLIs are the installed
ones (`shutil.which` on `env(p)`'s PATH, as `_installed_cli`), read only on a miss, once each, through
one cached `listing`. A list that fails counts as not owning.

### D3. A free name

A CLI with no full list cannot refuse, so at a start it warns. A spawn with no `provider` is refused
instead (#3655, 2): an agent's typo must not cost a worker. With an explicit `provider` it goes on,
and `check_start`'s WARN verdict is the warning, as at a start.

### D4. `model=""`

`session_row` already reads it as the CLI's own settings; `start_model` gives `StartModel()`, with
the source `cli`, which is true: nobody chose a name. The CLI is `given` or the session's.

### D5. The check at a spawn

`runtime._worker_start(sess, provider, model, layers)` replaces the three calls: it picks the CLI
and start, runs `check_start`, then `agent_servers`, and returns the CLI, base environment, start,
servers and warnings. A WARN verdict goes first into the warnings, as `_start_model` does. It runs
before the worktree, as today, so a refusal leaves nothing. `spawn_worker`'s `_check_permission_mode`,
`_check_commands` and `check_login` move after it, since they need the worker's CLI. The check is
for every worker: `check_start` asks nothing of a start with no model, so a session with none
behaves as before.

`check_launch`'s docstring loses "its server's check is not made yet".

### D6. The refusal's way out

`way_out` speaks of `--model`, which an agent cannot use. A spawn's refusal of a model not given adds
`; list_models shows the others, model="" is the CLI's own settings`, and of a model given nothing:
the refusal names it already. Like the start, through `ModelRefused(refused, tail)`.

### D7. `list_models`' result

```json
{"clis": [{"cli": "opencode", "title": "OpenCode", "session": true,
           "starts_on": "Локальная Qwen", "note": null,
           "builtin": ["opencode/big-pickle"],
           "external": [{"name": "Локальная Qwen", "server": "LM Studio дома", "blocked": null}]}]}
```

By CLI, not by row: Kilo CLI lists 320 models, and a name each is the cheapest form for a context
window. `provider` narrows it to one CLI. The session's CLI goes first. `starts_on`: `start_model`'s
`name`, null for the CLI's choice. `note`: the list's `why`. `blocked`: the line of `check_launch` on
that entry, so Claude Code's says it runs on no server yet, from the same rule that refuses it.
`server` is a saved name, never an address or a key. It is built from `choices`, the one place that
computes a CLI's models, so no second list exists. `model_settings.cli_models(...)` makes it,
`runtime.list_models(session, provider)` gives the layers' environment and turns `Refused` into
`ModelRefused`. A CLI not installed is left out; a `provider` not installed is refused.

### D8. Who gets the tool

The supervisor, read-only or not, next to `recommend`: it reads and starts nothing, so it is no
`COMMAND_TOOLS` entry and the read-only contract stays as it is. Workers do not get it: nothing of
theirs uses it.

### D9. The source

`state.SUPERVISOR_CHOICE = "supervisor"`, `MODEL_SOURCES` words `chosen by the supervisor`. The
server sends `source_words`, so `web/` does not change. `report_model` needs nothing: it does not
look at the source.

`agent_shown` takes the chosen entry only for `session` and `default`. A supervisor's choice is
looked up by `shown`, by server and model: two entries of one model on one server may then show
under the other's name. The model and the server are the same, so nothing false is said about what
runs; keeping the entry's id would need a column.

### D10. Run workers

`runs.spawn_worker` passes `model` on. A refusal comes before the step is taken, so the step still
waits for a worker and the supervisor may try again.

### D11. Texts

`SUPERVISOR_INSTRUCTIONS` gets a `list_models` line and the rules of #3655: leave `model` out unless
the human or the task names one; after a refusal tell the human the reason and ask, never pick
another by yourself; `model` holds for that spawn only, also after a resume and for the next worker
of a run. `spawn_worker`'s description says the same in short, and its `provider` line, which lacks
`codex`, is corrected.

## Risks / Trade-offs

- A spawn may wait up to the probe's or a list's timeout (5 s, 15 s), one list per other CLI on a
  miss. The MCP call blocks for it. Accepted: it is rare and the refusal saves a worker.
- A built-in session model's list is read at every spawn. Accepted for one rule; a list that fails
  only warns.
- `model` can move a worker to a CLI with no login: `check_login` refuses it, as with `provider`.
