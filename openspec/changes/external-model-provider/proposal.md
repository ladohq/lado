Task: LAD-220

## Why

Local models are too slow for development, so agents go to a cloud provider by its address and key.
The way there mostly exists: on the human's key, `lado model-server add` and a session of OpenCode
and Kilo on cloud.ru and on OpenRouter ran a shell tool and LADO's MCP with no change, and Claude Code
ran on cloud.ru before. What is missing is what a provider that bills needs:

- **No context reaches the agent.** The agent's config had no `limit` on either provider, though both
  list `context_length`. Root cause: `model_servers._listed_limits` reads only `max_input_tokens`.
  With no limit Claude Code assumes 200K and asks for 32K of answer, and OpenCode and Kilo compact
  only when a request is refused. The task took this for a provider that reports nothing; it is a
  gap of LADO's.
- **A refusal reads badly or wrongly.** The chat gets `APIError: Incorrect API key provided`, and for
  Claude Code the bare `authentication_failed`. A 402 reaches Claude Code's hook as `unknown`, which
  LADO takes for temporary: three resumes, ten minutes, before anyone hears of it. Root cause: the
  plugin drops `statusCode`, and the Claude provider reads only `error` and `error_details`, the
  second of which 2.1.295 does not send.
- **Claude Code repeats longest.** 11 requests in 3 minutes on a 401 and a 429, where OpenCode and
  Kilo stop after about 70 s with no `Retry-After` and at once on a 401.
- **A late answer reads as a missing API.** `Answer.refuses_as_an_api` is false for no answer, so a
  POST over 5 s (a slow first TLS connection, LM Studio just after a load) gives `no Anthropic
  Messages API` and `lado model add` refuses.
- **`LADO_DOWN` promises too much.** It says `nothing was done`, while `Unreached` means the request
  may have arrived.

Options weighed for the context:

- A (taken): read the fields the providers list: `context_length`, `max_model_len`,
  `top_provider.max_completion_tokens`. One function, no schema, no screen, and vLLM comes with it.
  Long-term cost: a provider with other field names needs a line. A public server that lists none
  gets a warning.
- B: an optional limit on each saved model. Works for any provider, and could also hold a 1M model
  back. Costs a migration, a CLI option and a field in Settings → Models for a case neither real
  provider has. The human chose against it for now.
- C: name the limitation in the docs only. Leaves the output uncapped on the very providers that list
  the numbers.

Options weighed for the words of a refusal:

- A (taken): the status goes from each CLI to `providers/`, and one table in `base.py` turns it into
  LADO's words. Long-term cost: a Claude Code that changes its `API Error: <status>` text falls back
  to its kind, which the smoke test catches.
- B: match the server's own text. Every provider words it differently.
- C: leave the CLI's words. The closed list asks for LADO's.

Held against the coming stages: Codex on a server joins by the same table (it has no hook for a
failed turn yet, see Out of scope); a limit per model stays possible on top of A. Neutral core: the
table and the key's removal are in `providers/base.py`, each CLI gives only its status, and all three
CLIs are covered. No silent drops: a public server with no context is warned about, and what LADO
does not show of cost is said. One source of truth: `Limit` stays the one rule of the output.

## What Changes

- LADO reads a model's context and output from `context_length`, `max_model_len` and
  `top_provider.max_completion_tokens`, so OpenCode, Kilo and Claude Code know the limits on cloud.ru
  and OpenRouter and compact in time.
- With a context of 131072 or more and no output reported, the output is 32000 instead of 8192: a
  cloud model's long answer or reasoning is not cut. Below that nothing changes.
- A start on a model of a public server with no known context warns: compaction comes late and the
  output has no limit. Local and private servers, by address or by a name of a local network, stay
  silent, as today.
- A turn refused with 401, 402, 403 or 429 reads in LADO's words with the status and the server's
  text; the whole text is the message's body. Such a turn is never a temporary error, so LADO resumes
  nothing; the lead or the human decides.
- A Claude agent on a server has `CLAUDE_CODE_MAX_RETRIES` 7: on a 429 it repeats 7 times, about 70 s
  with no `Retry-After`; on a 401 9 times, about 150 s. A provider's `Retry-After` lengthens the
  repeats of OpenCode and Kilo, and `docs/install.md` says so.
- Any other 4xx but 408 is a refusal too, with its status and text; a 400 about the key reads as a
  refused key, as cloud.ru answers. A context too small keeps its own words first.
- A Claude agent on a server asks for at most 16384 tokens of output and names no effort.
- A resume is counted when told, not when planned.
- The value of a server's key is taken out of an error's line and body.
- A probe asks a late POST once more with a longer ceiling, and says `did not answer in time` instead
  of a missing API; `lado model add` and a start refuse in those words.
- `LADO_DOWN` says the request may or may not have reached LADO.
- `docs/install.md` gets a section on a cloud provider: address, what context does, cost, and what to
  do on Claude Code with many plugins.

## Scope

- `model_servers.py`, `model_settings.py`, `providers/base.py`, `providers/claude.py`,
  `providers/opencode_family.py`, `providers/opencode_plugin.js`, `server/model_entries.py`,
  `web/src/api.ts`, `web/src/LaunchModel.tsx` (a warning's link goes to the section it names),
  `web/src/ModelSources.tsx` (the form says a late API): 10 code files. Tests; `tests/fake_endpoint.py`, `tests/fake_model_server.py`; docs.
  No schema change, no new dependency, no MCP tool or CLI option, no API field, no new screen. The
  line goes under 0.45.0: a feature, so a minor by the rule, which the epic's heading already is.

## Out of scope

- A limit given by hand on a saved model: decided against by the human; a new task if a 1M model's
  late compaction costs too much. `docs/install.md` names it.
- A session's tokens or money in LADO: the human chose the honest line. A new task: OpenCode and Kilo
  have the tokens in a step's end, Claude Code only in its session file.
- A resume after a 429: a short limit and a spent quota cannot be told apart, so the turn ends and the
  lead or the human decides. A night's run stops on it and waits.
- Codex: the next step. It runs no hook for a turn that ends on an API error.
- Effort and the power table: a new epic. A launch without a Claude login, picked first in the window:
  later. LAD-209, LAD-213: separate tasks.
- Reading `function_calling` of a provider's list to warn of a model with no tools: not in the closed
  list; goes to the backlog.
- An address whose path does not end in `/v1`: neither provider needs it.
- The key in a CLI's own terminal or session file, if a server echoes it: LADO does not write those.

## Impact

Local servers and agents with no external model work as today: the same limits for a context below
131072, no new warning, the same launch of a built-in Claude agent and the same words for its errors.
An OpenCode or Kilo agent on the CLI's own provider gets the new words, as the status is all they
need. `tests/` that fix `APIError: …` lines move to the new words.
