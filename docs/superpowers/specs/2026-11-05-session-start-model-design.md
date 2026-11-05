# A session on a model reference — design

Task LAD-180. The change: `openspec/changes/session-start-model/` (proposal, deltas
`session-model`, `agent-model`, `configured-models`, `model-servers`, `model-settings-page`,
design.md D1-D18). The human's answers: question #3523. The mock-ups: this run's
`mockup-session-model.html`, and the flow runs `ui-design/model-picker` (§5, section 11) and
`ui-design/launch-model` (refusals, the agent's page). The check with the real CLIs: this run's
`check-model-in-cli`.

## What the human sees

The launch window's Advanced has a Model field: the same picker as Settings → Models, for the
chosen agent CLI, with its default already in it. Leaving it alone starts on the default and follows
that default later. Another pick holds for this session. `<CLI>'s settings` lets the CLI choose,
past the default. `lado start --model` takes the same names, and `--model ''` the same settings.

Inside OpenCode and Kilo CLI, `/model` lists every model ticked for that CLI in a group `LADO ·
<server>` beside the built-in ones, whatever was chosen. The agent's page names the model, its
server and where the choice came from, also after a switch through `/model`.

Before a start or resume LADO asks the server of the model the agent starts on. A refusal names what
is wrong and the way out; LADO's own resume leaves the session stopped with the reason.

## How it fits

- Store: no schema change; `PowerRow` gets optional `model_id` and `name`, an empty `model` means
  the CLI's settings.
- Core: `model_settings.start_model`, `session_row`, `check_start`, `agent_servers`, `shown`; the
  session model's parts of `runtime` call them. `model_check` keeps its rule.
- Providers: `runs_on_server`, `AgentSpec.servers`, `server_model`, `on_server`; the family writes
  providers and passes `--model`. `Launch.env` carries the keys.
- API: `POST /api/session-model/check`; `NewSession`, `Resume`, `SessionInfo`, `ModelInfo`.
- UI: `ModelPicker` with `where: "launch"`, `Launch.tsx`, `ModelFact`, two leads of Settings.

## Against the roadmap and the principles

- Next changes: a worker by name calls `start_model` and `check_start` with a named row; effort
  sits beside the reference; Claude Code and Codex set `runs_on_server` and read `AgentSpec.servers`
  their own way; power rows hold the same row.
- Neutral core: above `providers/` only `runs_on_server`, `server_model`, `on_server`. Works with
  OpenCode and Kilo CLI; Claude Code and Codex are refused loudly.
- One source of truth: a default is never copied into a session; entries are read by id at each
  launch; one reading of a name (`check_default`), one list (`choices`), one picker.
- No silent drops: every model left out of a config and every unread key is a warning.
- Never touch the user's global config: all goes through the agent's config content, argv and
  environment. Kilo CLI's own memory is passed over by `--model`, not edited.
- Only what is used: no schema change, no new dependency, no new wait.

## Test layers

| Requirement | Layer |
|---|---|
| table, row forms, sources, `report_model` | unit |
| start model's order, reading a name, checks, servers, `shown`, names left out | unit |
| family's config, `--model`, key variable | unit |
| start model reaches the agent; all ticked models in each of three cases; refusals; LADO's own resume; silent other server; a default changed before a resume | integration, fake agent and fake server |
| key canary; a worker of another CLI; inherit mode | integration |
| real OpenCode and Kilo CLI on two fake servers, `--agent plan` | smoke, CI |
| the field, notes, refusals, stale answers | vitest |
| window, Resume, Settings in a new tab, the agent's page, 390 px | UI e2e |
| real LM Studio, external LiteLLM, Docker | manual, the human |
