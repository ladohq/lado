# LAD-220 external-model-provider: review report

Pull request #235 `feature/lad-220-external-model-provider` → `epic/lad-154-models`. Scale: full,
review depth: breadth first. Head reviewed: `f9b7e98b`. Agents on a cloud provider know their limits:
LADO reads `context_length`, `max_model_len` and `top_provider.max_completion_tokens`, and a context of
131072 or more gets an output of 32000 where none is reported. A start on a public server with no
known context warns. A provider's refusal reads in LADO's words, is never temporary and carries no
key. A Claude agent on a server repeats a request within a limit, names no effort and compacts within
its context. A late POST of a probe is asked once more and reads `did not answer in time`. `LADO_DOWN`
promises nothing. No API field, MCP tool or CLI option changes. Delta: 13 requirements added, 4
modified, in `claude-model-server`, `model-context`, `model-servers`, `model-settings-page` and the
new `provider-refusals`.

Outcome: converged, no blocker or confirmed important finding left; approved at the merge gate.

## Rounds

- **Round 1** (local, breadth, `origin/epic/lad-154-models...72c43d85`, 43 files).
- **Round 2** (local, precision, `72c43d85..a84120e0`, 24 files): F1-F7 closed.
- **Round 3** (external, 1 of 2, Claude Code GitHub Action on `a84120e0`): no blocker or important.
- **Gate #338**: the human refused after the manual check, findings 1, 2, 3.1 and 3.2. Findings 3.3,
  3.4 and the silence on a long `Retry-After` went to Later; 3.5 is closed by the Codex step.
- **Round 4** (local, precision, `a84120e0..16baf9e3`, 18 files, measured on real CLIs): F14-F17.
- **Round 5** (local, precision, `16baf9e3..f9b7e98b`, 8 files, measured on real Claude Code): F14-F17
  closed, new F18.
- **Round 6** (external, 2 of 2, requested 00:21:33 UTC, answered 00:22:33 UTC, head `f9b7e98b`, delta
  from `a84120e0`): no blocker or important.

External rounds used: 2 of 2. The last one read `base.py`, `claude.py`, `opencode_family.py` and
`state.py`: the diffs and the functions named, whole. It read no tests, documents or specs and ran no
tests. It is of the same model family and took 26 s, so its "nothing found" weighs little.

Metrics: confirmed 18 local, 5 external; refuted 7 local, 4 external; unverifiable 1 (E10); substitute
rounds 0; findings in code changed by the developer's cleanup: 0.

## Findings

| ID | Round | Source | Finding | Verdict | Level | Fate | Status |
|---|---|---|---|---|---|---|---|
| F1 | 1 | breadth: silent failures | `try again` in the live check of Settings answered for 60 s from the cache of a late probe | confirmed | important | fix | resolved in `97a75da0`, `test_a_late_check_asks_the_server_again_at_the_next_try` |
| F2 | 1 | breadth: spec, measured | On a 429 with `Retry-After` OpenCode and Kilo wait the time named: "about 70 s" was wrong | confirmed | important | fix | resolved in `a84120e0`, documents and spec |
| F3 | 1 | breadth: general | The context warning fired on local names of the network | confirmed | important | fix | resolved in `97a75da0`, `test_a_name_of_the_human_s_network_is_inside_it`, `test_an_unknown_context_on_a_local_server_does_not_warn` |
| F4 | 1 | breadth: no silent drops | Settings showed a late API as missing | confirmed | important | fix | resolved in `97a75da0`, `test_a_saved_server_s_probe_says_its_api_is_late_not_missing`, `test_a_late_api_is_said_once_in_the_probe_of_a_check_and_of_an_add` |
| F5 | 1 | breadth: comments | "at most 7 times" against 10 requests on a 401 | confirmed | minor | fix | resolved in `a84120e0` |
| F6 | 1 | breadth: comments | The docstring's "eight at most" | confirmed | minor | fix | resolved in `97a75da0` |
| F7 | 1 | breadth: tests | The scenario "The kind in the statistics" had no test | confirmed | minor | fix | resolved in `97a75da0`, `test_lado_stats_counts_a_refusal_by_lado_s_words_alone` |
| F8 | 1 | breadth: silent failures | `late` includes a reset connection and a TLS error on a POST | confirmed | minor | decline | declined: the advice to retry stays right, and the API is not named missing |
| F9 | 2 | precision: project rules | The CHANGELOG line grew to four lines; the rule is three | confirmed | minor | decline | resolved by the developer anyway in `c4fd58fc` |
| F10 | 2 | precision: comments | The descriptions of the probe cache do not name the exception for `late` | confirmed | minor | decline | declined |
| F11 | 2 | checks | A new test flaked on ceilings of 0.3 s (`tests/test_model_servers.py:535`, `assert 1 == 2`, once) | confirmed | minor | decline | declined by the timeout trap; later runs green; stays a risk |
| F12 | 2 | precision: spec | The scenario "A server that names a long wait" has no automatic test | confirmed | minor | decline | declined: it would cost minutes in every CI run; confirmed by measurement |
| F13 | 2 | precision: tests | The `apis_why` line in the Change form has no test; the words can stand twice | confirmed | minor | decline | declined: two different probes, no harm |
| F14 | 4 | precision: measured on real Claude Code | A 404 and a 413 of a Claude agent on a server had no LADO words; a unit test fixed an invented form | confirmed | important | fix | resolved in `78fd34db`, `test_a_404_on_a_server_has_its_status_and_the_cli_s_words`, `test_a_413_on_a_server_is_read_from_the_error_s_details`, smoke rows for 404 and 413; on a 404 the CLI's phrase stands in place of the server's text |
| F15 | 4 | precision: spec | The spec said the context's words come "whatever its status"; on Claude only on a 4xx but 408 | confirmed | minor | fix | resolved in `78fd34db`, `test_lado_s_words_of_a_context_too_small_come_first_whatever_the_status` |
| F16 | 4 | precision: pull request | A typo in the description, `7 skipped, 7 skipped` | confirmed | minor | fix | resolved in the description |
| F17 | 4 | precision: tests | The requirement of no `CLAUDE_CODE_EFFORT_LEVEL` on a built-in model had no test | confirmed | minor | fix | resolved in `78fd34db`, `test_a_claude_agent_on_a_built_in_model_has_nothing_of_a_server` |
| F18 | 5 | precision: measured on real Claude Code | Claude Code also changes its form by the answer's text: a 400 `prompt is too long` reads `invalid_request: 400 {json}`, a 400 `credit balance is too low` reads `billing_error`, with no status or text | confirmed | minor | decline | declined: the turn ends at once, no resume, no key; last round, a minor starts no new one |
| E1 | 3 | external | `without_keys` spoils a text with a very short key | confirmed | minor | decline | declined: a spoiled line is cheaper than a key shown |
| E2 | 3 | external | The warning's words are wrong on a public Ollama | refuted | — | drop | the context is unknown, so there is no `limit` in the config: the words hold |
| E3 | 3 | external | A probe of a half-dead server waits about 20 s | confirmed | minor | decline | declined: both ceilings are in `docs/cli.md` |
| E4 | 3 | external | A test is needed for a text outside `REFUSED` | refuted | — | drop | it exists: `test_a_claude_agent_s_other_failure_on_a_server_stays_temporary` |
| E5 | 3 | external | A link's anchor breaks on a heading with punctuation | confirmed | minor | decline | declined: only a future heading; both current ones work |
| E6 | 3 | external | The old `LADO_DOWN` text may remain somewhere | refuted | — | drop | `nothing was done` is nowhere |
| E7 | 6 | external | An `error_details` that is no string drops the hook | confirmed | minor | decline | declined: 2.1.295 sends a string, the same assumption stands a line earlier in `parse_event`, and `hooks.main` catches the exception |
| E8 | 6 | external | `ABOUT_THE_KEY` is wide: `unsupported parameter api_key` reads as a refused key | confirmed | minor | decline | declined: the server's text stands in the same line; the rule is the human's, for cloud.ru's answer |
| E9 | 6 | external | 409 and 425 end the turn at once and may be temporary | refuted | — | drop | no defect: "any 4xx but 408" is the human's decision at gate #338, and the spec says so |
| E10 | 6 | external | `CLAUDE_CODE_EFFORT_LEVEL=auto` on 2.1.319 is held only by a manual measurement | unverifiable | — | decline | CI holds 2.1.295; the developer measured 2.1.319 by hand; stays a risk |
| R1 | 1 | manual reading | `without_keys(None)` drops the hook | refuted | — | drop | `error_line` failed on the same value before, and the hook catches it |
| R2 | 1 | false greens | The integration test sets `LADO_MODEL_SERVER` itself | refuted | — | drop | the smoke proves the variable reaches the hook |
| R3 | 1 | manual reading | Parsing a link loses the old warning's anchor | refuted | — | drop | `Launch.test.tsx:1289` |
| R4 | 1 | manual reading | `asked[-len(posts):]` shifts the answers | refuted | — | drop | `posts` holds the control there |
| R5 | 4 | manual reading | Taking back the counter gives an endless loop | refuted | — | drop | a failed turn puts no message back in the queue, and the queue is finite |
| R6 | 4 | manual reading | A resume told takes the counter back itself | refuted | — | drop | `take_resume` clears `resume_at` first |
| R7 | 4 | measured | OpenCode and Kilo lose the status on a 404 as Claude Code does | refuted | — | drop | real CLIs: `refused the request (404): Model not found here` on both |

## Measurements

Real Claude Code 2.1.295 in its TUI on a local fake server, for F14 and F18. No money spent; a plugin
outside the tree swapped the status and the body.

| Server's answer | Chat's line | The CLI's message (`claude -p`) |
|---|---|---|
| 403 | `refused access (403): Region not allowed` | `Failed to authenticate. API Error: 403 …` |
| 404, before `78fd34db` | `model_not_found` | `There's an issue with the selected model (…)…` |
| 413, before `78fd34db` | `invalid_request: request_too_large: 413 {…}` | `Request too large (max 32MB)…` |
| 422 | `refused the request (422): Bad field` | `API Error: 422 Bad field` |
| 400 `prompt is too long…` | `invalid_request: 400 {…}` | `Prompt is too long · …` |
| 400 `credit balance is too low…` | `billing_error` | `Credit balance is too low` |

Real CLIs on a fake server that answers 429 to everything, for F2.

| `Retry-After` | OpenCode 1.18.35 | Kilo 7.8.8 | Claude Code 2.1.295 |
|---|---|---|---|
| none | 9 requests, about 70 s | 68 s | 8 requests, 72 s |
| 20 s | 9 requests, 100 s | 101 s | 8 requests, 160 s |
| 600 s | `busy` after 150 s, the chat silent | the same | 1 request, the turn ends at once |

On a 401 Claude Code makes 10 requests in 149 s.

## Checks at `f9b7e98b`

| Check | Result |
|---|---|
| `make lint` | clean |
| `make test` | 5844 passed, 7 skipped, first time |
| `openspec validate --specs --strict` | 70 passed |
| `openspec validate external-model-provider --strict` | valid |
| Trial archive in a copy | 71 passed |
| CI | 23 checks, `ci-ok` green, smoke on Linux and macOS |

At `16baf9e3` the integration tests of the changed files gave 25 passed; `16baf9e3..f9b7e98b` changed
none, and CI ran them on this head. `make web`, `make test-js`, `-m ui` and the regular smoke were not
run by the reviewer: their result is CI's. The red CI at `78fd34db` (`[401-claude]`, macOS, a ceiling
of 150 s) was no flake: the developer read it from the log and raised the ceiling to 300 s.
`make test-live` was not run.

## Named at the gate

- **A 404 on Claude Code.** The gate asked for the status and the server's text. The CLI gives the hook
  no such text; the line holds `the model provider refused the request (404)` and the CLI's own phrase.
  The spec and `docs/install.md` say so. The requirement is met in substance, not to the letter.
- **F18.** A provider's `prompt is too long` or `credit balance` will not read in LADO's words; the turn
  still ends at once. To be seen in its real form at the manual check.
- **Changed:** `src/lado/providers/` (`base.py`, `claude.py`, `opencode_family.py`) and `state.py`.
  Unchanged: `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py`, `tests/live/`.

## Not checked, residual risk

- Steps 3 and 5 of the manual check on a real provider: a refusal on a wrong key, and a long session
  up to a compaction on Claude Code.
- The human has Claude Code 2.1.319; the forms of 404 and 413 were measured on 2.1.295 only. No
  automatic test holds the compaction window and the effort on 2.1.319.
- On 2.1.295 a tool result of about 27 thousand tokens near the threshold still goes over the context;
  the turn ends with `refused the request (400)`. The fake's numbers are an estimate, a real token
  count differs.
- A real 429, 402 or quota, and Claude Code on OpenRouter, were not seen.
- The double `turn_error` of the human's session was not reproduced; the counter is right whatever
  its cause.
- Why Claude Code makes extra requests on a 401 and a 404 was not found out.
- F11: the cause of its one failure is not proven.

## Found on the way

Nothing.
