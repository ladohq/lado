## Context

The epic branch has `model_servers.probe`, `model_settings.agent_servers`, `check_start`, the
provider's `server_provider`, `own_state` and the plugin `opencode_plugin.js`. Every fact below was
checked on OpenCode 1.18.35 and Kilo 7.8.8 with a fake server of a small context, on a real LiteLLM
for its reports, and on a real LM Studio for its list. The human's decisions: #3731, the warning
before the start (1b), and the rest as recommended. The design doc:
`docs/superpowers/specs/2026-11-05-local-model-limits-design.md`; the plan with each task's tests:
`docs/superpowers/plans/2026-11-05-local-model-limits.md`.

## Goals / Non-Goals

Goals: an agent knows its model's context, a too small model is said, not silent; a first start with
no way out does not stall on OpenCode. Non-goals: the proposal's Out of Scope.

## Decisions

### D1. Read at each start, from the loaded state

`model_servers.context_limits(address, key) -> dict[model, Limit]`, `Limit(context, output | None)`.
Three reads at once by `_all`, with a ceiling `LIMIT_TIMEOUT = 2`: `/api/v0/models`, `/api/ps`,
`/v1/models`. Each is read by its shape, not by the server's saved `kind`, as a gateway hides what it
fronts. LM Studio's `max_context_length` and Ollama's `/api/show` are not read: they are what a model
can do, not what is loaded. A value that is not a positive integer counts as none (LiteLLM gives
floats: `16000.0` is 16000).

### D2. `agent_servers` carries it

`ServerEntry` gets `limits: Mapping[str, Limit]`, default empty. `agent_servers` reads every server of
the config at once, in threads, so the wait is one ceiling, not one per server. Start, resume and spawn
already go through it. `_window_warnings` reads only the chosen model's server.

### D3. `output`

`min(reported or 8192, context // 4)`. OpenCode compacts near `context - output` and sends `output` as
`max_tokens`; its default of 32000 would leave a small model nothing. Checked: 24000 with 2048 compacts
at about 21K on both CLIs. `limit` without `output` makes OpenCode refuse the config, so both always go.

### D4. The need is the provider's

`Provider.min_context: int = 0`; OpenCode 32768, Kilo 49152, from the fixed request of 21K and 31K
measured on a real model plus room to work. A comment names the measure and the versions. The core
compares; it holds no CLI's number. `0` warns never.

### D5. The warning's text

`model_settings.context_warning(start, provider, limit)`, one text for the CLI and the window:
`<name> on <server> has a context of 16,000 tokens; <CLI title> needs about 49,152 for its instructions
and tools: load the model with a larger context`. It joins the warnings as the key's does, so
`web/` changes nothing: `SessionModelCheck.warnings` and `LaunchModel.tsx` show it already.

### D6. The stop lives in the plugin

The plugin has the events and `client`; LADO's core gets nothing until `session.idle`, which the loop
never reaches. Per session a counter of `session.error` named `ContextOverflowError`. It resets on
`chat.message` and on a `message.part.updated` of type `step-finish`. At 3 it records the error with
the words of D7, marks the session stopped, so the abort's `MessageAbortedError` does not replace it,
and calls `client.session.abort`. `session.compacted` no longer clears a stopped session's error.
Kilo ends its own turn after three attempts; the same code does no harm there.

### D7. The stop's words

`{name: "ContextOverflowError", message: "<the server's message>; LADO stopped the turn after 3
attempts: the model's context is too small for the agent's request"}`. `parse_event` and `turn_failed`
stay as they are.

### D8. The reply check skips a failed turn

`hooks.py`: `if not event.error: state.check_replies(...)`. No new state, no schema or API change: the
message stays unchecked and the next clean turn decides it, which is true: the agent then has seen it.
A new state `failed` was weighed: it needs a migration of nothing and an API literal, and says what the
line of the error says already.

### D9. npm's switches

`OpenCodeFamily.server_env(spec) -> {}`, overridden in `OpenCodeProvider`: the two variables when
`on_server(spec.model)` holds, skipping a name `spec.environ` has. OpenCode only: Kilo's first start is
12 s on a closed port with no switch, and its long wait is another (`api.kilo.ai`). They reach what the
agent runs in its shell too: said in `docs/design/agents.md`. LADO's own plugin imports nothing from
`@opencode-ai/plugin`, so a failed install costs nothing.

### D10. `kv.json`

`own_state` copies it beside `model.json`, as bytes, no filter: it holds TUI settings and no provider.
Each file by its own `exists` check, so a folder from before this change takes it at the next start.

### D11. LAD-210

Cause not found yet. Known: the test took 1044 ms, past `waitFor`'s 1000, and the focus ended on
`body`, so ↻ was unmounted and either the effect came late or `refreshed` was lost. The developer
reproduces it under load and fixes the cause; no retry and no longer timeout alone. A cause not found
in reasonable time goes to the human, as the brief says, and LAD-210 stays open.

## Risks

- `client.session.abort` may not end OpenCode's loop in the TUI: untested. The developer checks it
  first, with the fake of a small context; failing that, `redesign`.
- Ollama's `/api/ps` is from memory: the server was out of reach. A wrong shape only means no limit.
  It is in the human's check.
- A model reloaded with another context mid-session keeps the old limit until a resume.
- `min_context` goes stale as kits and CLIs grow: a warning too early or too late, never a refusal.
