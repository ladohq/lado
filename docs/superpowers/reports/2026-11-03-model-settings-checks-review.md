# LAD-186 model-settings-checks: review report

Pull request #210 `fix/lad-186-model-settings-checks` → `epic/lad-154-models`. Scale:
tweak, review depth: precision by the design, taken broad (the diff removes user data and
changes the server's type rule). Head reviewed: `db794644` (= the remote head). Also closes
LAD-183, LAD-184 and LAD-185. The probe sends `anthropic-version` only with its POSTs and
one extra `GET /v1/models`, so a gateway that speaks both APIs (LiteLLM) is
OpenAI-compatible; LM Studio's embeddings models are marked and refused for agents; a
server at the address of another is saved and named; `lado model remove` takes several
names and a refused server removal hints one command for all its models. `providers/`,
`hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not change.

## Rounds

- **Round 1** (`origin/epic/lad-154-models...db794644`): a local broad pass (spec, tests,
  silent failures, comments and docs, types, general; no findings) and external 1 of 1
  (Claude Code GitHub Action); E1–E3. The external reviewer read the changed lines of
  `src/lado/` (all the risky files), not the tests, specs or docs; it is of the same model
  family, so its "no blockers" weighs less.

The five points of gate #237 (the Anthropic list with its header, the key in all eight
requests, `--replace` at its own address, one name of several not saved, eight requests
within one deadline) were confirmed by code and tests.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| E1 | minor | `Probe.models_why` keeps the plain list's error when the models come from the headered list | declined: read only when `models is None`, no visible effect |
| E2 | minor | `same_address` raises `ValueError` on a port out of range | declined: unreachable, every saved address passed `model_servers.address` |
| E3 | minor | `lado model remove`'s help says "all or none", but a model removed by another process between lookup and removal leaves the others removed | declined: the race is decision D5, documented in the docstring and `docs/cli.md` |

## Checks

- `make lint`: clean. `make test`: 5152 passed, 7 skipped.
- `uv run pytest -m integration -n auto tests/integration/test_model_server_probe.py
  tests/integration/test_model_settings_process.py`: 11 passed.
- `openspec validate model-settings-checks --strict` valid; `openspec validate --specs
  --strict` 60/0; a trial archive in a copy of `openspec/`: 60/0.
- CI: 23/23, `ci-ok` green.

## Residual risk

- Not checked on a real LM Studio or LiteLLM 1.105.1: LiteLLM's answer by the header is
  reproduced by the fake server only; the human's manual check in the PR's description.
- A server saved with the wrong type before this change keeps it until `--replace` (D7).
