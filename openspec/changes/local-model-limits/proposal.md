Task: LAD-211

## Why

OpenCode and Kilo agents on a model server are the epic's main scenario, and they break in ways
the human cannot see. A check of the running CLIs (OpenCode 1.18.35, Kilo 7.8.8, a fake server with
a small context) found:

- Neither CLI knows the model's context: LADO's config gives no `limit`, so OpenCode shows `0% used`,
  asks for 32000 output tokens and compacts only after the server refuses a request.
- The fixed part of an agent's request (role, skills, tools) is about 21K tokens on OpenCode and 31K
  on Kilo on a real model. A model of 8-16K cannot take one turn. Kilo ends the turn after three
  attempts; OpenCode compacts and resends without end (1107 requests in 45 s, the agent `busy`, the
  chat silent), and a `limit` does not stop it.
- A turn that ended on an error is marked "replied only in its terminal", though nothing replied.
- OpenCode with no way out waits 78 s or more at a first start: LADO's plugin makes it wait for the
  install of `@opencode-ai/plugin` (`waitForDependencies`), which npm retries.
- An agent's own state folder lost the user's TUI settings (`kv.json`).
- `ModelCards.test.tsx` fails now and then on ↻'s focus (LAD-210).

Root causes: LADO reads nothing but the list of names from a server; the plugin passes an error on
only at `session.idle`, which a loop never reaches; `check_replies` runs on every turn's end.

Options weighed for a model too small:

- A: the plugin stops the turn after three overflows in a row. Works with any server. Cost: a
  counter in the plugin.
- B (taken, the human's #3731): A, and a warning before the start when the server reports a context
  below what the CLI needs. Cost: one number per CLI to keep true as prompts grow.
- C: documents only. Free, and the human still sees a silent `busy`.

Options weighed for the context limit:

- A (taken): read it at each start from the server. Always the loaded value; costs one short
  request per server.
- B: save it with the model. No request at a start, but stale when the model is reloaded, and it
  needs a schema change.
- C: a field in Settings. The brief allows no new setting without the human's yes.

Held against the coming stages: Claude Code and Codex on a server (next in the epic) can read the
same limits; each provider decides what to do with them, so the core stays neutral.

## What Changes

- LADO reads each model's context from its server at a start: LM Studio's loaded context, Ollama's
  running model, a gateway's `max_input_tokens`. Nothing reported means no limit, as today.
- The limit goes to the agent's config as `limit: {context, output}`.
- A start on a model reported below the CLI's need warns in `lado start`, the start's warnings and
  the launch window, and starts.
- The plugin stops a turn after three context overflows in a row; the chat shows the turn's error.
- A turn that ended on an error marks no message "replied only in its terminal".
- OpenCode agents on a model server get npm's `fetch_retries=0` and `fetch_timeout=5000` while
  `@opencode-ai/plugin` is not in OpenCode's config folder.
- An agent's new state folder takes a copy of the user's `kv.json`.
- LAD-210's flaky test is fixed at its cause.
- `docs/install.md` says what to expect of small models; `docs/design/agents.md`,
  `docs/design/ui.md`, `docs/design/modules.md` and CHANGELOG follow.

## Scope

The closed list of LAD-211: items 1-9. Each is fixed, or named as a limit below.

Named as limits, in `docs/install.md`:

- Models under 32K (OpenCode) or 48K (Kilo) do not work: a lighter agent is new work (#3731).
- Kilo in a network that drops packets silently waits on `api.kilo.ai` over 140 s at a first start;
  no switch was found. A closed port costs 12 s.
- A server's 500 is retried by both CLIs for about 74 s before the turn ends on the error.
- Ollama truncates a long prompt silently when no limit is known.

## Out of Scope

- Claude Code and Codex on a server: the epic's next steps.
- Effort and the power table: a new epic.
- New settings: the brief needs the human's yes.
- A kept list for `list_models`: 1.7 s here against the reported 11 s, and it would go stale (#3731).
- A lighter agent for small models: a new task if wanted.
- The human's Esc still marks a message "replied only in its terminal": outside the closed list.
- A key over plain http to a public address, seen by hand: in the plan, not in the task's list.

## Impact

`src/lado/model_servers.py`, `model_settings.py`, `hooks.py`, `server/model_entries.py`,
`providers/base.py`, `opencode_family.py`, `opencode.py`, `kilo.py`, `opencode_plugin.js`;
`web/src/` only for LAD-210. No schema change, no MCP or CLI change, no API model change. Part of the
minor 0.45.0 (a feature).
