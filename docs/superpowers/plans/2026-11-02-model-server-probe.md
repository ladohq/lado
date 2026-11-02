# What a model server is: Implementation Plan

**Goal:** `lado model-server probe <address> [--key]` names a model server's type, its
models and the agent CLIs that can use it, proven by requests that generate nothing, with
clear failures and a key kept nowhere.

**Architecture:** `model_servers.probe` sends the model list first, then the native
endpoints of Ollama and LM Studio and one empty POST per API in five threads, each under
5 s, following no redirect; `Probe.clis()` names the providers whose declared
`server_api` was proven; `lines()` is the output; `cli.py` reads the key as a secret and
prints.

**Tech Stack:** Python 3.10+ standard library (`urllib.request`, `http.server`,
`threading`, `ipaddress`), pytest (unit with `-n auto`, integration with the marker).

**Spec:** `openspec/changes/model-server-probe/` (proposal, the delta `model-servers`,
design.md D1-D10) and `docs/superpowers/specs/2026-11-02-model-server-probe-design.md`.

## Global Constraints

- No new dependency; no schema change; no API, UI or `web/` change.
- No provider name above `providers/`: the rule reads `Provider.server_api` and names
  `Provider.title`.
- Texts (exact, design.md D8, D9): `<R> does not answer (<why>)` with `connection
  refused`, `unknown host`, `no answer in 5 s`; the container's hint `LADO runs in a
  container, where localhost is the container itself; a server on your machine: lado
  model-server probe <scheme>://host.docker.internal:<port><path> (not tried)`;
  `<R>: TLS failed (<why>); a company's CA goes in the file SSL_CERT_FILE names`; `<R> asks
  for a key (<status>): run lado model-server probe <R> --key`; `<R> refused the key
  (<status>)`; `unknown server: <R> answered, but not as an OpenAI-compatible,
  Anthropic-compatible, Ollama or LM Studio server (GET /v1/models: <answer>)`; the key on
  the command line: `a server's key is never given on the command line (ps and the shell's
  history keep it); run lado model-server probe <address> --key and type it, or pipe it
  in`; `the key is empty`; the prompt `Key of the server (not shown): `.
- Output lines: `<R>[ (added http://)]`, `type: <kind>`, `models: <a, b> | none | no list
  (<why>)`, `CLIs: <titles> (<API>)[; …] | none`, `not: <title> (no <API>)[, …]` (left
  out when empty).
- CHANGELOG.md: one line under the existing `## 0.45.0 (unreleased)`, `### Added`.
- Unit suites with `-n auto`; the integration file with `-m integration`; single node ids
  with `-n0`.

## Review Focus

- The key: never in an exception's text, output or file; `--key <value>` refused without
  echo (Task 4 `test_key_on_the_command_line_is_refused_unechoed`, Task 5 canary).
- No redirect followed, no request to any other host or port, at most one per check
  (Task 3 `test_redirect_is_not_followed`, `test_one_request_per_check`).
- The hint never becomes a request (Task 3 `test_container_hint_sends_nothing_there`).
- The 5 s limit holds for a hanging server (Task 3 `test_hanging_server_does_not_answer`).

---

### Task 1: Each provider declares its server API (D5)

**Files:** `src/lado/providers/base.py`, `claude.py`, `codex.py`, `opencode_family.py`,
`tests/test_providers.py`.

- [ ] Failing test `test_each_provider_declares_its_server_api`: claude →
  `ANTHROPIC_MESSAGES`, codex → `RESPONSES`, kilo and opencode → `CHAT_COMPLETIONS`; a
  `base.Provider` subclass without it has `""`.
- [ ] Implement. `uv run pytest -n auto tests/test_providers.py` → PASS.
- [ ] Commit `Each provider names the model server API its CLI speaks (LAD-177)`.

### Task 2: The fake model server

**Files:** `tests/fake_model_server.py`, `tests/test_fake_model_server.py`.

- [ ] A `ThreadingHTTPServer` on `127.0.0.1:0` with a profile: which of the six paths
  answer and how (`openai`, `ollama`, `lmstudio`, `anthropic`, `responses-only`,
  `models-only`, `unknown` (404 everywhere), `key` (401 without `Authorization: Bearer
  <key>`), `redirect` (301 to another fake's URL), `hang` (accepts, never answers),
  `list-500`). It records `(method, path, headers, body)`. It runs as a script too:
  `python tests/fake_model_server.py <profile> <port-file> [<key>]`, writing its port.
  Tests: each profile answers as described.
- [ ] Commit `A fake model server for the probe's tests (LAD-177)`.

### Task 3: The probe (D1-D8, D10)

**Files:** `src/lado/model_servers.py`, `tests/test_model_servers.py`.

Failing tests first, one per rule (requirement of the delta in brackets):

- `test_ollama_two_apis` (names a server's type, models and CLIs): kind `Ollama`,
  models, suits Kilo CLI and OpenCode (chat completions) and Codex CLI (Responses API),
  not Claude Code.
- `test_openai_chat_only`, `test_responses_only`, `test_anthropic_messages_only`,
  `test_models_only_proves_no_api`, `test_all_three_apis` (the CLIs follow from the APIs):
  each yes and each no of the rule.
- `test_lmstudio_type`, `test_anthropic_shape_type`, `test_type_by_api_without_models`
  (the server's type).
- `test_api_proven_by_400_or_422_json`, `test_404_405_and_non_json_are_no`,
  `test_post_bodies_are_empty`, `test_one_request_per_check` (an API is proven without
  generating): the fake's record holds at most the six requests and each POST's body is
  `{}`.
- `test_list_500_is_no_list`, `test_empty_list_is_none` (models or no list).
- `test_address_forms` table: `localhost:11434` → `http://localhost:11434`, added;
  `http://h/v1/` → `http://h`; `https://gw/llm/v1` → `https://gw/llm`;
  `ftp://h`, `http://u:pw@h`, `http://h?x=1`, `http://h#f` → `ValueError` whose text has no
  `pw` (the address as given).
- `test_closed_port_does_not_answer` (sends one request only), `test_hanging_server_does_not_answer`
  (≤ 7 s wall time), `test_unknown_host_does_not_answer` (`.invalid` host), `test_tls_failure`
  (an HTTPS URL to the plain fake) (an address that does not answer).
- `test_container_hint` with `LADO_CONTAINER=1` for `localhost`, `127.0.0.1`, `[::1]`;
  `test_no_hint_outside_container`; `test_no_hint_for_a_lan_address`;
  `test_container_hint_sends_nothing_there` (localhost in the container).
- `test_key_headers` (each of the six requests carries `Authorization: Bearer` and
  `x-api-key`), `test_key_never_in_error_text` (a refused key's `ProbeError` and `repr`
  hold no key) (the key is kept nowhere).
- `test_asks_for_a_key`, `test_refuses_the_key` (asks for a key or refuses it).
- `test_unknown_server`, `test_redirect_is_not_followed` (the second fake receives
  nothing; the line names `301 to`) (an unknown server).

- [ ] Run → FAIL. Implement `address`, `probe`, `Probe`, `ProbeError`, `lines`.
  `uv run pytest -n auto tests/test_model_servers.py` → PASS.
- [ ] Commit `LADO tells what a model server is from its address (LAD-177)`.

### Task 4: The command (D7, D9)

**Files:** `src/lado/cli.py`, `tests/test_cli_model_server.py`.

- [ ] Failing tests: `test_probe_prints_the_server` (the five lines of D9, exit 0);
  `test_no_not_line_when_all_suit`; `test_failure_exit_1_on_stderr`; `test_bad_address_exit_2`;
  `test_key_from_stdin` (the fake receives it); `test_empty_key_is_refused`;
  `test_key_on_the_command_line_is_refused_unechoed` (`--key s3cr3t` and `--key=s3cr3t`:
  exit 1, no request, `s3cr3t` in neither stream); `test_model_server_alone_prints_help`.
- [ ] Implement the parser and `cmd_model_server`; the key read by the reader
  `lado project set --secret` uses, made shared with a parameter for the prompt and the
  refusal (no copy). `uv run pytest -n auto tests/test_cli_model_server.py tests/test_cli.py`
  → PASS.
- [ ] Commit `lado model-server probe prints what a server is (LAD-177)`.

### Task 5: Integration across processes

**Files:** `tests/integration/test_model_server_probe.py`.

- [ ] Tests (marker `integration`, own `LADO_HOME`): `test_probe_a_fake_server_process`
  (the fake started as a script; exit 0, the lines); `test_canary_key_is_kept_nowhere`
  (a canary piped to `--key`: the fake got it, it is in neither output nor any file
  under `LADO_HOME`, `lado.db` included, nor the error journal); `test_closed_port`;
  `test_container_hint_process` (`LADO_CONTAINER=1`).
- [ ] `uv run pytest -m integration -n auto tests/integration/test_model_server_probe.py`
  → PASS.
- [ ] Commit `The probe's key reaches the server and nothing else, across processes (LAD-177)`.

### Task 6: Docs, changelog, regression

**Files:** `docs/cli.md`, `docs/design/modules.md`, `AGENTS.md`, `CHANGELOG.md`.

- [ ] `docs/cli.md`: a paragraph for `lado model-server probe` (address forms, the
  requests, the output, each message, the key, exit codes). `docs/design/modules.md`:
  `model_servers.py`. AGENTS.md Layout: one line for `model_servers.py` (the file stays
  ≤ 200 lines). CHANGELOG: `**Find out what a model server is.**` under `### Added`.
- [ ] Regression: `make lint`; `make test` (the count as numbers); the integration file
  with its marker; `openspec validate model-server-probe --strict`; the trial archive in a
  copy of `openspec/` outside the tree (`openspec archive model-server-probe --yes`, then
  `openspec validate --specs --strict`), its result in the pull request.
- [ ] The pull request's manual check: the branch, the folder, `env | grep LADO_` and
  `unset` of leftovers, a private `LADO_HOME` and `LADO_TMUX_SOCKET`, the commands against
  a real Ollama or LM Studio (and a closed port, and `LADO_CONTAINER=1 … localhost`) and
  what each should print.
- [ ] Commit `The model server probe in the docs and the changelog (LAD-177)`.
