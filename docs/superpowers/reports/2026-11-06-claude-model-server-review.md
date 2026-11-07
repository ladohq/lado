# LAD-217 claude-model-server: review report

Pull request #226 `feature/lad-217-claude-on-model-server` → `epic/lad-154-models`. Scale: full, review
depth: breadth first. Head reviewed: `fc453d8a` (= the remote head), base `995ab826`. A Claude agent
whose model is on a model server runs there with its tools, MCP servers and hooks, the server's key
only in its environment and nothing of the human's Claude credentials on that server. Its context and
output are limited when the context is known, LADO's tools are allowed in auto mode, and a name Claude
Code reads as its own is refused. No schema migration, no `web/` change, no new dependency. Delta: new
capability `claude-model-server`; `agent-start-screens`, `model-context`, `model-servers`,
`provider-logins`, `session-first-message`, `session-model` and `worker-model` change.

## Rounds

- **Round 1** (local, breadth first, `995ab826...392f4854`): with probes on real Claude Code 2.1.295, a
  fake server and a closed proxy.
- **Round 2** (local, precision, `392f4854..ac18e916`): no new findings.
- **External round 1** (Claude Code GitHub Action, the whole source diff, 8 files of `src/`): it did not
  read tests, documents or openspec, and ran nothing.
- **Gate #313:** the human rejected the merge after the manual check on LM Studio and LiteLLM (H1, H2).
- **Round 3** (local, precision, `ac18e916..fc453d8a`): no new findings.
- **External round 2** (the same, the delta): it read the 3 files of `src/`, all the risky ones, and
  found no defect.

External rounds used: 2 of 2. The reviewer is of the same model family, so its "no findings" weighs
less.

Metrics: rounds 3 local, 2 external, 0 substitute. Local findings: confirmed 6, refuted 7. External:
confirmed 3, refuted 3. Findings of the human at the gate: 3, of them 2 fixed. Findings in code changed
by a cleanup pass: 0.

## Findings

H1–H3 are the findings of the human's manual check at gate #313 (F1–F3 in the human's report), renamed
so as not to mix with F1–F3 here.

| ID | Level | Finding | Outcome |
|---|---|---|---|
| H1 | blocker | Claude Code asks for `max_tokens` 32000 with a prompt of 45K on a context of 64K: LM Studio ends the stream and the agent repeats the request for hours | fixed in `fc453d8a`, smoke `test_a_turn_of_a_large_prompt_ends_on_a_context_that_fits_it`, test `test_a_claude_agent_s_output_leaves_room_in_a_known_context` |
| H2 | blocker | in auto mode the classifier blocks LADO's tools on the server's model | fixed in `fc453d8a`, smoke `test_auto_mode_of_the_human_leaves_a_claude_agent_on_a_server_lado_s_tools`, test `test_a_claude_agent_on_a_server_may_use_lado_s_tools` |
| H3 | minor | a choice in `/model` is written to `~/.claude/settings.json` | declined: the human's decision in the design, described in `docs/install.md` |
| F1 | blocker | with `LADO_AGENT_ENV=inherit` a Claude worker on a built-in model inherits the supervisor's `ANTHROPIC_BASE_URL`, and the human's login may go to that server | fixed in `9140fcf3`, `tests/integration/test_claude_model_server.py`, tests `test_what_claude_code_hands_its_children_is_named_as_the_launch_s`, `test_a_launch_names_what_its_cli_hands_on` |
| F2 | important | `SERVER_BLANKS` leaves out `CLAUDE_CODE_USE_ANTHROPIC_AWS`, `..._GOOGLE_CLOUD`, `CLAUDE_CODE_USE_MANTLE` and `ANTHROPIC_UNIX_SOCKET`: the agent never reaches the server | fixed in `9140fcf3`, smoke `test_another_way_out_in_the_environment_...` |
| F3 | important | `reserved_model` lets through `Sonnet`, `OPUS`, `Haiku`, `default`, `qwen[1M]` | fixed in `9140fcf3`, tests `test_claude_code_reserves_its_own_names`, `test_a_name_claude_code_reads_as_its_own_is_not_saved_for_it` |
| F4 | minor | `list_models` gives `blocked: null` for a saved model with a name of Claude Code | fixed in `9140fcf3`, test `test_a_saved_name_of_claude_code_s_own_says_why_it_cannot_start` |
| F5 | minor | the manual check of the pull request passes no key, and its step 6 looks for `<key>` | fixed: `--key` in steps 1 and 2 |
| F6 | minor | the scenario `A subagent asking for another model` has no automatic test | declined: it needs a new scenario of the fake server; a probe showed the server's model in all requests, though without `model: haiku` |
| E3 | minor | external: the docstring of `launched_on` relies on a stop removing the config folder | declined: the docstring is true, the rule is written at `configs_root` (`providers/base.py`) |
| E4 | minor | external: `LADO_MODEL_SERVER` in the login shell lifts the login check on a built-in model | declined: `LADO_` is LADO's namespace, and the only result is Claude Code's login screen |
| E6 | minor | external: `config["permissions"]["allow"] = [...]` assigns the list instead of extending it | declined: nothing else writes `allow` today (`claude.py:283`), tests hold the list |
| E1 | — | external: `check_start_login` creates `lado.db` earlier than before | refuted: `check_name` (`cli.py:178`) opens the database before it |
| E2 | — | external: `_new_start` catches only `Refused` | refuted: `start_session` reads the same table right after, with the same loud failure |
| E7 | — | external: a model below `min_context` is now refused | refuted: `context_warning` only warns (`model_settings.py:1128`), and spec `model-context` starts the agent |
| R1 | — | `CLAUDE_CODE_SUBAGENT_MODEL` takes a subagent to another model | refuted: probe, with `claude-haiku-9` all 4 requests named `probe-qwen` |
| R2 | — | `CLAUDE_CODE_MAX_CONTEXT_TOKENS` works only with `DISABLE_COMPACT` | refuted: probe, with this variable the warning about 200k goes |
| R3 | — | `CLAUDE_CODE_GATEWAY_TOKEN`, `CLAUDE_CODE_USE_GATEWAY`, `ANTHROPIC_IDENTITY_TOKEN` go to the server | refuted: probe, no canary on the server |
| R4 | — | some restart of an agent loses `spec.servers` | refuted: `_spec` is called only from `start_session` and `spawn_worker`, both pass `servers` |
| R5 | — | a name with capitals is spoiled in general | refuted: probe, `Qwen/Qwen3-8B` reached the server unchanged |
| R6 | — | `inherit` is read as an alias too | refuted: probe, `inherit` reached the server as it is; `Best` and `fable` are refused by `reserved_model` |
| R7 | — | with an output limit `thinking` does not fit in `max_tokens` | refuted: probe, `max_tokens` 8192, `thinking` of type `adaptive`, no budget |

The section "Found on the way" is empty.

A flake of round 1: `test_the_loop_types_a_swallowed_message_again` failed once with `-n auto` under
the load of the reviewer's probes and passed alone with `-n0`. It did not come back.

## Checks on `fc453d8a`

| Check | Result |
|---|---|
| `make lint` | clean |
| `make test` | 5716 passed, 7 skipped |
| `pytest -m integration` on `test_claude_model_server`, `test_session_model_canary`, `test_session_loop`, `test_model_server_probe`, `test_provider_logins` | 42 passed |
| `openspec validate --specs --strict` | 67 passed (68 after the archive) |
| `openspec validate claude-model-server --strict` | valid |
| CI of #226 | 23 of 23, the smoke included |

## Not checked, residual risk

- Both fixes of the gate on a real server and on Claude Code 2.1.319: the review ran 2.1.295, the
  findings were made on 2.1.319 with LM Studio and LiteLLM. Only the human's manual check, task 5.3 of
  the change, can confirm them.
- A prompt over about 45K on a context of 64K, and compaction, on a real server.
- The classifier's requests with `max_tokens` 2112 and 10240 from the human's report may stay outside
  the limit; for LADO's tools the classifier is no longer asked.
- A context below `min_context`: a probe with context 8000 and output 2000 made no request to the
  server, cause not found. Such a start comes with a warning anyway.
- The real login going down the chain of F1: the fix is confirmed by the worker's environment.
- `model: haiku` of a subagent (F6).
- `make test-live` was run nowhere, though `providers/` and `runtime.py` changed. `make check` and
  `make test-integration` as a whole were not run locally; the smoke ran locally only with the
  developer and passed in CI.

## Limits known

- With an unknown context the output is not limited, and the hours of repeats of H1 are possible
  (`docs/install.md`).
- Tools not of LADO, a kit's among them, stay with the auto mode classifier and are blocked on a weak
  model (`docs/install.md`).
- With `inherit` a built-in worker of a supervisor on a server does not get the human's
  `ANTHROPIC_API_KEY` and, with no other login, refuses loudly (`docs/design/agents.md`).
