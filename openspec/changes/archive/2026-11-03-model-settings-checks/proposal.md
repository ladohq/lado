Task: LAD-186

Also closes LAD-183, LAD-184 and LAD-185: four findings of the human's manual check of
`lado model-server probe|add|list|remove` and `lado model add|list|remove` on LM Studio and
LiteLLM 1.105.1, fixed together before Settings → Models shows the same types, checks and
refusals.

## Why

- **A gateway that speaks both APIs is named Anthropic-compatible (LAD-186).** LiteLLM
  shows `type: Anthropic-compatible` in `probe`, `add`, `lado model-server list` and
  doctor's `Model servers` line. Root cause: the probe sends `anthropic-version` in every
  request (`model_servers.probe`, one set of headers), the `GET /v1/models` too; LiteLLM,
  seeing it, lists its models in Anthropic's shape (items `"type": "model"`), and the type
  rule reads that shape as Anthropic. Without the header the same address lists them in
  OpenAI's shape. The CLIs are right (they follow from the APIs proven); only the type is
  wrong.
- **Two names on one address pass unnoticed (LAD-183).** `lms` and `macpro` were both saved
  at `http://10.73.10.235:1234` without a word; doctor asks the server twice. Two names on
  one address are a legitimate setup (one gateway, two keys), so it is neither refused nor
  warned about: the human only sees it.
- **An embeddings model is saved as an agent's model (LAD-184).** `lado model add … --model
  text-embedding-nomic-embed-text-v1.5 --server lms` is saved because the name is in the
  server's list; the agent on it fails at its first turn. LM Studio says which models are
  embeddings (`type` in `GET /api/v0/models`, a request the probe already sends); LADO reads
  it nowhere.
- **The hint of a refused server removal names one model (LAD-185).** `model server "lms"
  is used by the models a, b, c, d, e; remove them first: lado model remove "a"` reads as if
  removing `a` were enough.

Options weighed for LAD-186 (the type):

- A: send `anthropic-version` only with the POSTs. No new request, but an Anthropic API
  that lists its models only with its version header loses its list, so `lado model add`
  on it degrades from a check against the list to a warning. Long-term cost: a silent loss
  of a check on the servers Claude Code uses.
- B (taken): ask `GET /v1/models` without the header first, as now alone, and once more
  with it among the second wave of requests (in parallel, so no extra time; 8 requests
  instead of 7, each still within 5 s). The type and the models come from the plain list;
  the list asked with the header counts only when the plain one gives no list. Long-term
  cost: one request more per probe, in the probe's rules of one request per check.
- C: keep the header and change the type rule (a server with chat completions or the
  Responses API is OpenAI-compatible whatever its list's shape). No request more, but the
  type stops following what the server answered and an Anthropic gateway with chat
  completions turns OpenAI-compatible: a heuristic that drifts from the spec's rule.

Held against ROADMAP's coming steps (Settings → Models shows the type, the models and the
same refusals; a session on a configured model), B keeps one source of truth (the probe)
for both, and the neutral core is untouched (no provider named; Claude Code's API is one of
three).

## What Changes

- The probe asks `GET /v1/models`, `GET /api/version` and `GET /api/v0/models` without
  `anthropic-version`, and adds one `GET /v1/models` with it to its second wave. A gateway
  that speaks both APIs (LiteLLM) is `OpenAI-compatible`; a server that lists in
  Anthropic's shape without the header stays `Anthropic-compatible`, and one that lists
  only with it is `Anthropic-compatible` with that list. The CLIs do not change.
- The `models:` line of `probe` and `add` marks each model LM Studio types `embeddings`:
  `models: qwen3-8b, text-embedding-nomic-embed-text-v1.5 (embeddings)`.
- `lado model add … --server <s>` refuses a model the server marks as embeddings: `<model>
  is an embeddings model on <server>; an agent needs a chat model: lado model-server probe
  <address> lists the models`, exit 1, nothing saved. A server with no such mark (Ollama, a
  plain OpenAI-compatible one) is checked as now.
- `lado model-server add` prints `same address as model server "<name>"` for each other
  saved server at the same address, after the probe's lines and before `Saved model
  server …`, and saves the server; `--replace` does not count the server it replaces.
- `lado model remove <name>…` takes several names: it finds them all first (one not found
  refuses the command and removes nothing), then removes each, `Removed model "<name>".` a
  line. The refusal to remove a server a model uses names one command for all its models:
  `remove them first: lado model remove "a" "b" "c"`.

## Scope

- The four tasks above, in `model_servers.py`, `model_settings.py`, `cli.py`, the fake
  server of the tests, `docs/cli.md`, the specs `model-servers` and `configured-models`,
  and CHANGELOG's lines of the unreleased features under `## 0.45.0 (unreleased)`,
  `### New` (they are not released, so `### Fixed` is not touched).

## Out of scope

- Settings → Models and its API: the epic's next step; it reuses these rules.
- A session on a configured model, a second check of models after `--replace`, a warning
  for a Claude Code or Codex model on a server: the step after it (LAD-180).
- Changing a model in place, renaming servers or models: not asked for.
- Models of embeddings for a future feature (vectors): they would be an entry of their own
  without `--cli`; nothing here closes that way, and the `(embeddings)` mark is ready for
  it. Not built until a feature needs it.
- A server already saved with the wrong type keeps it until `lado model-server add <name>
  <address> --replace`: the type is stored at saving, the features are unreleased, and only
  test stands have such entries; no migration for it.
- An embeddings mark from Ollama or OpenAI-compatible servers: they give none the probe
  reads; without a mark LADO stays silent, as now.
- Doctor asking a shared address once: two names may carry two keys, so each is asked.

## Impact

- Code: `src/lado/model_servers.py` (the headers per request, the second list, the type,
  `Probe.embeddings`, the `models:` line), `src/lado/model_settings.py` (the embeddings
  refusal, the same-address line, several names in `remove_model`, the removal's hint),
  `src/lado/cli.py` (`lado model remove` with `nargs="+"`, the same-address lines of add).
- Tests: `tests/fake_model_server.py` (answers by a header; LM Studio types),
  `tests/test_fake_model_server.py`, `tests/test_model_servers.py`,
  `tests/test_model_settings.py`, `tests/test_cli_model_server.py`,
  `tests/test_cli_model_settings.py`, `tests/integration/test_model_server_probe.py`,
  `tests/integration/test_model_settings_process.py`.
- Docs: `docs/cli.md`; CHANGELOG.md.
- Version: within 0.45.0 (minor, unreleased): `lado model remove` takes several names (a CLI
  change). No schema change, no MCP tool, no dependency.
