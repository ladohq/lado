Task: LAD-217

## Why

A model on a server can be saved for Claude Code, but no Claude agent runs on it: `check_launch`
refuses it, as `ClaudeProvider.runs_on_server` is false. So `lado model add --cli claude --server …`
and a server's `CLIs` promise what the start then refuses, and a session of Claude Code cannot use
the human's own server at all.

Root cause: the provider has no way to the server. Claude Code has one endpoint per process, set
by `ANTHROPIC_BASE_URL`. Setting that variable alone is not safe, as Claude Code 2.1.295 showed
against a fake server:

- with no key given, the human's Claude login goes to the server as `Authorization: Bearer`;
- the human's `ANTHROPIC_API_KEY` goes to the server beside the server's own token;
- `env` and `apiKeyHelper` of `~/.claude/settings.json` beat the process's environment, so a base
  URL there takes the agent and the server's key to another host;
- `/model` offers Opus, Fable, Sonnet and Haiku, each a model the server does not have.

Options weighed for how the agent gets its server:

- A (taken): the agent's own `--settings` file holds the address, blanks the human's credentials
  and names the key's variable: `apiKeyHelper: printenv LADO_MODEL_KEY_<ID>`. Flag settings beat
  the user's and the repository's, the file holds no secret, and the key goes out in both
  `x-api-key` and `Authorization`, which covers LM Studio's and LiteLLM's ways. Long-term cost:
  LADO keeps a list of the variables that would otherwise win (`claude.py`), which a new Claude
  Code may lengthen; the canary test catches that at the version bump.
- B: `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN` in the environment. Simplest, but the two
  leaks above stay, and a key in `settings.json`'s `env` would be a key on disk.
- C: a private `CLAUDE_CONFIG_DIR` per agent on a server. Keeps the human's `~/.claude` out both
  ways, but the agent loses the human's `CLAUDE.md`, plugins, skills and hooks. The human chose
  against it.

Options weighed for `/model`:

- A (taken): only the chosen model, by `availableModels` and `ANTHROPIC_DEFAULT_MODEL`. Two rows,
  Default and the model; a subagent's `model: haiku` falls back to it. Another model of the server
  is another agent, which is how D44 of the epic has it for a CLI of one model per process.
- B: no limit. Any built-in row breaks the agent at its next turn.
- C: other ticked models in the alias slots. At most four, under labels like `Custom Sonnet model`.

Held against the coming stages: Codex joins by the same seam (`agent_servers` for a CLI of one model
per process, `needs_login`, `runs_on_server`); the local-models work is untouched. Neutral core:
nothing above `providers/` names a Claude variable, and OpenCode, Kilo and Claude Code all run on
servers after this. No silent drops: every refusal stays, and what Claude Code cannot do (`/model`
of several models) is said in `docs/install.md`.

## What Changes

- A Claude agent whose start model is on a server runs on that server, the supervisor and workers
  alike, in sessions and by `spawn_worker(model=…)`.
- The key reaches the agent only in its environment; nothing of the human's Claude credentials
  reaches the server; an agent on a built-in model is as before.
- Such an agent needs no Claude login: no refusal, no wait, no keychain warning, and LADO records
  Claude Code's first run for it.
- A server's known context goes to the agent as `CLAUDE_CODE_MAX_CONTEXT_TOKENS`, with its output
  limited as for OpenCode and Kilo; a context below 65536 is warned about.
- A server's model whose name Claude Code reads as its own alias is refused when saved and at a
  start, so `lado model add --cli claude --server …` promises only what starts.
- Refusals that named Claude Code now name Codex, the one CLI left.
- The session loop no longer shows a false `Open its terminal` before a silent TUI's report:
  OpenCode and Kilo wait 45 s, past the plugin's own 30 s.
- `docs/design/agents.md` loses the wrong line about a real turn.

## Scope

- `providers/base.py`, `providers/claude.py`, `providers/opencode_family.py`, `model_settings.py`,
  `runtime.py`; tests; `tests/fake_endpoint.py`'s Anthropic streaming; docs. No schema change, no
  `web/` change, no new dependency, no MCP tool or CLI option. The line goes under 0.45.0: a
  feature, so a minor by the rule, which the epic's heading already is.

## Out of scope

- Codex on a server: the next step. Its refusal stays, and `CLIs` of a probe still lists it by API.
- Effort and the power table: a new epic.
- LAD-209, LAD-213: separate tasks.
- Several of a server's models in one Claude agent's `/model`: decided against, see above.
- A private settings folder per agent: decided against by the human, so Enter in `/model` of such an
  agent still writes `model` into `~/.claude/settings.json`; `docs/install.md` says so and names `s`.
- Claude Code's gateway model discovery: it keeps only ids holding `claude` or `anthropic`, so it
  adds nothing for a local model.
- A real server in CI: the human's manual check on LM Studio and LiteLLM covers it.

## Impact

Claude Code on a built-in model, or with no model chosen, starts with the same argv, settings and
environment as today. `lado start`, the launch window and `spawn_worker` accept a Claude model on a
server. The refusals in `tests/` that use Claude Code as the CLI of no server move to Codex.
