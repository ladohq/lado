# LAD-180 session-start-model: review report

Pull request #219 `feature/lad-180-session-start-model` → `epic/lad-154-models`. Scale: full,
review depth: breadth, then precision. Head reviewed: `9e6ffda9`.
A session refers to a model: an agent starts on the session's model, else its CLI's default, else
as before; `lado start --model`, the launch window's Model field, every ticked external model in
each OpenCode and Kilo agent's config, one `lado-<server id>` provider per server, the check before
a start and at each resume, the agent's card with its source, doctor on the default. No schema
change. `providers/`, `runtime.py`, `mcp_server.py` and `agent_env.py` changed; `make test-live` was
not run anywhere.

## Rounds

- **Round 1**: local, breadth, `origin/epic/lad-154-models...2ed73594`, every lens by the reviewer.
- **Round 2**: local, precision, `2ed73594..307c6982`, with a browser probe.
- **Round 3**: local, precision, `307c6982..20e64593`, with a browser probe. External 1 of 2 (Claude
  Code GitHub Action), the whole pull request, 52 s.
- **Round 4**: external 2 of 2, at the lead's request: the files the first skipped, `agent_env.py`
  and the key's path, 2 min 1 s. Probe of E6.
- **Round 5**: local, precision, `20e64593..92b19b12`, a return from the human's gate. No external
  round.
- **Round 6**: local, precision, `92b19b12..9e6ffda9`, a return from the human's gate: the agents'
  own state of OpenCode and Kilo and doctor's words. No external round: the cap of 2 was used.

6 local rounds, 2 external, 0 substitute. Local: 11 confirmed, 6 refuted, 1 unverifiable. External:
5 confirmed, 2 refuted. Findings in code rewritten by the developer's cleanup: 0. The external
reviewer is of the same model family as the kit's agents, so its "no findings" weighs less.

## Findings

| ID | Source | Level | Finding | Outcome |
|---|---|---|---|---|
| F1 | local | important | `lado doctor` raises when a built-in default is set and the agents' environment cannot be read | fixed in `727116dc` |
| F2 | local | important | A server key with `"` or `\` breaks the agent's config | fixed in `727116dc` |
| F3 | local | important | The window's model choice is silently dropped when Where or the project changes | fixed in `727116dc` |
| F4 | local | minor | The line `-> CLI default` is wrong for an agent starting on the new CLI's default | fixed in `727116dc` |
| F5 | local | minor | `Default models` says `does not answer` of a server that refused | fixed in `727116dc` |
| F6 | local | minor | Code without callers: `model_check.check`, the route `/api/providers/{name}/models`, `launch.provider_models`, `ProviderModels` | fixed in `727116dc`: removed |
| F7 | local | important | By keyboard: the footer link, the return from Settings, Esc closes the whole launch window | fixed in `1816c7b9` |
| F8 | local | minor | `design.md` D5 named the removed `model_check.check`; a test named after the removed route | fixed in `1816c7b9` |
| E1 | external | minor | `_default_moved` calls `providers.get(old.provider)` unchecked | declined: needs a provider LADO no longer knows |
| E2 | external | — | `checked.append` in `start_session` is needless | refuted: `checked` goes to the session's log |
| E3 | external | minor | `asValue` before Settings is read shows an external model as a built-in name | declined: only the field's look, for a moment |
| E4 | external | minor | `by_name[default.server]` raises `KeyError` when a server goes between two reads | declined: a window of milliseconds in one doctor run |
| E5 | external | minor | doctor reads the built-in lists one by one | declined: up to 60 s at worst; the requirement bounds the requests to servers |
| E6 | external | minor | A key file edited by hand with a control character breaks the config as F2 | fixed in `df1fce0a`, `92b19b12`, by the human's decision |
| E7 | external | — | `for_git` gives `os.environ` to git inside the agent's `lado mcp` | refuted: the agent's own environment; the key is not on a command line |
| N1 | local | minor | The agent's own state also takes OpenCode's `kv.json` with TUI settings away; only `model.json` is copied | declined: the look of the agent's window, not behaviour; left to the human |
| N2 | local | minor | In inherit mode a worker spawned by a family agent loses the user's `XDG_STATE_HOME` | declined: needs inherit and an own `XDG_STATE_HOME`; `CODEX_HOME` behaves the same |
| N3 | local | minor | A `lado-…` pick through `/model` in a session without a model survives a resume, unchecked before the start | declined: so decided in D8 and the spec; a silent server shows on the agent's first turn |
| U1 | spec | — | The scenario `A pick in the agent`: a pick in a real `/model` leaves the user's file alone | unverifiable by the developer from tmux: step 7 of the manual check |
| R1 | local | — | The key reaches a worker of another CLI in shell mode | refuted: `from_shell` starts the shell with `SHELL_BASE` only |
| R2 | local | — | `--model <external>` on Claude asks the server before the refusal | refuted: `check_default` asks no server, `check_launch` refuses |
| R3 | local | — | A record with another CLI under the same id | refuted: `UPDATE models` changes the name only |
| R4 | local | — | A broken table raises at `row()` | refuted: every call checks `readable` |
| R5 | local | — | F7 by mouse | refuted: the focus stays on the field, Esc closes the list only |
| R6 | local | — | The state folder stays after a session or a worker goes another way | refuted: every path through `delete_session`, `delete_agent` removes it |

## Checks on `9e6ffda9`

| Check | Result |
|---|---|
| `make lint` | exit 0 |
| `openspec validate session-start-model --strict` | exit 0 |
| `openspec validate --specs --strict` | exit 0 |
| `make test` | exit 0, 5501 passed, 7 skipped |
| `pytest -m integration`, the five changed files of model servers and session models | exit 0, 31 passed |
| CI of the pull request | 23 of 23, first attempt |

Not run locally: `make web`, `pytest -m ui` and smoke (CI ran them), `make test-js` (the plugin did
not change), live.

## Not checked

- U1: a pick through a real `/model` with the agent's own folder, in no run; step 7 of the manual
  check. Indirectly: Kilo wrote its memory to the agent's folder and left the user's file; OpenCode
  did not show the write.
- The deltas `20e64593..9e6ffda9`, with the new `own_state` of `providers/`, had no external reading:
  the round cap was used.
- External rounds did not trace `tmux.new_session` and `interpreter.run_module`, and did not read
  the middle of `doctor.py`'s helpers, `web/src/Launch.tsx` outside the named places, `tmux.py`,
  `interpreter.py`, the tests, the documents and the specs.
- Design QA's findings F11, F13, F14, F21, F22 were left by the lead's decision; no third pass.
- OpenCode hung for 90 s with outside traffic to a closed port, cause not found; a real start
  without a network was not checked.
- Kilo's plugin writing the model in the TUI was seen in `kilo run` only.
- The key canary runs in inherit mode only; shell mode rests on reading the code and on external
  round 2.
- The ban on characters in a key and the path `<state>/<cli>/model.json` were checked on OpenCode
  1.18.35 and Kilo 7.8.8; another version may differ.
- The agent's folder grows with input history until `forget`; a later pick in the human's own CLI
  does not reach an agent already made.
- In a running agent's `/model` a renamed server keeps its old name until the next start.
- The Team tooltip with a model's name has no test of its own.
- Red first was not kept everywhere: some browser tests, the server integration and smoke were not
  seen red before the code.
