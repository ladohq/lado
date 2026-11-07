## Context

The epic branch has the probe (`model_servers.py`: `probe` sends `GET /v1/models` alone,
then at once `GET /api/version`, `GET /api/v0/models`, three API POSTs and the control,
all with one `headers` dict that holds `anthropic-version`; `_kind`, `_models`, `lines`),
the saved servers and models (`model_settings.py`: `add_server`, `remove_server`,
`add_model` → `_on_server`, `remove_model`) and their commands (`cli.py`:
`cmd_model_server_add`, `cmd_model_remove`). The fake server (`tests/fake_model_server.py`)
answers by `(method, path)` alone.

The human's answers (questions #2832, #2835): the scale tweak; the same address under
another name is saved and named in a neutral line, neither refused nor warned about (1а);
an embeddings model is refused for an agent and marked in the probe's models (2а);
`lado model remove` takes several names and the removal's hint is one command for all (3).

## Decisions

### D1. The header of Anthropic's API goes with the POSTs and one list request only

`probe` builds the shared headers without `anthropic-version` and adds it per request:
to each POST (as now, so every API proof stays as proven on LiteLLM and LM Studio) and to a
new `GET /v1/models` in the second wave. The first `GET /v1/models` stays alone and
without it (it decides whether the address answers at all). `_all` takes per-request
headers, e.g. `asked` items of `(url, method, extra_headers)`. Why: option B of the
proposal; one request more, no extra time, no check lost on an Anthropic API.

### D2. The type and the models: the plain list first

`_kind(listed, anthropic_listed, version, lmstudio, apis)`: Ollama, LM Studio, then the
plain list's shape (Anthropic's: an item `"type": "model"` or `has_more`, as now; else
OpenAI's), then, only when the plain list is no list, the headered list in Anthropic's
shape, then the APIs. `_models` takes the plain list; when it gives none, the headered one
when it is a list in Anthropic's shape; the why is the plain list's. Why: the plain list is
what an OpenAI client sees; the headered list only fills a gap, so a gateway that speaks
both is never read twice or as Anthropic.

### D3. Embeddings come from LM Studio's own list, kept on the Probe

`Probe.embeddings: frozenset[str]`: the ids `GET /api/v0/models` gives with `"type":
"embeddings"` (visible one-line ids, as `_models`), empty for any other server or answer.
`lines` adds ` (embeddings)` after such an id in `models:`. `_on_server` refuses a model in
`found.embeddings` after the API check and before `model_check.verdict` (Refused, the line
of the spec). Why: the probe already sends that request; one source (the probe) for both
the mark and the refusal, which Settings → Models will reuse. `llm` and `vlm` are chat
models and pass.

### D4. The same address: a pure comparison in model_settings, the line through a callback

`model_settings.same_address(a, b)` compares two probe roots by scheme, lowercased host,
port with its default filled in, and path. `add_server` gets a second callback (or reuses
`warn` under a new name, `note`) and, after the probe succeeded and before saving, calls it
with `same address as model server "<name>"` for each other saved server (all of
`state.model_servers()`, the replaced one left out by id). `cmd_model_server_add` prints
those lines on stdout after the probe's lines and before `Saved …`/`Replaced …`. Why: it
is information, not a warning (the human's 1а), so stdout, no `lado: warning:` prefix; no
key can be in it (an address holds no user or password, refused by `address`).

### D5. Several names in model remove: all found first

`cli`'s `lado model remove` takes `names` with `nargs="+"`; `model_settings.remove_models(
names) -> list[str]` resolves every name with `state.model` first, drops repeats by the
saved name, refuses the unknown ones in one line (Refused, the spec's text, names in the
order given), then removes each. A model another process removed between the two steps
(`state.remove_model` returns False) is not passed over in silence: the others are still
removed and printed, and the command ends with the refusal line for it, exit 1.
`remove_model(name)` is replaced by `remove_models`; callers in tests follow. The removal's hint in `remove_server` quotes each model
name as now and joins them with spaces. Why: one command copies cleanly; all-or-nothing on
unknown names keeps a typo from removing half.

### D6. The fake server answers by a header and types LM Studio's models

`fake_model_server.Answer` tables may hold a key `(method, path, "anthropic-version")` that
wins when the request carries that header; profiles added: `litellm` (OpenAI list plain,
Anthropic list with the header, all three APIs), `anthropic-versioned` (400 without the
header, Anthropic list with it, the Messages API), and `lmstudio` gains
`text-embedding-nomic-embed-text-v1.5` typed `embeddings` beside `qwen3-8b` typed `llm` in
`/api/v0/models` (and in `/v1/models`). Tests that count `lmstudio`'s models follow.

### D7. No migration of saved types

A server saved before this change keeps its stored type until `--replace`. Why: the
features are unreleased (0.45.0), only test stands hold such entries; a migration that
probes servers is out of the question, and one that guesses is a second source of truth.

## Test layers

| Requirement | Layer | Where |
|---|---|---|
| An API is proven without generating (headers, 8 requests) | unit | `tests/test_model_servers.py` (requests and their headers on the fake) |
| The server's type (LiteLLM, Anthropic with header) | unit; integration | `tests/test_model_servers.py`; `tests/integration/test_model_server_probe.py` (the `litellm` profile in its own process: `type: OpenAI-compatible`) |
| A server's models or no list | unit | `tests/test_model_servers.py` |
| Embeddings models are marked | unit | `tests/test_model_servers.py` (`lines`) |
| An embeddings model is no agent's model | unit; integration | `tests/test_model_settings.py`; `tests/integration/test_model_settings_process.py` (add refused, nothing saved) |
| A server at the address of another; two addresses of one server | unit; CLI | `tests/test_model_settings.py` (`same_address` table: `http://h:1234`, `h:1234/v1/`, `http://h:1234/`, `http://H:1234`, other port, other path; `--replace` of itself); `tests/test_cli_model_server.py` (order of lines, stdout) |
| model-server remove's hint | unit; CLI | `tests/test_model_settings.py`; `tests/test_cli_model_settings.py` (the hint's command run, then remove succeeds) |
| model remove with several names | unit; CLI; integration | `tests/test_model_settings.py`; `tests/test_cli_model_settings.py`; `tests/integration/test_model_settings_process.py` (several models of one server removed, then the server) |
| The key canary (LAD-116, LAD-182) | integration | `tests/integration/test_model_settings_process.py` stays green; the new lines (`same address`, embeddings refusal) are added to the streams it scans |

The crossing of processes here is the CLI talking to the fake server over HTTP; the fake
agent is not involved (no session reads these settings yet).

Regression: `make lint`, `make test`, `uv run pytest -m integration -n auto
tests/integration/test_model_server_probe.py tests/integration/test_model_settings_process.py`;
`openspec validate model-settings-checks --strict`, `openspec validate --specs --strict`,
and a trial archive in a copy of `openspec/` with `openspec validate --specs --strict`
there, its result in the PR's description.
