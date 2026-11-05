## Context

The epic branch has the session's table (`state.PowerTable`, `PowerRow(cli, model)`, JSON in
`sessions.power`), its check (`model_check`), its way to an agent (`runtime.session_model`,
`_power`, `_changes`, `_launch_command`, `AgentSpec.model`, each provider's `launch_command`), the
free-text Model field (`Launch.tsx`, `SuggestField`, `ModelNote`), and from the last two changes
`state.ModelRef`, `models.id`, `cli_defaults`, `model_settings.choices`, `check_default`,
`set_default_ref`, `_on_server`, `probe_saved`, `server_key`, `Provider.server_api`,
`external_whole_process`, `model_servers.plain_http_warning`, `ModelPicker.tsx` with `where:
"settings"`.

The human's decisions: the external-models concept; question #3523 (the CLI's settings are a
choice; a session with no choice follows the current default; the source words; http warnings for
every server in the config; Settings in a new tab). The mock-ups: the flow runs
`ui-design/model-picker` (§5, section 11) and `ui-design/launch-model` (refusals, the agent's page),
and this run's `mockup-session-model.html`, which wins where the words differ. The check with the
real CLIs: this run's `check-model-in-cli`. Plan:
`docs/superpowers/plans/2026-11-05-session-start-model.md`.

## Goals / Non-Goals

Goals: an agent starts on the right model with its source said; OpenCode and Kilo CLI keep every
ticked model and every built-in one; a key lives only in the environment; loud refusals. Non-goals:
the proposal's Out of scope.

## Decisions

### D1. The table's row

`PowerRow(cli: str, model: str, model_id: str | None = None, name: str | None = None)`. Three
forms, all JSON in `sessions.power`, so no schema change:

| Form | Fields | Means |
|---|---|---|
| built-in | `cli`, `model` | the rows that exist today, unchanged |
| external | `cli`, `model`, `model_id`, `name` | the entry's id; `model` and `name` are copies for words after its removal |
| settings | `cli`, `model: ""` | the CLI's own settings, past any default |

A launch always reads an external entry and its server by id, so a rename or a new address
applies. `PowerTable.single(cli, model)` stays; `PowerTable.of(row)` fills the levels.

### D2. A tolerant table

`from_json` returns a table for every text: JSON that does not parse, a top level or row that is
no object, a row without a string `cli` or `model` give `PowerTable.unreadable()` (`rows` empty,
`readable` False); unknown keys are ignored. `row()` is never called on an unreadable table
without a check: `model_settings.start_model` refuses it. `_model_words` reads `an unreadable
model`. Session lists, the feed and `lado ls` never raise.

### D3. One function says what an agent starts on

`model_settings.start_model(power, provider) -> StartModel`, reading no network and running no CLI:

1. a readable table whose row's CLI is the provider's: the row (source `session`; form settings:
   no model, source `cli`);
2. else the provider's default (`state.cli_defaults`), source `default`;
3. else no model, source `cli`.

`StartModel(name, model, server, entry, source, note, gone)`: `note` is `the session's model
<model> is for <CLI>` for a table of another CLI; `gone` for an entry no longer saved. It replaces
`runtime.session_model`. `spawn_worker` and `start_session` both call it, so a default at the
moment of each launch applies.

### D4. A name is read once

`model_settings.session_row(name, provider, env, listing=None) -> PowerRow`: `""` is the
settings form; else `check_default` reads it (a built-in name or an external model's name, one
reading, its refusals as they are) and the reference becomes a row. `start_session`'s `_power` takes
the row. A name that is only another CLI's model is refused by `_not_its_model`; the model never
changes the session's CLI (variant B of the window).

### D5. The check before a start

`model_settings.check_start(start, provider, env, probe=None) -> Verdict`:

- no model: DEFAULT, no request;
- `gone`: refused;
- no server: `model_check.check` (the list, as for a kept model today);
- a server and `not provider.runs_on_server`: refused with no request (D6);
- a server: `_on_server`, the same full probe as saving a model, each request within
  `model_servers.TIMEOUT`, no new wait. Why not one `GET /v1/models`: one rule with Settings and
  `lado model add`, and it sees a server that stopped speaking the CLI's API.

`start_session` calls it for the supervisor before anything is stored, for a model given, kept or
default. `Refused` becomes `LadoError`. The tail of a refusal says the way out by where the model
came from: kept (`the session ran on it before: …`), default (`it is <CLI>'s default model: …`).
LADO's own resume goes the path a kept model's refusal has. `spawn_worker` makes the local checks
only (`gone`, D6), no probe: its server check is later work.

### D6. Neutral core: the provider says whether it runs on a server

`Provider.runs_on_server: bool = False`; True on `OpenCodeFamily`. The refusal names the providers
that run on one and whose `server_api` the server proved, in LADO's order; none: `no agent CLI runs
on it yet`. Claude Code and Codex join by their provider alone. No provider's name above
`providers/`.

### D7. The config of the OpenCode family

`AgentSpec.servers: tuple[ServerEntry, ...]`, `ServerEntry(id, name, base_url, key_variable, key,
models)`, `key` with `repr=False`; `models` pairs of id and saved name.
`model_settings.agent_servers(provider) -> (entries, warnings)` groups the provider's external
models by server, for a provider with `runs_on_server` and not `external_whole_process`. Config:

```json
"provider": {"lado-<server id>": {
  "npm": "@ai-sdk/openai-compatible",
  "name": "LADO · <server name>",
  "options": {"baseURL": "<address>/v1", "apiKey": "{env:LADO_MODEL_KEY_<ID>}"},
  "models": {"<model>": {"name": "<saved name>"}}}}
```

No `apiKey` for a server with no key. Checked on both CLIs: `name` of the provider is the group in
`/model` and the label beside the model, `name` of the model its row, a key-less server and an id
with a slash work. `Provider.server_model(server_id, model)` gives `lado-<server id>/<model>`;
`base.Provider`'s raises. The server's id never changes, so a rename breaks nothing; the prefix
keeps the user's providers apart. The risk of the cancelled design, a first fetch of the npm
package, did not show: both CLIs ship it; the developer confirms it in the container.

### D8. The model on the command line too

Kilo CLI keeps the last `/model` pick in its user state and prefers it to `model` of the config;
OpenCode does not; `--model` beats it on both. `OpenCodeFamily.argv` adds `--model <spec.model>`
when one is chosen, `model` stays in the config for what reads it there. With nothing chosen the
CLI's memory stands: that is its own settings. Not checked: `--model` with `--agent plan`, to be
covered by the smoke.

### D9. The keys

`Launch.env[key_variable] = key`, `LADO_MODEL_KEY_<ID upper>`, in the reserved prefix. Nothing but
the env file that `agent_env.command` removes on reading holds it. A key file that cannot be read:
for the server the agent starts on, the check refuses (`server_key`); for another server its
models are left out, with a warning. The canary covers config, `lado.db`, output, log, errors and
API answers.

A key holding `"` or `\` goes the same way as one that cannot be read: both CLIs put a variable's
value into the config's text as it is (checked with `debug config`, OpenCode 1.18.35 and Kilo CLI
7.8.8), so OpenCode stops and prints the text with the key, and Kilo drops the whole config, LADO's
plugin and MCP with it. `check_launch` refuses it, so the window sees it too.

### D10. Text that the CLIs would expand

OpenCode and Kilo CLI substitute `{env:…}` over the config's text; `{file:…}` is taken to work the
same way (not checked). A server name, a saved name or a model id, the last from a server's answer,
could carry one. A model or server with `{env:` or `{file:` in those is left out of the config
with a warning, and refused as a start model. Unit test.

### D11. The http warning

`plain_http_warning(server.address, key)` for each server of `agent_servers`, with the launch's
warnings (stderr of `lado start`, the session's start warnings, `spawn_worker`'s). The window shows
only the chosen model's, in its own words (the human's answer 4).

### D12. Sources

`DEFAULT_MODEL = "default"`: `default in Settings`. `CLI_CHANGED = "cli-changed"`: `changed in the
agent CLI`, set by `report_model` where it sets `CLI_DEFAULT` for a model that differs today;
effort stays. `AgentSpec.model_source` feeds `Provider.session_choice`. A first report still keeps
the source.

### D13. Recognising LADO's models

`Provider.on_server(reported) -> (server_id, model) | None`; the family parses `lado-<id>/<rest>`,
the first slash ending the provider. `model_settings.shown(provider, model) -> Shown(name, model,
server, address) | None` finds the server and the provider's entry of that model, live. Used for
`ModelInfo`, `list_agents` and `lado ls`. `agents.model` keeps the CLI's form, so `same_model` needs
no change. A server removed since: the CLI's form as it is. A model of the server with no entry:
its id and server.

### D14. The API

- `POST /api/session-model/check` `{cli, model, project}` → `SessionModelCheck(ModelCheck +
  retry: bool, short: str, peek: str, warnings: list[str], server: str | None)`: D4 and D5 for the
  window, in the project's agents' environment; a refusal is a 200 of kind refused; `text` the
  window's line, `peek` a few words for the folded Advanced (`not answering`).
- `NewSession.model`, `Resume.model`: the same name; `""` the CLI's settings; absent as now. A
  refusal of the model is a 409 `ModelRefusal` with `field: "model"`, so the window puts it under
  Model; `runtime.ModelRefused` carries the core's refusal to it.
- `SessionInfo.model`: None for no choice, `""` for the CLI's settings, else the name; adds
  `model_missing: bool`.
- `ModelInfo` adds `configured`, `server`, `address`. `make web-types`, both files committed.

### D15. The window

`ModelPicker` takes `where: "launch"`: the field's name `Model`, the mark `default`, the foot's
line, `aria-invalid`. `Launch.tsx` loses `SuggestField` for Model and `ModelNote`; the list is the
chosen agent CLI's, by `useModelChoices`. Sending: a field left on the default, or on the settings
with no default, sends nothing; `<CLI>'s settings` with a default sends `""`; a pick sends its name.
Agent CLI stays changeable in Resume, as the code has it (the mock-up says off); the field follows
it. The check runs when a value is in the field, the preselected default too, and Start stays on
meanwhile; a stale answer is dropped. The foot's link opens `/settings#models` in a new tab, and the
window reads the list again on `focus`: nothing typed is lost. `Other name…` works as in Settings. The field takes the whole row of
Advanced: in one column a name, an id and a server do not fit.

### D16. Inherit mode: a worker without its spawner's launch

Root cause of `test_a_worker_of_another_cli_runs_its_default_and_says_so`: tests run with
`LADO_AGENT_ENV=inherit`; `spawn_worker` runs in the supervisor's `lado mcp`, whose environment
holds the supervisor's launch, so the worker inherits it, and whether its first hook lands before
the test reads is the race. A product bug: the same carries `OPENCODE_CONFIG_CONTENT` and a server's
key into a worker of another CLI. Every launch adds `LADO_LAUNCH_VARS`, the names of
`providers.agent_env(agent)` and `launch.env`; `agent_env.layers` in inherit mode drops those names
and itself. The test then asserts after the worker's first hook: it fails every time without the
fix.

### D17. The window's flaky test

`Launch.test.tsx:1077` belongs to the free-text field, which goes. Every new test waits for the
list with `findByRole`.

### D18. Doctor and Settings

`doctor.check_default_models` prints `Default models` only when a default is set: `WARN` for a
server that does not answer (from the probes `check_model_servers` made, not again), a model it
lacks, a built-in name its CLI no longer lists. Its exit status is as without it. `LEAD`,
`LEAD_NO_MODELS` in `ModelSettings.tsx` get the delta's words.

### D19. What a session last started on

The human's condition at the gate: a resume on a moved default says `changed model: … -> …`. A
stop forgets the agents' rows, so a resume cannot read the last model there; a second record in
`sessions` would mean a schema change. An event `start_model`, written when the supervisor's model
differs from the last one, holds it as the CLI was told it (`state.last_start_model`, "" with no
record: a session of an older LADO with no table ran on the CLI's choice). It shows in `lado log`;
the UI's feed shows only the kinds it lists. `lado start` prints the line once, from `changes`; the
start's warnings and loop.log hold it too.

### D20. A hook process does not load the HTTP client

`runtime` imports `model_settings` inside the launches: every hook process imports `runtime`, and
`model_servers` would add about 15 ms to each. `tests/test_lazy_imports.py` keeps it so.

### D21. From the design QA of the working build

- Tab goes from the rows or the search into the list's foot, and closes the list only past its last
  control: the link and ↻ were out of the keyboard's reach. The picker is one, so Settings has it too.
- During Check again the refusal and its buttons stay, the button off as `Checking…` with
  `aria-disabled`, so the focus stays on it, and Start stays off for a refusal already known. A first
  check still leaves Start on (D15).
- A kept model no longer saved has a row of its own above the groups: it is no built-in model.
- An agent keeps the name it started on (`model_settings.agent_shown`, by the session's or the
  default's entry), so a twin saved later does not take it; two entries of one CLI, model and server
  stay allowed, and only a model changed through `/model` is looked up by its id.

## Risks / Trade-offs

- The probe at every start costs up to a few seconds on a slow server; each request stays within
  its timeout.
- A server that dies after the start shows at the agent's turn; the check at a worker's spawn is
  later work.
- D38's price: every ticked server's key is in each such agent's environment, so its tools can read
  it. Decided by the human.
- A custom model has no context limit in the CLI's config: long sessions on a small local model may
  overflow. LADO knows no limit to give; the manual check looks at it.
- Kilo CLI's group of LADO's models stands below its 300 models; search by name or server finds it.
- A worker on a default in a CLI that cannot run it is refused: until the human changes the
  default, no such worker starts. Loud, and it goes away with Claude Code and Codex on a server.

## Migration Plan

None: `sessions.power` is JSON and old rows read as built-in. Rolling back within the epic: an older
build reads a row with new keys as an error; that build never shipped.

## Open Questions

None.
