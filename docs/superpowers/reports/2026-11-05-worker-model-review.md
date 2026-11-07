# LAD-208 worker-model: review report

Pull request #220 `feature/lad-208-worker-model` → `epic/lad-154-models`. Scale: full, review depth:
breadth first. Head reviewed: `f6bca0bd` (= the remote head). The supervisor sees the models of every
installed agent CLI with the new MCP tool `list_models` and starts a worker on one with
`spawn_worker(model=…)`; every spawn checks its worker's model as a start does, before anything of
the worker exists. No schema migration, no new dependency, no change to `web/`. Delta: a new
capability, `worker-model`, eight requirements; `session-model` and `agent-model` modified.

## Rounds

- **Round 1** (local, breadth first, `origin/epic/lad-154-models...ac4f32ed`): the lenses of spec,
  tests, silent failures, comments and descriptions, a general one and the architecture against
  AGENTS.md; the types lens was skipped, as there are no new types. Found F1-F8.
- **Round 2** (local, precision, `ac4f32ed..f6bca0bd`): F1-F4 resolved, no new findings.
- **External round 1** (Claude Code GitHub Action, asked 21:34:51 UTC, answered 21:35:49 UTC, worked
  27 s): no blockers or defects, three remarks refuted (F9-F11) with an answer in the pull request.
  It read every changed file of `src/`, not `tests/`, `docs/`, `openspec/` or `CHANGELOG.md`, and ran
  nothing.

External rounds used: 1 of 2. The reviewer is of the same model family, so its "no findings" weighs
less; the specs and the tests were checked locally alone.

Metrics: confirmed 5 local, 0 external; refuted 3 local, 3 external; findings in code changed by a
cleanup pass: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | after the archive the living spec `session-model` contradicted the code: "Each agent of the session's CLI starts on the session's model" and the scenario "A worker of that CLI" knew neither a worker's `model` nor the refusal's tail | fixed in `0ae98019`, `f6bca0bd`: both requirements in the delta as MODIFIED, every scenario kept |
| F2 | important | a refusal for a session table that cannot be read came without the tail of `list_models` and `model=""` the spec asks for | fixed in `0ae98019`, test `test_a_table_that_cannot_be_read_refuses_a_worker_with_its_way_out` |
| F3 | important | a scenario and step 3 of the manual check promised a refusal within the probe's timeout, while the other CLIs' lists are read first (about 16 s with Kilo, by calculation) | fixed in `0ae98019`: the requirement, the scenario, `design.md`'s risks and step 3 say the probe comes after the lists; the code did not change, D2 stands |
| F4 | minor | a saved model of a CLI not installed: the refusal named a false reason and gave advice leading to a second refusal | fixed in `0ae98019`, test `test_a_saved_model_of_a_cli_not_installed_says_so` |
| F5 | minor | for a model removed from Settings the refusal offers both `resume it with --model`, useless to an agent, and `model=""` | declined: the text is shared with the start (`check_launch`) and older than the change, and the tail holds a way that works |
| F6 | — | `check_login` stops an OpenCode worker on a local server with no cloud login | refuted: `needs_login` is false for OpenCode and Kilo (`providers/base.py`) |
| F7 | — | a worker on another model upsets the `changed model` warning at a resume | refuted: `last_start_model` reads only the supervisor's `START_MODEL` event |
| F8 | — | the source `supervisor` is lost on the way | refuted: nothing in `providers/` reads `.power`, and `report_model` does not look at the source |
| F9 | — | external: `docs/design/agents.md` should say a spawn may wait for a silent server's timeout | refuted: `docs/design/agents.md`, `docs/cli.md` and `design.md`'s risks say so |
| F10 | — | external: in `list_models` a model whose server was removed has an empty `blocked` and would start with no server | refuted: `models.server` is `NOT NULL REFERENCES model_servers(id)`, foreign keys are on, and `remove_server` refuses while a server is in use |
| F11 | — | external question: saved names ignore case, built-in ones do not; is that meant? | refuted: yes, it is the rule of `check_default`, the one reading of a name |

## Checks on `f6bca0bd`

| Check | Result |
|---|---|
| `make lint` | clean |
| `make test` | 5548 passed, 7 skipped |
| `pytest -m integration -n auto`, `test_worker_model.py`, `test_session_model_canary.py` | 10 passed |
| `openspec validate worker-model --strict` | valid |
| `openspec validate --specs --strict` | 63 passed |
| Trial archive on a copy of `openspec/` | + 8, ~ 5, - 0, → 0; then 64 of 64 |
| CI of the pull request | 23 of 23, first attempt by the developer's report |

CI flake: `ModelCards.test.tsx` on the first build visit, task LAD-210 created with the human's yes.

## Not checked

- The manual check was not run: no real supervisor on a real server.
- `make test-live` was run nowhere, while `mcp_server.py` and `runtime.py` changed.
- `make check`, `make test-integration` as a whole and the smoke did not run locally (CI ran them);
  `make test-container` neither, as there is no Docker here.
- The 16 s of a refusal on a silent server is a calculation (11.1 + 5), not a measurement.
- The MCP client's timeout at the worst case, three hanging CLIs at 15 s, the probe at 5 s and the
  login at 10 s, about 60 s; a rare case.

## Left as it is

- With Kilo installed, `list_models` and a spawn by another CLI's name, the main scenario, wait about
  11 s (the developer's measurement). Speeding it up changes D2 and is the human's decision.
- D9 of the design: with two entries of one model on one server, an agent's page may show the name of
  the other entry; the model and the server are the same.
- The history has two commits for round 1's fixes: `0ae98019` was pushed with a red trial archive,
  and `f6bca0bd` fixed it.

Found on the way, outside the task: nothing new.
