# LAD-211 local-model-limits: review report

Pull request #223 `feature/lad-211-local-model-limits` → `epic/lad-154-models`. Scale: full, review
depth: breadth first. Head reviewed: `dad0368e` (= the remote head). OpenCode and Kilo agents on a
model server learn the model's context from the server, a start on too small a context warns, a turn
stuck on overflows stops and says why, a turn that failed decides no reply, OpenCode's first start
with no way out does not wait for npm, an agent's new state folder keeps the user's `kv.json`, and
LAD-210's flake is fixed. No schema migration, no MCP, CLI or API model change. Delta: new
capabilities `model-context` and `reply-check`; `session-model` gets two requirements.

## Rounds

- **Round 1** (local, breadth first, `9ae96407...c11d79cd`): every lens and the architecture against
  AGENTS.md.
- **Round 2** (local, precision, `c11d79cd..dad0368e`): no new blockers or important findings.
- **External round 1** (Claude Code GitHub Action, `9ae96407..dad0368e`): no blockers. It read
  `hooks.py`, `runtime.py` (the hunk of `turn_failed` only) and `providers/*`.
- **External round 2** (the same, the same head, only for the risky files not read): no blockers. It
  read `model_servers.py`, `server/models.py` and the hunks of `model_settings.py` and
  `model_entries.py`.

External rounds used: 2 of 2. The reviewer is of the same model family, so its "no findings" weighs
less. It did not read `tests/`, `web/`, `docs/` or `openspec/` beyond two spec deltas, and ran nothing.

Metrics: confirmed 9 local, 5 new external (F4 named again by the external reviewer); refuted 4 local,
1 external; unverifiable 1; findings in code changed by a cleanup pass: 0 (the cleanup changed
nothing).

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | LADO's words about too small a context were cut off and never reached the human | fixed in `2698dfe4`, `69ddbcaf`, test `test_a_stopped_turn_says_why_past_the_cut_of_a_long_server_message` |
| F2 | minor | task 7.3 was unchecked while the report said all were checked | fixed in `2698dfe4` |
| F3 | minor | `proposal.md` did not reflect the narrowing of D9 | fixed in `2698dfe4` |
| F4 | minor | a failed `abort` leaves the session `stopped` and the loop goes on silently (also external round 1) | declined: the call goes to the CLI's own server, no refusal was seen in any run, and a fix needs a new test |
| F5 | minor | an overflow loop in a subagent is not stopped | declined: test `…a subagent's not at all`; that the main turn fails first is reasoning, not a measure |
| F6 | minor | the branch `where` of `context_warning` is dead | declined: both calls pass a model with a server; no harm |
| F7 | — | a second `idle` closes the next turn when a queued message follows the error | refuted: real OpenCode, turn stopped, `busy` to the end, two turns with an error; one run, not repeated on a 500 |
| F8 | — | a real LiteLLM gives no `max_input_tokens` in `/v1/models` | refuted: litellm 1.108.1, `proxy/utils.py:9905`; code read, not run |
| F9 | — | on Kilo `stopped` sticks and an old error goes to the next turn | refuted: real Kilo, two turns in a row, each with its own error |
| F10 | — | a reply from a failed turn counts as missed | refuted: `state.py:3086-3088` compares `sent_at` |
| F11 | minor | the pull request's description says "Three things differ" over four items; step 3 of the manual check says `/api/ps` is from memory, though `design.md` now cites the API's documents | declined: no effect on substance, left to the human |
| F12 | minor | `Event.details` promises a cut error's whole text, but a short multi-line error loses its later lines and `details` is empty | declined: `opencode_family.py:392-395`, `base.error_line`; older than the change |
| F13 | minor | a server's error text now goes to `body` with no length limit, where it was 160 characters | declined: `runtime.post` does not check `MAX_MESSAGE`; the size is bounded by what the CLI gives; not measured |
| F14 | minor | external: with `room <= 0` the slice `error[: room - 1]` counts from the end | declined: `turn_failed`; needs a name over 150 characters, no crash, `_cut` cuts the line anyway |
| F15 | minor | external: the dependence of `ended` on `chat.message` is not said in a comment | declined: neither reviewer found a turn with no `chat.message` |
| F16 | minor | external: the spec says "one short read per server", the code makes three GETs at once | declined: `model_servers.py:301`; the docstring and D1 say three; a matter of wording |
| F17 | minor | external: `_no_answer` may name 5 s at a ceiling of 2 s | declined: `context_limits` drops `why`, the human does not see this text |
| F18 | minor | external: a silent server adds up to 2 s to the window's check | declined: `model_entries.py:186`; bounded by the ceiling, the check runs in the background |
| F19 | — | external: an Ollama model that is not running has no limit and no warning | refuted: the spec's rule, and `docs/install.md` says so |

Outside the table: the found-on-the-way entry P3 (`; it is idle` was cut off) was fixed in `69ddbcaf`,
test `test_a_long_error_keeps_the_line_s_end_and_goes_whole_in_the_body`. The section "Found on the
way" is empty.

The false "replied only in its terminal" mark on a server's 500 was found by design QA, not by round
1, which did not run that scenario; it was fixed in `69ddbcaf`. The reviewer did not run that fix on
the real CLIs: it rests on the plugin's tests and the developer's run.

## Checks on `dad0368e`

| Check | Result |
|---|---|
| `make lint` | clean |
| `make test` | 5609 passed, 7 skipped |
| `make test-js` | 28 passed |
| `pytest -m integration`, limits and canary | 6 passed |
| `openspec validate local-model-limits --strict` | valid |
| `openspec validate --specs --strict` | 64 passed, 0 failed |
| CI of #223 | 23 of 23 |

## Not checked, residual risk

- U1: a message right after the start did not reach Kilo (developer 2 of 4, reviewer 3 of 3 arrived).
  Cause not found; a link to this change is not ruled out.
- AC-2 rests on the design's measure alone.
- Ollama's `/api/ps`: confirmed by its documents, not seen on a server.
- Real LM Studio, Ollama, LiteLLM and weak models: the human's manual check, in the pull request.
- The second pass of design QA is with the supervisor; its result is not in the ledger.
- `make web`, `pytest -m ui` and the smoke were not run locally, CI ran them. `make test-live` was run
  nowhere, though `providers/`, `hooks.py` and `runtime.py` changed.
- The developer reported edits by scripts in the first build visit, against the project's settings. The
  diff shows no trace of it.
