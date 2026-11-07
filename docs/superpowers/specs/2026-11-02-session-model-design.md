# One model per session: design

Task: LAD-174 (epic LAD-154). Change: `openspec/changes/session-model/` (proposal, the
delta of the new capability `session-model` and of `agent-model`, design.md D1-D12).
Mockup: run artifact `mockup-session-model.html` (approved with the design).

## What the human sees

**`lado start --model <model>`** starts a session whose agents of its provider's CLI run
on that model. A model the CLI's list lacks is refused before anything starts:
`gpt-9 is not in Codex CLI's list of models; codex debug models prints the list`. A model
the CLI cannot check (Claude Code's full names, Codex on its own model provider, a list
command that failed) starts with a warning on stderr, among the session's start warnings
in the UI and in loop.log. A resume keeps the model; `--model ''` goes back to the CLI's
default; a resume with another provider and no model drops it; each prints
`changed model: <cli> <model> -> CLI default` (or the other way).

**The launch window**, Advanced (New session and Resume): a **Model** field before Switch
off. Free text with suggestions: the chosen provider's aliases and its list. Under it one
note: empty → `empty: Codex CLI's default model; type or pick one of its models`; in the
list → `✓ in Codex CLI's list of models`; an alias → `✓ an alias of Claude Code`; no
list → the ⚠ warning; not in the list → the refusal, and Start is off. Folded with a
model, the summary reads `Advanced: model gpt-5.6-sol`; without one, `Advanced: model,
switch off agents, skills, MCP servers or flows`. Another provider empties the field.
Resume fills it with the session's model.

**The agent's page**: Model `gpt-5.6-sol · chosen for the session`. A Claude agent
started with `opus` shows `opus`, then `claude-opus-5-5` once Claude Code names it, the
source unchanged. A model changed by `/model` shows with `CLI default` at the CLI's next
event naming it. A worker of another CLI shows `CLI default, the session's model
gpt-5.6-sol is for Codex CLI`, and the supervisor's `spawn_worker` warns `w1 runs on
Claude Code's default model: the session's model gpt-5.6-sol is for Codex CLI`.

**`list_agents`**: `model_source` `session` for those agents. **`lado ls`**: their model,
as for any agent.

Without `--model` and with the field empty, nothing changes.

## Facts the design rests on

Proposal, Why: each CLI's way to take a model and its list, checked in this run on Claude
Code 2.1.295, Codex CLI 0.162.0, OpenCode 1.18.35 and Kilo 7.8.8. `codex debug models
--bundled` answered without the network; without `--bundled` it refreshed the user's
`models_cache.json`. `kilo models` gave a different list online and with the network cut
(its gateway's list, refreshed by Kilo itself). `opencode models` left its cache file
untouched.

## Options

Proposal, Options: A (taken) a power table as a JSON column; B a plain `model` column
(a second format later); C a table of rows (does not travel to the user's and project's
stores). For the check: the CLI's own aliases and local list (taken); LADO's catalogue
(refused by the task: no catalogue of LADO's own); the model APIs (refused: no network
request for a list).

Held against AGENTS.md's principles and ROADMAP's coming steps:

- **Neutral core**: the table, the rule of which agent gets the model (`session_model`),
  the check's verdicts and the words are above `providers/`; each provider only applies
  `AgentSpec.model` and answers `model_list` and `same_model`. All four CLIs take it.
- **No silent drops**: another CLI's agent, a list that cannot be read and a provider
  change are each said (warning, the page's detail, the resume's changes).
- **One source of truth**: the check is one function; the CLI, the API and the UI show its
  text. The model's list is the CLI's, never a copy in LADO.
- **Never touch the user's global agent config**: Codex's user config is read only; the
  model goes into each agent's own home, command line or config content.
- **Only what is used**: no effort key, no level choice, no session model in `start_session`.
- **Coming steps**: effort adds a key to a row; the user's and the project's tables reuse
  the format; a level per role picks another row than `normal`; model servers add a
  source and a list of their own.

## Questions for the human

Answered at question #2471, all as recommended: the mockup; the words `chosen for the
session`; a provider change drops the model; a resume keeps it, `''` clears it; OpenCode's
and Kilo's own list commands; the model shown on the agents only.

## Tests by layer

- Unit: the table's format and the migration; each provider's launch with and without a
  model (argv, config.toml, config content); `model_list` per provider from recorded
  outputs; the check's four verdicts; `report_model`'s alias and no-name rules;
  `start_session`'s keep, drop and provider change; `spawn_worker` of another CLI; the
  API's models endpoint and `Launch`/`Resume`/`SessionInfo`; `Launch.tsx` (vitest).
- Integration (fake agent): a session started with `--model` → the fake agent's
  environment, `lado.db`, `list_agents` and the API with the source `session`; a refused
  model stores nothing; a worker of another provider gets the note.
- UI e2e: the field's notes, Start off on a refusal, the folded summary, the agent's page.
- Smoke (CI, per provider): the model reaches the real CLI's argv or config.

## Version

The minor (a CLI option, the API, a schema migration), within `## 0.45.0 (unreleased)`
on the epic branch.
