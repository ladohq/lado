Task: LAD-174

## Why

Every agent of a LADO session runs on its CLI's default model: a human who wants a
session on a cheaper or a stronger model has to change the CLI's own global config, which
LADO must never touch, or type `/model` into every agent's terminal. LADO already shows
each agent's model and where it came from (the `agent-model` capability); it cannot yet
choose one.

What each CLI takes and what it lists, read in this run in LADO's image (Claude Code
2.1.295, Codex CLI 0.162.0, OpenCode 1.18.35, Kilo 7.8.8):

- **Claude Code** takes `--model <alias or full name>`; its help names the aliases
  (`fable`, `opus`, `sonnet`, …). It gives no list of models. Its SessionStart names the
  model it runs (`claude-opus-5-5` for `--model opus`).
- **Codex** takes `model` in the config.toml of its `CODEX_HOME`, which LADO writes for
  each agent with the user's carried settings; a chosen `profile`'s `model` wins over the
  top level's. `codex debug models --bundled` prints the catalogue shipped in the binary
  with no network; the account's catalogue is cached in the user's
  `~/.codex/models_cache.json`. Without `--bundled` Codex fetches the catalogue over the
  network. A `model_provider` other than OpenAI's (a local server) has no list.
- **OpenCode** and **Kilo** take `model` (`provider/model`) in the config content LADO
  hands each agent (`OPENCODE_CONFIG_CONTENT`, `KILO_CONFIG_CONTENT`), which wins over
  the user's and the repository's config. `opencode models` and `kilo models` list the
  models of the providers the CLI can use; OpenCode answered from its cache, Kilo refreshes
  its gateway's list over the network itself and answers from its cache without one.

Root cause: a session has no place for a model, and no launch passes one to its CLI.

Options weighed:

- A (taken): the session keeps its choice in the format of a power table (rows light,
  normal and heavy, each a CLI and a model; here all three the same) as one JSON column
  of `sessions`; every agent of the session's CLI gets the normal row's model through its
  CLI's own way; a model is checked against the CLI's own local list before the start.
  Long-term cost: one column and one format that the user's and the project's tables
  reuse (they add levels and different rows, not a second format).
- B: a plain `model` column of `sessions`. Cheapest now, but the coming tables would need
  a second format and a second migration of the same data.
- C: a table of rows (`session, level, cli, model`). Relational, but the user's and the
  project's tables live in other stores (a settings store, the project's files), where a
  JSON document travels as it is and rows do not.

## What Changes

- `lado start --model <model>` and a **Model** field in the launch window's Advanced
  (New session and Resume) choose the session's model for its provider's CLI. Empty or
  absent: the CLI's default, as today.
- The session keeps the choice as a power table (`sessions.power`, schema 37): light,
  normal and heavy, each `{cli, model}`, all the same.
- Each agent of the session's CLI starts on the normal row's model: Claude Code with
  `--model`, Codex with `model` in its agent's config.toml (over the carried value, in the
  chosen profile too), OpenCode and Kilo with `model` in their config content. Its record
  says the model with the new source `session` ("chosen for the session").
- The model is checked before the start: an alias of the CLI or a model in the CLI's own
  local list starts; a model not in the list is refused, naming the model and the command
  that prints the list; a CLI that gives no list (Claude Code beyond its aliases, Codex on
  another model provider, a list command that fails) starts with a loud warning.
- An agent of another CLI in the same session (a worker spawned with another provider)
  runs its CLI's default: `spawn_worker` warns, and its page says the session's model is
  for the other CLI.
- A CLI that names the full name of a chosen alias keeps the source `session`; a CLI that
  names another model (changed in its terminal) makes it the CLI's, as today.
- A resume keeps the session's model unless given; `--model ''` goes back to the CLI's
  default; a resume that changes the provider without a model drops the model and says so.

## Scope

- `sessions.power` and its migration; the power table's format in `state.py`.
- `lado start --model`; `Launch.model` and `Resume.model` of the API; `SessionInfo.model`;
  `GET /api/providers/{name}/models` (the CLI's list and the check of a typed model).
- The Model field in Advanced of New session and Resume, its suggestions and its check.
- Passing the model to Claude Code, Codex, OpenCode, Kilo and the fake agent.
- The check of a model against each CLI's aliases and local list.
- The source `session`; the other CLI's note; `spawn_worker`'s warning.
- Docs: `docs/cli.md`, `docs/design/ui.md`, `docs/design/agents.md`,
  `docs/design/modules.md`; CHANGELOG.

## Out of scope

- Effort: the next work of the epic; no effort field appears in the launch window.
- Model servers (an address and a key): later work; a Codex user's own `model_provider`
  stays as carried, with no list.
- Different rows, the user's and the project's tables, a power on roles or steps: later
  work; every agent takes the normal row, the only one that differs from nothing.
- The session's model in the session's head, its list row or `lado ls`'s session line:
  the agents' pages and `lado ls`'s agent lines show it (human, question #2471).
- `start_session` of the MCP tools: it starts a session the human asked for with its
  stored settings; it takes no model (nothing uses one).
- A network request to a model API for a list: LADO runs only the CLI's own list command
  or reads its local cache; what the CLI does inside it is its own (Kilo refreshes its
  gateway's list; the human accepted it, question #2471).
- Claude Code's `--settings` `model`: `--model` is enough and wins over the user's
  settings and `ANTHROPIC_MODEL` alike (design.md D4).

## Impact

- Code: `state.py` (column, migration, power table, source `session`, `report_model`),
  `providers/base.py` (`AgentSpec.model`, `Provider.model_list`, `same_model`), each
  provider, a new `model_check.py`, `runtime.py`, `hooks.py`, `cli.py`,
  `server/models.py`, `server/app.py`, `server/launch.py`, `web/src/Launch.tsx`,
  `web/openapi.json`, `web/src/api.gen.ts`, the fake agent.
- Tests: unit per provider and of the check, the migration, integration with the fake
  agent, UI e2e of the field and the page, smoke per provider (CI).
- Docs: as in Scope.
- Version: the minor (a CLI option, the API, a schema migration), within the epic's
  `## 0.45.0 (unreleased)` on the epic branch.
- Way back: `lado update`'s rollback restores `lado.db` from its backup; an older LADO on
  schema 37 refuses it with `state.py`'s existing schema error.
