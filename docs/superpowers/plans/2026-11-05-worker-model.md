# A worker on a model by name: Implementation Plan

**Goal:** the supervisor sees the models of every installed agent CLI and starts a worker on one by
name; a model that cannot run refuses the spawn before anything of the worker exists.

**Architecture:** the rules in `model_settings.py`, calling the existing reading and checks;
`runtime.py` replaces the spawn's three model calls by one; `runs.py` passes `model` on;
`mcp_server.py` holds the tools; a new source token in `state.py`.

**Tech Stack:** Python 3.10+, pytest (`-n auto`, `-m integration`), `tests/fake_model_server.py`, the
fake agent (`tests/integration/fake_agent.py`, `fake_provider.py`).

**Spec:** `openspec/changes/worker-model/` and `docs/superpowers/specs/2026-11-05-worker-model-design.md`.

## Global Constraints

- No new Python or npm dependency. Past ~15 code files (tests aside): stop and ask whether it is
  still this task. The estimate is 5.
- The server check is the probe's, with its timeout; no new wait. No agent CLI's global config is
  touched. No schema change, no `web/` change.
- No second reading of a name and no second list of models: `check_default`, `choices`.
- Nothing in code, docs, specs or the UI names the epic's steps; `docs/epics/` is not touched.
- Refusals exact as in the delta.

## Review Focus

1. A key anywhere but the worker's environment: a tool's result, a refusal, `loop.log`, a config
   file. Test: task 6.
2. A refused spawn leaving a branch, worktree, row, queued task, or a run's step taken. Test: tasks
   3, 5.
3. `model=""` against no `model`, on a session with a table and a CLI with a default. Test: tasks 2, 3.
4. A name that is a saved model of one CLI and a built-in of another; ignoring case for saved names.
   Test: task 2.
5. A list that fails or overruns on another CLI during a miss: counts as not having the name. Test:
   task 2.

## Tasks

### Task 1: the source (D9)

Files: `src/lado/state.py`. Test: `tests/test_state.py`.

- [ ] Test: `source_words("supervisor", None, "Claude Code") == "chosen by the supervisor"`; fails.
- [ ] Add `SUPERVISOR_CHOICE = "supervisor"` and its words to `MODEL_SOURCES`, passes.
- [ ] Commit `An agent's model can be chosen by the supervisor (LAD-208)`.

### Task 2: a name finds its CLI (D1-D4)

Files: `src/lado/model_settings.py`. Test: `tests/test_model_settings.py`.

Produces: `worker_start(name: str, given: Provider | None, session_cli: Provider, env: Env, listing:
Listing) -> tuple[Provider, StartModel]`, `Refused` otherwise.

```python
def worker_start(name, given, session_cli, env, listing):
    name = name.strip()
    cli = _name_cli(name, given, session_cli, env, listing) if name else given or session_cli
    row = session_row(name, cli, env(cli), listing)
    start = start_model(state.PowerTable.of(row), cli)
    return cli, replace(start, source=state.SUPERVISOR_CHOICE) if name else start
```

`_name_cli` follows design D2's table, `owns` being a saved model of that CLI (`state.model(name)`,
ignoring case) or a name in `listing(p)`'s aliases or models.

- [ ] Tests, each failing first, one per row of D2: the session's CLI; one other CLI; several; none;
  none with a session's CLI of no full list; given and owned; given with no full list and a free
  name; given and another's saved model; given and another's built-in model.
- [ ] Tests of the Review Focus: saved in one CLI and built-in in another (the session's CLI first,
  `check_default`'s clash kept); a saved name in another case; another CLI's list with `models`
  None, or not installed, owns nothing; the session's own hit reads no other list (a `listing` that
  records its calls).
- [ ] Tests: `model=""` gives `StartModel()` past a table and a default; a named model's `source`.
- [ ] Implement; `uv run pytest tests/test_model_settings.py -n auto`.
- [ ] Commit `A name given for a worker finds its agent CLI (LAD-208)`.

### Task 3: the spawn (D5, D6, D10)

Files: `src/lado/runtime.py`, `src/lado/runs.py`. Tests: `tests/test_runtime.py`, `tests/test_runs.py`.

Consumes: `worker_start`. Produces: `spawn_worker(..., model: str | None = None)` in both modules,
as a keyword after `warnings` in `runtime` and `runs`, so that existing positional calls hold.

`_worker_start(sess, provider, model, layers)` returns the CLI, `base_env`, start, servers and
warnings. It holds one cached `listing` (factor it out of `_start_model`), calls `start_model` with
`sess.power` for `model is None`, else `worker_start`; then `check_start`, `agent_servers`. A WARN
verdict goes first into the warnings; `Refused` becomes `ModelRefused(refused, tail)`, `tail` by D6.
`_check_permission_mode`, `_check_commands` and `check_login` go after it. Remove the comment and
the docstring's "no server's check yet".

- [ ] Tests, failing first: a silent `fake_model_server` refuses with `model` given and with the
  session's model, the tail in the second only; nothing is left: no row, branch, worktree, window,
  message; a name's WARN in `warnings`; no table and no default read no list and ask no server;
  `sess.power` unchanged after a spawn with a model; a next worker with no `model` on the session's.
- [ ] Test in `tests/test_runs.py`: a refused `spawn_worker` leaves the step waiting, a second call
  takes it; `model` reaches `runtime.spawn_worker`.
- [ ] Implement; run both files with `-n auto`, and `tests/test_session*` for the start's listing.
- [ ] Commit `A spawn checks its worker's model and takes one by name (LAD-208)`.

### Task 4: the tools (D7, D8, D11)

Files: `src/lado/model_settings.py`, `src/lado/runtime.py`, `src/lado/mcp_server.py`. Tests:
`tests/test_model_settings.py`, `tests/test_mcp_server.py`.

Produces: `model_settings.cli_models(session: state.Session, only: Provider | None, env: Env,
listing: Listing) -> list[dict]`; `runtime.list_models(session: str, provider: str | None) -> dict`.

Each entry as D7: `choices(p, listing)` gives the models; `start_model(session.power, p).name`
gives `starts_on`, with `None` for an unreadable table's `Refused`; `blocked` is `str(refused)` of
`check_launch(_external(saved, state.SUPERVISOR_CHOICE), p)`, else None.

Texts of D11, in `SUPERVISOR_INSTRUCTIONS` and the tools' docstrings:

```
- list_models: the models of each installed agent CLI, for spawn_worker's `model`.
spawn_worker's `model`: leave it out unless the human or the task names a model; the worker then
starts on the session's model. It holds for that one spawn, so give it again for a next worker or
after a resume. When a model is refused, tell the human the reason and ask: never pick another by
yourself. "" is the CLI's own settings.
```

- [ ] Tests, failing first: D7's shape, the session's CLI first; `provider` narrows; a CLI not
  installed left out, and refused by name; `blocked` for Claude Code; `starts_on` per CLI; a
  `fake_model_server` that counts requests sees none; no address or key in the result.
- [ ] Tests in `tests/test_mcp_server.py`: the supervisor and a read-only supervisor have the tool;
  a worker's call is unknown; `spawn_worker` has `model` and passes it with `run` and without; a
  refusal is the tool's error; the instructions hold the three rules.
- [ ] Implement next to `recommend`; correct `provider`'s line to name `codex`.
- [ ] Commit `The supervisor lists the models and is told how to choose (LAD-208)`.

### Task 5: end to end through `lado mcp` (requirements of `worker-model`)

Files: `tests/integration/fake_agent.py` (a command `spawnmodel <name>@<provider or -> <model> <task>`
next to `spawnwith`, and `listmodels`), new `tests/integration/test_worker_model.py`.

- [ ] A worker on a listed model: its command line, record, source; the session's table unchanged.
- [ ] A worker of another CLI by the name alone (`fake` and `fake-stop`, the saved model on a
  `fake_model_server` when the fake provider runs on a server, else a listed name).
- [ ] A run's worker with `model`; a refused one leaves the step waiting.
- [ ] A silent server: refused within the probe's timeout, `git branch` and tmux show no worker.
- [ ] `listmodels` returns both CLIs.
- [ ] `uv run pytest -m integration -n auto tests/integration/test_worker_model.py`, exit status
  read from a log outside the tree.
- [ ] Commit `A worker on a model, end to end through lado mcp (LAD-208)`.

### Task 6: the key's canary

Files: `tests/integration/test_session_model_canary.py`.

- [ ] A supervisor of one CLI spawns a worker on a keyed server's model: the key is in the worker's
  environment, not in the supervisor's, its config files, `list_models`, the tool's result, a
  refusal with the server stopped, or `loop.log`.
- [ ] `uv run pytest -m integration -n auto tests/integration/test_session_model_canary.py`.
- [ ] Commit `The key's canary covers a worker on a model by name (LAD-208)`.

### Task 7: docs, the archive's trial

Files: `docs/design/agents.md` (the paragraph at "`spawn_worker` makes the local checks only"),
`docs/design/modules.md` (`mcp_server.py`, `model_settings.py`), `docs/cli.md` (the "worker spawned
with another provider" lines), `CHANGELOG.md`.

CHANGELOG, `## 0.45.0 (unreleased)`, `### New`:

```markdown
- **Start a worker on another model.** The supervisor sees every agent CLI's models with
  `list_models` and names one in `spawn_worker(model=…)`; a silent server or a missing model
  refuses the worker at once, instead of failing at its first turn.
```

- [ ] Update each; `make lint`; `make test`; `openspec validate worker-model --strict`.
- [ ] Trial archive on a copy of `openspec/`, `openspec validate --specs --strict` there; result in
  the pull request's description, with the manual check: branch, folder, commands, expected,
  `env | grep LADO_` and `unset`, own `LADO_HOME` and `LADO_TMUX_SOCKET`; a real supervisor spawns a
  worker on an external model.
- [ ] Commit `Docs and the changelog say a worker takes a model by name (LAD-208)`.
