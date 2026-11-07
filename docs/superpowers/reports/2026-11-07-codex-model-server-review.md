# LAD-230 codex-model-server: review report

Pull request #246 `feature/lad-230-codex-model-server` → `epic/lad-154-models`. Scale: full, review
depth: breadth first. Head reviewed: `725557bb`. A Codex agent, supervisor or worker, runs on a model
server with the Responses API: a `model_providers` entry in its own `CODEX_HOME`, the key only in its
environment, no Codex login, `/model` of its one model. A failed turn is read from Codex's journal, for
an agent on a server only. `Provider.refuses_server(kind)` replaces `runs_on_server`: LM Studio does
not suit Codex, in the same words everywhere. One new API field (`ProbeInfo.cli_notes`), no schema
migration, no MCP tool, no CLI option, no new dependency. Delta: the new capability
`codex-model-server` (5 requirements); 9 added, 8 modified, 1 removed in all.

## Rounds

1. Local, breadth, `origin/epic/lad-154-models...b57ef0de`, with the lenses spec, tests, silent
   failures, comments, types, general and the architecture against AGENTS.md: 2 important, 4 minor,
   4 refuted.
2. Local, precision, `b57ef0de..725557bb`: F1 to F4 closed, no new finding.
3. External 1, Claude Code GitHub Action, the whole pull request at `725557bb`: no blocker, 4 minor,
   1 refuted. It read all the changed code in `src/`; not the tests, the documents, the specs or
   `web/`. It is the same model family as the kit's agents.

External rounds used: 1 of 2. Stand-ins: 0.

## The human's decisions

- **Answer #4550:** a failed turn is read from the journal on a server only, `/model` of one model,
  LM Studio refused by its type and the other servers allowed.
- **Answer #4538:** real runs by agents on OpenRouter.
- **Gate `merge_ok`, approved** on `725557bb`, with no comment: the declined findings below stand as
  declined.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | only a 500 was temporary: 502, 503, 504, 529 and `server_overloaded` ended the turn as a lasting error | fixed in `725557bb`, `test_any_5xx_codex_gives_up_on_is_temporary`, `test_a_5xx_after_codex_s_repeats_is_temporary`, `test_a_model_at_capacity_is_temporary`, smoke `test_a_503_of_a_gateway_is_temporary_for_a_codex_agent` |
| F2 | important | a 400 whose body is no JSON object went past LADO's words, and nothing named it | fixed in `725557bb`: `Codex CLI's turn ended on an error: <text>`, the limit named in the requirement, D9 and `docs/install.md`; `test_a_400_with_no_json_object_says_so_as_codex_gives_no_status` |
| F3 | minor | `, url: ` inside a 400's JSON body cut the body before it was read | fixed in `725557bb`, `test_a_body_is_read_before_the_address_is_cut` |
| F4 | minor | the change's texts differed from the work: a scenario and `proposal.md` on `Model metadata`, Scope, task 4.1 | fixed in `725557bb` |
| F5 | minor | the loop strips only the key saved now: an old key, or a removed server's, stays if the server repeats it | declined: the requirement names the saved key, and no old one is on disk |
| F6 | minor | each pass parses `config.toml` of busy Codex agents, where the design promised one `stat` | declined: a built-in agent's journal is not read and the cost is small; the external reviewer agrees |
| F11 | minor | external: an error is lost if `hooks.handle` fails after the offset moved | declined: the order is deliberate, the other way the error repeats on every pass; it needs an SQLite failure at that moment |
| F12 | minor | external: a non-numeric `journal-offset` raises `TypeError` and stops the loop's pass for the whole session | declined: LADO writes the file atomically, only a hand edit or the agent's own command breaks it |
| F14 | minor | external: the address cut loses words of a `http_connection_failed` body holding `, url: ` | declined: no leak, a rare case |
| F15 | minor | external: the server's key is visible in the agent's shell (Codex 0.162, `env` of a command), so the model can read its own server's key | declined: the task's rule (the key only in the agent's environment) holds and OpenCode and Kilo are the same; `shell_environment_policy` could close it, a decision of its own |
| F7 | — | a first turn refused: the agent is not yet `busy` | refuted: `UserPromptSubmit` comes before the model's request, the smoke with a 401 keeps it `busy` |
| F8 | — | Codex's subagents interleave journals | refuted: `launch_command` turns off `multi_agent`, `multi_agent_v2`, `agents.enabled` |
| F9 | — | `context_window: null` not checked on real Codex | refuted: a turn passed on real `_on_server` and Codex 0.162 |
| F10 | — | a quote in a server's name breaks the config | refuted: with `Шлюз "q"\` Codex read both files |
| F13 | — | external: a 408 is neither a refusal nor temporary | refuted: D9 says so, and the spec says "as the CLI gave it" |

## Checks on `725557bb`

| Check | Result |
|---|---|
| `make lint` | clean |
| `make test` | 5941 passed, 7 skipped |
| `uv run pytest -m integration` on `test_codex_model_server` | 8 passed |
| `openspec validate codex-model-server --strict` | passes |
| `openspec validate --specs --strict` | 77 passed; 78 after the archive |
| A trial archive in a copy, with the Purpose of task 6.2 | passes, 78 passed |
| CI | 23 of 23, `CLEAN` |

Real Codex 0.162 on a local fake server, before the fixes of round 1 (`Retry-After: 1`, `codex exec`,
its journal read by the real `_failed_event`; no request to a real provider):

| Server's answer | Requests | `codex_error_info` | LADO's line before the fix | Temporary before the fix |
|---|---|---|---|---|
| 500 | 30 | `internal_server_error` | Codex's words | yes |
| 502, 503, 504, 529 | 30 | `http_connection_failed` with the status | `unexpected status …` | no, F1 |
| 503, `server_is_overloaded` | 30 | `server_overloaded` | `Selected model is at capacity…` | no, F1 |
| 400 `Bad Request`, HTML, `[1,2]` | 1 | `other` | the text as it is | no, F2 |
| 400 with an empty body | 1 | `other` | `Codex CLI's turn ended on an error` | no |
| 400 `{"message":"invalid api key secret",…}` | 1 | `other` | `the model provider refused the key (400): …` | no |
| 422 `nope` | 6 | `http_connection_failed` 422 | `the model provider refused the request (422): nope` | no |
| 413 with an empty body | 6 | `http_connection_failed` 413 | `the model provider refused the request (413): Unknown error` | no |
| 408 | 6 | `http_connection_failed` 408 | `unexpected status 408 Request Timeout: timeout` | no, as meant |

## Not checked

- The external reviewer did not read the tests, the documents, the specs or `web/`; only the local
  reviewer did.
- `make web`, the UI tests, the smoke and `make test-js` were not run by the reviewer; CI ran them.
- `make test-live` was not run. The diff changes `providers/` (`base.py`, `claude.py`, `codex.py`,
  `opencode_family.py`), `runtime.py` and `loop.py`.
- A real 401, a real 429 and a compaction on a real server: the human's manual check. The fixes of F1
  and F2 ran on real Codex with a fake server, not on a real server.
- Ollama and vLLM. LM Studio's loss of the tools is the project's record, not checked again.
- A long `Retry-After` on Codex; `docs/install.md` says so.

## Notes

- The archive's commit replaces the placeholder Purpose of `codex-model-server` with the text of task
  6.2.
- The pull request's history of edits was read whole: no key or secret in it.

## Found on the way

- No defect outside the task in the code.
- For the session's setup, not this pull request: the shared folder `/tmp/claude-1000` let another
  agent overwrite the developer's draft, which put a stranger's text into the pull request's
  description for a time.
