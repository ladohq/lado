## Context

The epic branch has `Provider.server_api`, `external_whole_process`, `model_settings.agent_servers`,
`check_launch`, `check_start`, `model_servers.suiting`, `base.refusal_line`, `base.without_keys`,
`runtime.turn_failed`, `hooks.handle`, and `claude._server_settings`, the pattern of this change.

The human's decisions: question #4550 (a failed turn read from the journal on a server only; `/model`
of one model; LM Studio refused by type, the rest allowed), and #4538 (real runs by agents on OpenRouter,
`deepseek/deepseek-v4-flash`). Every fact on Codex comes from Codex CLI 0.162.0 on a fake server or
on OpenRouter: see `docs/superpowers/specs/2026-11-07-codex-model-server-design.md`. The plan with each
task's tests: `docs/superpowers/plans/2026-11-07-codex-model-server.md`.

## Goals / Non-Goals

Goals: a Codex agent on a server works with LADO's tools, a refusal reads in LADO's words, every place
that promises says what a start does. Non-goals: the proposal's Out of scope.

## Decisions

### D1. The provider in the agent's config

`launch_command` takes `spec.servers[0]`, the one server of a CLI that holds one model per process
(`agent_servers`), and writes on top of the carried `model_providers` an entry `lado-<server id>`:
`name` `LADO · <server>`, `base_url` the server's `/v1` address, `wire_api` `responses`, and `env_key`
the server's key variable when it has a key. A key-less server has no `env_key`: measured, Codex then
sends no `Authorization`, also with `OPENAI_API_KEY` set and a key in `auth.json`.

`model_provider` and `model` go to the top level and, as a carried profile's value wins, into the
chosen profile (`_choose_model` takes the provider too). The launch's environment gets the key under
`key_variable` and `base.MODEL_SERVER`. `SERVER_PROVIDER` moves to `base.py`: both CLIs name it so.
`server_model` is the model as it is, and `launched_on` reads `model_provider` from the agent's
config.toml, as a model's name says no server.

### D2. No login

`needs_login` is false with `base.MODEL_SERVER` in the environment, as on Claude Code.
`first_hook_blocker` does not call `_settle_login` then: no link to the human's `auth.json` and no key
file in an agent on a server. An agent that moves back to a built-in model gets its login at that
launch, as `_settle_login` replaces what it finds.

### D3. What stays off on a server

`web_search = "disabled"`: the tool has its own type, which a server may refuse or bill. The carried
`model_reasoning_effort` is dropped at both levels, as a server may refuse a value
(`reasoning_effort='xhigh' is not supported`, the human's check of Claude Code), and `Launch.effort` is
none.

### D4. `/model`: the agent's catalogue

`model_catalog_json` points to `<home>/models.json`, which replaces Codex's whole list (measured). It
holds one entry, made at launch from `codex debug models --bundled` (23 ms): the last entry with no
`tool_mode`, so that its format is the installed binary's, with `slug` the model, `display_name` the
saved name, `description` `On <server>`, `context_window` and `max_context_window` the known context or
null, and with everything that would add a tool or a parameter off: `apply_patch_tool_type` null,
`supports_search_tool` false, `experimental_supported_tools` empty, `multi_agent_version` null, the
reasoning levels empty, `default_reasoning_level` null, `supports_reasoning_effort_updates` false,
`support_verbosity` false, `default_verbosity` null, `service_tiers` and `additional_speed_tiers` empty,
`availability_nux` and `upgrade` null, `input_modalities` text. A list that cannot be read, or has no
such entry, leaves `model_catalog_json` out, with a launch warning that `/model` shows OpenAI's models.

The saved name and the server's name are text in JSON, written by `json.dump`. Nothing in the file is
a secret.

### D5. Context

For a known limit, `model_context_window` is `limit.context` and `model_auto_compact_token_limit` is
`limit.context - limit.output_room()`. Measured at 65536 and 50000: the next turn is preceded by a
compaction, an ordinary `POST /v1/responses`, so a server needs nothing more. Unknown: neither key, and
`context_warning` warns as on the other CLIs. Codex has no key for the output.

### D6. Who can use a server

`Provider.refuses_server(kind) -> str`, "" by default: why this CLI cannot use a server of that type.
Codex answers for `base.LM_STUDIO` (the constant moves from `model_servers.py`, which imports
providers): `its Responses API loses Codex CLI's MCP tools, so the agent could not talk to LADO`.

`model_servers.suiting(apis, kind)` puts such a CLI among those that do not suit, and each caller passes
the type: `Probe.clis`, `model_settings.clis`, `probe_info`, `_runs_on`, the check of `lado model add`.
`lines` prints `not: Codex CLI (<why>)`. `check_launch` refuses a start before any request:
`<model> is on the model server <server>; <server> does not suit Codex CLI: <why>; <who does>`, so
`list_models`' `blocked` and `spawn_worker` have the same words. `runs_on_server`, `_runs_on`'s test of
it and the branch `does not run on a model server yet` go: `_runs_on` stays for the new refusal.

A server saved before this change keeps its kind in `lado.db`: no migration.

### D7. The form's note

`ProbeInfo.cli_notes: list[str]`, `<CLI>: <why>` per CLI refused by D6, and `Found` shows each as a
`field-note warn` under its `dl`. The columns need no change: they come from `probe.clis`, which no
longer has Codex on LM Studio. See the artifact `mockup-lm-studio-note.html`.

### D8. A failed turn

`Provider.failed_turn(agent, keys) -> Event | None`, None by default: the end of a turn that no hook
reports. `runtime.check_turns(session)`, called by the loop's pass after `check_starts`, asks it for
each busy agent and passes what it gets to `hooks.handle` as a `TURN_END` under the agent's name, so a
failed turn takes the one path of a hook's: the event, the resume, the lead, idle, the queue.

`CodexProvider.failed_turn` returns None unless the agent's config names a `lado-` provider, so a
built-in agent has no read at all. It reads what is new in the newest `sessions/**/rollout-*.jsonl` of
its home, from an offset kept in `<home>/journal-offset`: a whole line at a time, so a line in writing
waits for the next pass. A new file starts at 0. An `event_msg` `task_complete` with an `error` is a
failed turn, unless a later `task_started` stands in what was read: the human's next turn has begun.

The offset lives in the home as it must survive a loop's restart and a resume, and no old error may be
told twice. The pass costs one `stat` per busy agent on a server when nothing grew.

### D9. Reading the error

| `codex_error_info` | `message` | Reads as |
|---|---|---|
| `http_connection_failed.http_status_code` | `unexpected status 404 Not Found: <text>, url: …` | status, `<text>` |
| `response_too_many_failed_attempts.http_status_code` | `exceeded retry limit, last status: 429 …` | status, no text |
| `other`, a JSON object | `{"error": {"message": …}}` | 400 (the one status Codex passes so), that message |
| `other`, any other text | `Bad Request`, an HTML page, empty | `Codex CLI's turn ended on an error`, then the text, not temporary |
| `internal_server_error`, `server_overloaded` | Codex's own words | temporary |
| a status of 500-599 in either of the first two rows | as there | its message, temporary |
| anything else | any | its message, not temporary |

A status of `base.is_refusal` goes through `base.refusal_line`, `base.context_line` first as on
OpenCode. Everything from `, url: ` on is cut before any line is made: an address may hold a password,
and a `cf-ray` is noise; a JSON object of `other`, to which Codex adds no address, is read whole first.
`details` is the text so cut. Every 5xx is temporary, as on Claude Code; 408 is not.

`other` has no status and is more than a 400, so a 400 whose body is no JSON object cannot be told
from another error: LADO does not claim a refusal there and names this in `docs/install.md`. LADO's
words stand before the colon, so that `lado stats` keeps the server's text out of the error's kind.

### D10. The key in the loop

`base.without_keys` reads the variables of the agent's environment, which the loop does not have.
`without_keys(text, keys=())` takes more values, and `check_turns` passes the kept key of the agent's
server (`model_settings.server_key`) to `failed_turn`, which applies it before anything is cut.

### D11. Repeats

LADO sets none of `request_max_retries`, `stream_max_retries`: measured, a 4xx makes 6 requests in 6 s
(12 in the TUI), a 500 30 in 25 s, and the turn ends. Limited, so nothing is added.

### D12. Tests' layers

Each requirement's layer is in the plan. The real CLI's journal, tools and refusals are the smoke's,
as only that catches a Codex update; the loop and the chat's line are the integration tests', with the
fake agent writing a journal; the rest is unit. No test reaches a real provider.
