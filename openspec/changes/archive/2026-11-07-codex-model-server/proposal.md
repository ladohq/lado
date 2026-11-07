Task: LAD-230

## Why

Codex is the last agent CLI that does not run on a model server. Today the promise and the refusal
disagree: the probe of OpenRouter prints `Codex CLI (Responses API)`, `lado model add --cli codex`
saves the model, and `lado start` refuses with `Codex CLI does not run on a model server yet`. Root
cause: `Provider.server_api` drives the promise, `Provider.runs_on_server` drives the refusal, and
Codex declares the first without the second.

What stood in the way, checked with real Codex 0.162 (the measured facts are in
`docs/superpowers/specs/2026-11-07-codex-model-server-design.md`):

- **Tools.** Codex sends every MCP server's tools as one tool of type `namespace`, and no setting
  changes that. A server that does not know the type leaves the agent without LADO's tools. OpenRouter
  keeps them: a real LADO session on `deepseek/deepseek-v4-flash` ran a shell command, `list_agents`
  and `send_message`. LM Studio's Responses API drops them.
- **A refused turn is silent.** Codex runs no hook and no `notify` for a turn that ends on a 4xx. The
  agent looks busy for good. Only its session journal (the rollout) has a `task_complete` with an
  `error`.
- **`/model` lies.** An agent on a server is offered OpenAI's models, which the server then refuses.

Options weighed for a refused turn (the human's question #4550):

- A (taken): the session loop reads the new part of the journal of a busy Codex agent on a server.
  Refusals read as on the other CLIs. Long-term cost: LADO depends on the journal's format, which the
  smoke test catches at each Codex update. Reverses the human's decision of 2026-10-09 that LADO reads
  no transcript, for these agents only.
- B: the same for every Codex agent. Closes the backlog entry, but changes Codex without a server,
  which this task must not.
- C: no reading, a named limitation. An agent on a wrong key stays busy and nobody hears of it.

Options weighed for `/model` (#4550):

- A (taken): the agent's own list of one model, built from the installed Codex's own catalogue, so
  that its format follows the binary. It also carries the context; the smoke reads the real `/model`, as the
  absence of the warning `Model metadata not found` proved nothing. Long-term cost: a field of the catalogue that matters changes meaning with a Codex
  update; a list that cannot be read costs a loud warning, not the start.
- B: leave OpenAI's names and say so in `docs/install.md`. Free, and a trap.

Options weighed for which servers get Codex (#4550):

- A (taken): refuse LM Studio by its type, in every place that promises, and allow the rest, with
  `docs/install.md` saying what was checked. Long-term cost: a type is a coarse rule, and a later
  LM Studio that keeps the tools stays refused until the line goes; another server that drops them is
  found only when its agent says nothing.
- B: allow only the servers checked. Closes Ollama and every gateway that does work.
- An active check is not offered: it takes a paid request to a model, and what a dropped tool looks
  like differs by server.

Held against the coming stages: with Codex every CLI runs on a server, so `runs_on_server` goes, and
the one question left, whether this CLI can use this server, is asked in one place that a later
provider answers too. Neutral core: reading a failed turn is a provider's method the loop calls
without knowing which CLI it is; only Codex has one, as the other three have hooks for it. No silent
drops: what Codex cannot do is named below and in `docs/install.md`. One source of truth: `suiting`
decides for the probe, the form, `lado model add` and a start. Only what is used: no field for a limit
Codex has no setting for.

## What Changes

- A Codex agent whose start model is on a server runs there: a `model_providers` entry in its own
  `CODEX_HOME` on top of the carried values, the key only in its environment, no OpenAI login needed,
  and nothing of the human's login reaches the server. Workers too.
- `model_context_window` and `model_auto_compact_token_limit` come from what the server reports.
- `/model` offers the agent's one model.
- Its web search tool and its carried effort stay off on a server.
- A turn such an agent ends on a 4xx but 408 reads in LADO's words and ends the turn, but for a 400
  whose body is no JSON object, for which Codex gives no status; a 5xx is temporary, as on Claude
  Code. The key and the address are in no text of LADO's.
- LM Studio does not suit Codex: the probe's `not:` line, the form's note, `lado model add`,
  `list_models`' `blocked`, a start and a spawn say the same words.
- `Provider.runs_on_server` and the refusal `does not run on a model server yet` are gone.
- `docs/install.md`: Codex on a server, what was checked, what Codex cannot do, and the line that a
  model can fail through a CLI with no error at all, so the first session on a new model is worth
  watching. `docs/cli.md`, `docs/design/agents.md`, `docs/design/ui.md`, `docs/design/modules.md`,
  `docs/testing.md`. A line in CHANGELOG.md under `## 0.45.0 (unreleased)`: a feature, a minor, which
  the heading already is.

## Scope

`providers/base.py`, `providers/codex.py`, `providers/claude.py`, `providers/opencode_family.py`,
`model_servers.py`, `model_settings.py`, `runtime.py`, `loop.py`, `server/models.py`,
`server/model_entries.py`, `web/src/ModelSources.tsx`: 11 code files, and the generated
`web/openapi.json`, `web/src/api.gen.ts`. Tests, `tests/fake_endpoint.py`; docs. One new API field
(`ProbeInfo.cli_notes`). No schema change, no new dependency, no MCP tool, no CLI option, no new
screen.

## Out of scope

- A failed turn of a Codex agent on a built-in model: Codex without a server must not change; the
  backlog entry stays for it.
- A limit of Codex's output: Codex 0.162 has no such setting and sends no `max_output_tokens`.
  `docs/install.md` names it: a model that repeats without end on a server that bills stops at the
  provider's own limit.
- A server gone in the middle of a turn: Codex waits for the network without end and goes on when it
  returns. Nothing was refused, no turn ended, so LADO has nothing to read. The agent stays busy;
  `docs/install.md` names it.
- A Codex agent's smallest context (`min_context`): no number was measured; 0 stays. A new task if a
  small context hurts.
- The server's text of a 429: Codex keeps only the status.
- The key in Codex's own journal or terminal, if a server echoes it: LADO does not write those (as
  for the other CLIs).
- A check by request of whether an unknown server keeps the tools: see above.
- Effort and the power table: a new epic. A real 429 or quota on a provider: not in this task.

## Impact

Codex on a built-in model or on the user's own `model_provider` starts as before, with no new file,
no journal read and the same launch. Claude Code, OpenCode and Kilo work as today; only the field
`runs_on_server` leaves them. A Codex model saved on LM Studio, which was refused at the start, is
refused there in other words. `lado model add --cli codex` on LM Studio, which saved, now refuses.
