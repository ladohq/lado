# The agent's model is visible: design

Task: LAD-169 (epic LAD-154). Change: `openspec/changes/agent-model-visible/` (proposal,
delta of the new capability `agent-model`, design.md D1-D9). Mockup: run artifact
`mockup-agent-model.html`.

## What the human sees

**The agent's page** (mockup, option A)

- The head line under the name: `role · provider · <model>`, e.g.
  `developer · codex · gpt-5.6-sol`; `CLI default model` while the CLI has named none.
- Two new facts first in the list: **Model** and **Effort**. Each shows the name in code
  type and, muted, where it came from: `CLI default` (the CLI's own choice) or
  `your Codex config` (carried from `~/.codex/config.toml`), with `, profile <name>` when
  a profile gave it. With no name, only the muted words.
- Cases: a Claude agent shows `claude-opus-5-5 · CLI default` and Effort `CLI default`; a
  Codex agent with a profile shows model and effort from `your Codex config, profile
  work`; a Kilo or OpenCode agent before its first prompt shows `CLI default` twice, then
  `anthropic/claude-sonnet-5-5 · CLI default` and its variant as Effort.
- The page updates by itself when the model becomes known (the agents feed).

**The Team chip's tooltip**: `developer · codex · gpt-5.6-sol`, the model only when known.

**`lado ls`**: the model's name, or `-`, after each agent's time and before its branch.

**Agents** (`list_agents`): `model`, `model_source`, `model_detail`, `effort`,
`effort_source`, `effort_detail` per agent.

## Facts the design rests on

Read in this run in the CLIs of LADO's image (proposal, Why): Codex 0.162.0 sends `model`
in every hook input LADO uses and no effort; Claude Code 2.1.295 sends `model` in
SessionStart in its interactive mode (checked by hand: `claude-opus-5-5`, and
`claude-sonnet-5-5` with `--model sonnet`) and no effort was seen; OpenCode 1.18.35's
`chat.message` plugin hook gets the user message with `model.providerID`, `modelID` and
`variant`. Kilo 7.8.8 shares OpenCode's plugin interface; its bundle is packed and was not
read.

## Options

- A (taken): columns of `agents` for model and effort with a source each; the providers
  translate fields of events they already get; Codex adds the carried config at launch.
- B: one JSON column: hides the shape from SQL and the journal for no gain, since later
  steps add values, not fields.
- C: ask the CLI or the model API: a process or network call per agent, refused by the
  task's limits.

Held against the principles: **Events, not screens**: only hook and plugin inputs, no
terminal. **Neutral core**: `Event.model`/`effort` and `Launch.model`/`effort` are
neutral; all four providers fill what their CLI gives, and where a CLI gives nothing the
agent says `CLI default` without a name (no silent guess). **One source of truth**: the
source words live in `state.source_words` only; the UI shows what the API gives. **Only
what is used**: two source tokens now; the detail is used by Codex's profile.

Against ROADMAP and the epic: the session's model, model servers, effort as a setting and
power tables come later and each writes a `Launch.model`/`effort` with its own source
token (`session`, `server`, `user`, `project`, `role`, `flow-step`, `supervisor`) through
the same `set_model`; the UI and API need no change of shape for them.

## Decisions for the record

- Separate sources for model and effort (D1): they already come from different places.
- Source tokens and words in one function of `state.py` (D2); an unknown token shows as
  itself.
- A reported name that differs from the chosen one makes the source `cli` (D5): the CLI
  runs another model than chosen, and the card must not claim otherwise.
- Claude Code's effort is not read: no hook gave it in the check; it shows `CLI default`.
- No write when nothing changes (D5): every Codex hook names the model, and the journal
  must not grow by one row per hook.
- `list_agents` gives tokens, the API words too (D6, D7).

## Testing

| Requirement | Layer | Tests |
|---|---|---|
| Every agent has a model and an effort, each with its source | unit (state, migration) | `tests/test_state.py`, the migration test from `previous_schema` |
| A Codex agent shows the carried model and effort | unit | `tests/test_providers.py` (Codex launch with and without a profile) |
| The model a CLI names becomes the agent's model | unit + integration + node | `tests/test_providers.py` (each `parse_event`), `tests/test_hooks.py`, `tests/js/` (plugin payload), `tests/integration/test_agents.py` (fake agent's model reaches `lado.db`, `list_agents`, the API) |
| A reported model that differs is the CLI's | unit | `tests/test_hooks.py` / `tests/test_state.py` |
| list_agents and the API give each agent's model | unit + integration | `tests/test_mcp_server.py`, `tests/test_server_*.py`, the integration test above |
| The page, the tooltip and lado ls show the model | vitest + UI e2e + unit | `web/src/Agents.test.tsx`, `tests/ui/test_agents_tab.py`, `tests/test_cli.py` |

Regression: `make lint`, `make test`, `make web`, `make test-js`, the changed integration
and UI files with their markers, `openspec validate --specs --strict`, CI green.
