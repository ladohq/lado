Task: LAD-180

## Why

The human keeps model servers, external models and a default model per agent CLI in Settings →
Models, and no session uses them: the launch window's Model field takes a name typed by heart,
a default is read by nothing, and no agent reaches a model server. The epic's main scenario,
agents on a model of the human's own server next to the CLI's built-in ones, needs a session to
refer to a model, and a provider to put the servers into its agent.

Root cause: a session's power table holds a CLI and a raw name, so it cannot refer to an external
model; nothing says which model an agent starts on when the session chose none; and the providers
know no model server. A second cause showed in the check with the real CLIs: Kilo CLI's remembered
`/model` pick beats `model` of its config, so even a built-in session model can be silently
replaced there.

Options weighed for the way to a server:

- A (taken): each server a provider of the agent's config content (`provider.lado-<server id>`
  with `@ai-sdk/openai-compatible`), its key named as `{env:…}` and given through the environment.
  Checked in the real TUIs of OpenCode 1.18.35 and Kilo CLI 7.8.8 on two servers: `/model` lists
  them beside the built-in models, a switch sends the right key to the right server. Long-term
  cost: one config shape per CLI family; Claude Code and Codex get their own ways later.
- B: a local proxy in LADO that adds the key: no key in any agent, but a process per session,
  streaming to pass through, one more thing that hangs. Rejected for now.
- C: the provider in a config file with its key: a secret on disk, against the key's rule.
  Rejected.

Options weighed for what a session keeps:

- A (taken): the table's row keeps a model reference only when the human chose; a session with
  no choice follows the CLI's default as it is at each launch. One source of truth for a default;
  a default changed in Settings reaches the next resume and the next worker.
- B: the default copied into the table at the first start. A session's model never moves by
  itself, but Settings then silently stops acting on older sessions, and a second record of the
  default drifts.

Held against the coming stages: a worker on a model by name reuses the resolved start model and
its check; effort sits beside the reference; Claude Code and Codex on a server join by their
provider's `runs_on_server` alone; the power table's later rows take the same reference.

## What Changes

- A session's table row refers to a model: built-in (a CLI and its name, the rows that exist
  already) or external (the entry's id, with a copy of its name and model for words after its
  removal), or the CLI's own settings. No schema change: the table is JSON in `sessions.power`.
- `PowerTable.from_json` reads an unknown or missing key and a broken table without breaking the
  session lists; such a session's resume is refused with the way out.
- An agent starts on the session's model, else on its CLI's default model, else as before. A
  worker of another CLI takes its own CLI's value.
- `lado start --model <name>` reads a name as `lado model default` does: a built-in name of the
  session's CLI or an external model's name. `--model ''` and the row `<CLI>'s settings` mean the
  CLI's own settings for this session, past any default, kept at a resume.
- A session's model is where an agent starts, not a limit. Every external model ticked for
  OpenCode or Kilo CLI goes into each of their agents' config, one provider per server, marked
  `LADO · <server>`, in any case: a built-in model chosen, an external one, nothing.
- Every such server's key reaches the agent in its environment only, as `{env:…}` in the config.
- The OpenCode family also takes the model as `--model`, which beats Kilo CLI's remembered pick.
- Before a start and each resume the model the agent starts on is checked: its server answers
  and has it, or its CLI lists it; else a loud refusal, and LADO's own resume leaves the session
  stopped with the reason. A silent server of another ticked model stops nothing. A model on a
  server for a CLI that runs on none yet is refused, naming the CLIs that do. A key over plain
  http to a public address is warned about for every server in the agent's config.
- The launch window's Model field becomes `ModelPicker` for the chosen agent CLI, with the
  default chosen in advance, the refusals and their way out, and Settings → Models in a new tab.
  The window says "agent CLI".
- The agent's page names the external model, its id, server, address and the source, Kilo CLI
  too; a model switched through `/model` is recognised by its provider id. New sources:
  `default in Settings`, `changed in the agent CLI`.
- `lado doctor` names a default that cannot start. Settings → Models says the default is used.
- A worker no longer takes its spawner's launch variables when agents inherit the starting
  process's environment: the cause of one flaky test, and a way a key could reach another CLI.
  The other flaky test goes with the old field.

## Out of scope

- `list_models`, `spawn_worker(model=…)` and a server check at `spawn_worker`: the next work; a
  worker spawned while its server is down fails at its first turn until then.
- Effort and the polish of the key's form: their own work.
- Claude Code and Codex on a server: later work of the epic; until then refused with the CLIs
  that can.
- The power table by level: a session still fills its rows with one model.
- Keeping a default fixed for a session: option B above.
- Settings → Models beyond the words about the default being used.
- A proxy for the key (option B above).
- Changing the user's remembered pick when nothing is chosen: that is the CLI's own settings. An
  agent starts from it, and its own later picks stay with the agent (D8).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `session-model`: a model reference in the table, the start model's order, the CLI's settings as
  a choice, all ticked models beside the built-in ones, checks of a server, refusals, the window's
  field, a tolerant table, a worker without its spawner's launch.
- `agent-model`: two sources, a model recognised by its provider id, the agent's page.
- `configured-models`: sessions use the external models and the defaults.
- `model-servers`: a key's way to the agents; doctor on the defaults.
- `model-settings-page`: the words that the default is used.

## Impact

- Code, about 21 files: `src/lado/state.py`, `model_settings.py`, `runtime.py`, `agent_env.py`,
  `cli.py`, `doctor.py`, `mcp_server.py`, `model_servers.py`, `providers/base.py`,
  `providers/opencode_family.py`, `server/app.py`, `server/launch.py`, `server/models.py`,
  `server/model_entries.py`; `web/src/Launch.tsx`, `ModelPicker.tsx`, `Agents.tsx`,
  `ModelSettings.tsx`, `api.ts`, `styles.css`; generated `web/openapi.json`, `web/src/api.gen.ts`.
- Docs: `docs/install.md`, `docs/cli.md`, `docs/design/ui.md`, `docs/design/agents.md`,
  `docs/design/modules.md`, CHANGELOG.md (0.45.0, New).
- Tests: unit, integration with the fake agent and `tests/fake_model_server.py`, smoke of OpenCode
  and Kilo CLI on a fake server, vitest, UI e2e, the key canary.
- No schema migration, no new dependency. A feature and a CLI change: minor, 0.45.0 (the epic's).
