## Context

The epic branch has `model_servers.probe`, `context_limits`, `Limit.output_room`,
`model_settings.agent_servers`, `context_warning`, `opencode_family.turn_error`, the plugin's
`errorOf`, `ClaudeProvider.parse_event`, `_server_settings`, `SERVER_SWITCHES`, and
`runtime.turn_failed` with its resumes.

The human's decisions: question #4153 (OpenRouter as the second provider; keyless requests allowed),
question #4163 (points 1-4 as recommended; the real run). Every fact on a provider comes from the
human's report `lad-220-run` or a keyless request; every fact on a CLI from OpenCode 1.18.35, Kilo
7.8.8 and Claude Code 2.1.295 (`claude -p`) on a fake server: see
`docs/superpowers/specs/2026-11-06-external-model-provider-design.md`. The plan with each task's
tests: `docs/superpowers/plans/2026-11-06-external-model-provider.md`.

## Goals / Non-Goals

Goals: an agent on a cloud provider knows its limits, a refusal reads in LADO's words and ends the
turn, no repeat goes on without end, the key is in no text of LADO's. Non-goals: the proposal's Out of
scope.

## Decisions

### D1. Which fields give a context

`_listed_limits` asks one function per item: context from `max_input_tokens`, `context_length`,
`max_model_len`, the first that `_tokens` accepts; output from `max_output_tokens`, then
`top_provider.max_completion_tokens`. `max_input_tokens` goes first as it is what a gateway says of
the prompt alone. `top_provider.context_length` is not read: OpenRouter's `context_length` is the
same number. The merge with Ollama's and LM Studio's readings keeps its order, so a local server's
loaded context still wins. OpenRouter's list is 0.8 MB in 0.5 s, within `MAX_ANSWER` and
`LIMIT_TIMEOUT`.

### D2. The output of a large context

`Limit.output_room` takes `LARGE_OUTPUT = 32000` in place of `DEFAULT_OUTPUT` for a context of
`LARGE_CONTEXT = 131072` or more. Without this D1 would cut every cloud model to 8192 tokens, where
today it has its CLI's 32000: a regression for a reasoning model or a long file. 32000 is the CLIs'
own default. A context below 131072 keeps the rule the local work tuned.

### D3. Who is warned of an unknown context

`model_servers.is_local(root)` is taken out of `plain_http_warning`, which keeps its behaviour.
`context_warning` warns when `limit is None`, the start is on a server and that server is not
`model_servers.in_network`: `is_local`, or a name with no dot or of `NETWORK_SUFFIXES`, which no
provider that bills has. The key's rule stays by address alone: such a name may be anything, and a
key over plain http to it is warned about as before.
`CONTEXT_PEEK`'s sibling `CONTEXT_UNKNOWN_PEEK` goes to `model_entries`, which already builds the
words of the folded Advanced. A local server stays silent: an Ollama model not yet running is normal
there. A server that did not answer in `LIMIT_TIMEOUT` counts as unknown too: the warning is true.

### D4. The status reaches `providers/`

The plugin's `errorOf` adds `status` from `error.data.statusCode`. `turn_error` passes a status of
`base.REFUSALS` to `base.refusal_line(status, text)`; every other error keeps its path, the context's
words first. Claude's `parse_event` reads `last_assistant_message` by `REFUSED = API Error:
(?:Request rejected \()?(\d{3})\)?\s*·?\s*(.*)`, only when `base.MODEL_SERVER` is in `os.environ`:
real Claude Code's hook sees it, as the smoke's refusal in LADO's words shows. No `Failed to
authenticate.` prefix matters: the search is not anchored.

### D5. LADO's words, one table

`base.REFUSALS = {401: "the model provider refused the key", 402: "the model provider asks for
payment", 403: "the model provider refused access", 429: "the model provider limits requests, or the
quota is spent"}`. The line is `<words> (<status>): <server's first line>`, cut to `ERROR_LIMIT`, and
`details` the server's whole text. `state`'s error kind is what stands before the first colon, so it
holds no server text. 403 has words of its own: a provider also uses it for a quota.

### D6. Never temporary

Claude's `transient` becomes `kind in TRANSIENT and status not in base.REFUSALS`. OpenCode and Kilo
mark nothing transient already. `rate_limit` stays non-transient: no resume after a 429, the human's
choice. `isRetryable` of the plugin's error is not used: both CLIs have spent their repeats by then.

### D7. Claude Code's repeats

`SERVER_SWITCHES` gets `CLAUDE_CODE_MAX_RETRIES: "7"`. Measured delays double from 0.5 s to about 36 s,
so 7 repeats take about 72 s, what OpenCode and Kilo take on a 429. With the value 2, 3 requests went
out on 401, 429 and 500. A built-in agent gets nothing. In the TUI, measured by the smoke on 2.1.295:
8 requests of the turn on a 429, in 72 s with no `Retry-After`, 160 s at 20 s; 10 on a 401, in 149 s,
cause not looked into; beside them the session's title, a request with no tools that `claude -p` does
not send, repeats as much, so a provider counts 16 and 20. The turn ends and the count stops on both.
At `Retry-After: 600` it stops at once. OpenCode and Kilo wait what the server names instead: 100 and
101 s at 20 s, and at 600 s the agent is `busy` with a silent chat past 150 s. The repeats stay
limited, so the requirement holds and the documents say it; telling the chat of that wait would read
the CLIs' retry events, a new behaviour out of this change's scope.

### D8. The key's removal

`KEY_VARIABLE` moves to `base.py`; `model_settings` imports it. `base.without_keys(text)` replaces the
value of each `LADO_MODEL_KEY_*` of `os.environ` with `***`, the longest first, skipping an empty one.
`turn_error` and Claude's `parse_event` call it first, before any cut: a key cut in two would pass a
later replacement. The hook runs with the agent's environment; the canary test proves it per CLI.

### D9. A late POST

`Answer.status is None` for a POST means late or lost. `probe` asks those POSTs again in one `_all`
with `LATE_TIMEOUT = 15`, a late control included, at most once. `Probe.late` holds the APIs still
unanswered. `lines` prints them on the `not:` line in their own words. `Probe.late_warning()` gives
one sentence that `lado model-server add` prints and `probe_info` puts in the existing `apis_why`
when that is empty, so no API field changes and Settings says it once, in the form and on a saved
server. A probe with a late API is not kept (`model_entries._keep`), as its words say to try again.
`_on_server`'s check, `api not in found.apis`, raises `Refused(..., retry=True)` with those words when
`api in found.late`. `server.apis` of a saved server holds what was proven; a later `lado model add`
probes anew, so a late answer heals by itself.

### D10. `LADO_DOWN`

Only the constant's text changes; `ModelSources.tsx` compares with the constant.
`docs/design/ui.md` says the new line. No mock-up: no screen changes, the line stands where it stood.

### D11. Tests at the lowest layer

The fake endpoint gets a mode that answers a status with a body, and a `Retry-After: 1` so that a real
CLI's 429 takes seconds, not 70. Requirement by requirement: the plan's table.

## Questions for the human

None left: #4153 and #4163 are answered. The scale and this design wait for `design_ok`.
