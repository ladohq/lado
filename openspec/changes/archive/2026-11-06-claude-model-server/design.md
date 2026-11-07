## Context

The epic branch has `model_settings.start_model`, `check_launch`, `check_start`, `agent_servers`,
`StartModel`, `Provider.server_api`, `runs_on_server`, `external_whole_process`, `needs_login`,
`server_model`, `min_context`, and in `runtime` `_start_model`, `_worker_start`, `check_login`,
`_held_for_login`, `_before_window`, `check_starts`. `model_servers.probe` proves
`ANTHROPIC_MESSAGES` by `/v1/messages`.

The human's decisions: D15, D38, D44, D47 of the epic; question #3880 answered "as recommended":
one model in `/model`, the agent keeps the human's `~/.claude`, no login for it. Every fact below on
Claude Code was seen on the real 2.1.295 against a fake server, its outbound traffic stopped by a
refusing proxy: see `docs/superpowers/specs/2026-11-06-claude-model-server-design.md`. The plan
with each task's tests: `docs/superpowers/plans/2026-11-06-claude-model-server.md`.

## Goals / Non-Goals

Goals: a Claude agent on a server does its whole job there, tools, MCP and hooks included; no secret
of the human reaches the server; no key on disk. Non-goals: the proposal's Out of scope.

## Decisions

### D1. The seam

`ClaudeProvider.runs_on_server = True`, `external_whole_process` stays `True`. `agent_servers`, for a
provider of one model per process with a `start.server`, gives one `ServerEntry`: that server, with
the start model alone, with its limits, its key variable and the context warning, by the code the
family uses; `start.server` None gives `()`, so a built-in agent has nothing of the server.
`ClaudeProvider.server_model(server, model)` returns `model` as it is.

### D2. What the launch writes

`launch_command`, with `spec.servers`, adds to the agent's `settings.json`:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "<the server's root>",
    "LADO_MODEL_SERVER": "<id>",
    "ANTHROPIC_DEFAULT_MODEL": "<model>",
    "ANTHROPIC_SMALL_FAST_MODEL": "<model>",
    "ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": "", "ANTHROPIC_CUSTOM_HEADERS": "",
    "CLAUDE_CODE_OAUTH_TOKEN": "",
    "CLAUDE_CODE_USE_BEDROCK": "", "CLAUDE_CODE_USE_VERTEX": "", "CLAUDE_CODE_USE_FOUNDRY": "",
    "CLAUDE_CODE_USE_ANTHROPIC_AWS": "", "CLAUDE_CODE_USE_ANTHROPIC_GOOGLE_CLOUD": "",
    "CLAUDE_CODE_USE_MANTLE": "",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1",
    "CLAUDE_CODE_ATTRIBUTION_HEADER": "0"
  },
  "apiKeyHelper": "printenv LADO_MODEL_KEY_<ID>",
  "availableModels": ["<model>"]
}
```

The address is the server's root, not `model_servers.base_url`, which ends in `/v1`: Claude Code adds
`/v1/messages` itself. `ServerEntry` gets a field `root`. A server with no key has `apiKeyHelper:
"echo no-key"`: with no credential at all the human's login is what goes out. The file is rewritten
at each launch, so a resume on a built-in model drops all of it.

### D3. The blanks are one list

`SERVER_BLANKS` in `claude.py`, beside `LOGINS`, which it includes. Flag settings beat the process's
environment and the user's and repository's settings: seen for each of them. The empty value was
checked to end a variable's effect for `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`,
`ANTHROPIC_CUSTOM_HEADERS`, `CLAUDE_CODE_OAUTH_TOKEN` and `CLAUDE_CODE_USE_BEDROCK`.

### D4. Traffic

`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`, so telemetry does not leave for Anthropic from an agent
the human put on their own server. With it Claude Code still tried `downloads.claude.ai` and
`github.com` in the TUI; the docs say so and promise nothing more. `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS`
takes `context_management` and `safeguards` out of the body and most betas out of the header, which
a gateway may refuse. `CLAUDE_CODE_ATTRIBUTION_HEADER=0` is LM Studio's own advice for its cache.

### D5. No login

`Launch.env` gets `LADO_MODEL_SERVER=<id>`. `ClaudeProvider.needs_login(env)` is false with it, so
`_held_for_login` holds nothing; `first_hook_blocker` skips its `login_status` and records the first
run, as `claude auth status` sees no `--settings` and would say not logged in;
`keychain_login(env)` gives None, and `_keychain_warnings` gets the launch's environment.
`check_login` is called before the launch: the start's two calls and `spawn_worker`'s are
skipped for a `start.server` on a provider of one model per process. Neutral: no Claude name in
`runtime.py`. `_approve_key` is not reached: `ANTHROPIC_API_KEY` is the human's and stays out.

### D6. Context

`launch_command` sets `CLAUDE_CODE_MAX_CONTEXT_TOKENS` in the settings' `env` from
`entry.limits[model].context` when known. Unknown: Claude Code assumes 200k and says so at its start;
that is the limitation `docs/install.md` names. `ClaudeProvider.min_context = 65536`: the first request
was about 16k tokens with a clean config, and 45k with a human's `CLAUDE.md`, rules and plugins (D12).

### D7. Names Claude Code would read as its own

Saving and `check_launch` refuse a model in `provider.model_list`'s aliases, ignoring case, `default`,
or ending in `[1m]`: `--model sonnet` would go out as `claude-sonnet-5-5`. New in
`base.Provider`: `reserved_model(model) -> bool`, false by default.

### D8. The false `Open its terminal`

The cause: `check_starts` counts 30 s from the window, the plugin's `tuiWait` 30 s from its init, 3 to
5 s later, so the first fires before the second. Options: a shorter `tuiWait` (a slow machine's init
still loses), a report at the plugin's init (more code in the plugin and `hooks`, and `tui-input-ready`
had that init report nothing on purpose), or a longer wait for that family (taken). `Provider.start_silence = 30.0`,
the family's `TUI_WAIT + 15`; `runtime.START_SILENCE` goes, and the reason says the provider's number.
`heard_at_start` tells the reason by its start, not by equality. Cost: an unknown screen of OpenCode
or Kilo shows 15 s later; none is known.

### D9. A worker

Nothing new: `spawn_worker` goes through `_worker_start`, and each agent has its own config folder
and launch environment. `spawn_worker(model=…)` of an agent on a server starts from the session's
layers, so the first server's key is not passed on. An integration test holds that.

### D10. Added in the build: what the human asked after the design

Without a login the launch window greyed Claude Code out before any model was known. A CLI's default
on a server now clears `login_missing`; a window that lets a model be picked first is a separate
task. `check_start_login` reads a `--model` too, as it runs before the clone. A Claude agent's id
says no server, so `Provider.launched_on` reads it from the agent's settings: no schema change, and a
stopped agent, whose folder is gone, shows the id.

### D11. Added by the review

Claude Code hands the `env` of its settings to the processes it starts, so `lado mcp` of an agent on
a server holds the address: `Launch.cli_env` names those for `LADO_LAUNCH_VARS`, or a built-in
worker in inherit mode would inherit `ANTHROPIC_BASE_URL` and send the human's login there.
`ANTHROPIC_UNIX_SOCKET` ignores an empty value in the settings, so the launch sets it empty. The check
of a CLI's own name is in `check_launch`, so `list_models` says it too, and in `check_model`.

### D12. Added by the human's manual check (2.1.319, LM Studio and LiteLLM)

At a context of 65536 Claude Code asked for `max_tokens` 32000 on a prompt of 45K: LM Studio ended the
stream with a 500, and the agent retried over two hours. `CLAUDE_CODE_MAX_OUTPUT_TOKENS` holds
`Limit.output_room`, the rule of OpenCode and Kilo: what the server reports or 8192, at most a quarter
of the context. `min_context` goes to 65536, as such a prompt and its output need it. A `defaultMode:
auto` of the user's settings runs the classifier on the server's model, and LADO's tools were blocked
at every try: such an agent's settings allow `mcp__lado__*`. Any other tool stays with the classifier.

## Risks / Trade-offs

- **A new Claude Code adds a variable or a credential source.** `TESTED_VERSION` is bumped by hand;
  the smoke test's canary (a fake user login, key and settings) goes red when something gets out.
- **Real servers refuse a field.** `thinking` and `output_config` stay in the body. Seen only on a
  fake server: the human's manual check on LM Studio and LiteLLM decides. Ollama, LM Studio and
  LiteLLM document Claude Code with these variables; none was run here.
- **The probe may not prove `/v1/messages` on LM Studio or Ollama**, which needs a 400 or 422 with a
  JSON object to an empty body. Unknown; the manual check starts with `lado model-server probe`. A
  failure there is a question to the human, not a change of this design.
- **The key is in the agent's environment**, so a tool of the agent can read it: as for OpenCode, by D15.
- **Enter in `/model`** writes the human's `~/.claude/settings.json`: taken by the human, documented.
