# Models in settings: the store, servers and models from the CLI — design

Task: LAD-182 (epic LAD-154). Change: `openspec/changes/model-settings/` (proposal, the
delta of `model-servers`, the new capability `configured-models`, design.md D1-D11). No
mockup: the change has no screen. Scale: full (a schema migration, two new entities, new
commands, two capabilities).

## What the human sees

The human sets a model server and a model once, under names; nothing uses them yet, and a
session without them is as before.

```
$ lado model-server add "LM Studio дома" localhost:1234
http://localhost:1234 (added http://)
type: LM Studio
models: qwen3-8b, gemma-3-12b
CLIs: Kilo CLI, OpenCode (chat completions)
not: Codex CLI (no Responses API), Claude Code (no Anthropic Messages API)
Saved model server "LM Studio дома".

$ printf '%s' "$KEY" | lado model-server add work https://gw.corp/llm --key
…
Saved model server "work".

$ printf '%s' "$KEY" | lado model-server add ext http://llm.example.com --key
lado: warning: the key goes to llm.example.com over plain http://, unencrypted; use https:// if the server has it
…

$ lado model-server add "LM Studio дома" localhost:1235 --replace
…
Replaced model server "LM Studio дома".

$ lado model-server list
NAME            ADDRESS                TYPE               KEY  CLIs
LM Studio дома  http://localhost:1235  LM Studio          no   Kilo CLI, OpenCode
work            https://gw.corp/llm    OpenAI-compatible  yes  Kilo CLI, OpenCode, Codex CLI

$ lado model add "Локальная Qwen" --cli opencode --model qwen3-8b --server "LM Studio дома"
Saved model "Локальная Qwen": OpenCode, qwen3-8b on LM Studio дома (in LM Studio дома's list of models)

$ lado model add Быстрая --cli claude --model haiku
Saved model "Быстрая": Claude Code, haiku (an alias of Claude Code)

$ lado model list
NAME            CLI          MODEL     SERVER
Быстрая         Claude Code  haiku     —
Локальная Qwen  OpenCode     qwen3-8b  LM Studio дома

$ lado model-server remove "LM Studio дома"
lado: model server "LM Studio дома" is used by the models Локальная Qwen; remove them first: lado model remove Локальная Qwen

$ lado model remove "Локальная Qwen"
Removed model "Локальная Qwen".
$ lado model-server remove "LM Studio дома"
Removed model server "LM Studio дома".
```

Refusals (exit 1, nothing saved): an address that does not answer (`http://localhost:1234
does not answer (connection refused)`, in LADO's container with the hint `… a server on
your machine: lado model-server add "LM Studio дома" http://host.docker.internal:1234 (not
tried)`); a server that asks for a key (`… asks for a key (401): run lado model-server add
"work" http://gw:4000 --key`); a name taken in any case; a key on the command line (never
echoed); a model's CLI LADO does not know; a model its CLI's or server's list lacks; a
model's server that does not answer (`… LADO cannot check qwen3-8b`); a server that does
not suit the CLI (`LM Studio дома does not suit Codex CLI: it has no Responses API; it
suits Kilo CLI, OpenCode`). A CLI or server that gives no list saves the model after a
warning.

`lado doctor` adds one line when servers are saved:

```
[WARN] Model servers: LM Studio дома answers (LM Studio); work does not answer (connection refused)
```

## Root cause and options

LADO has no place for the human's own settings, so a model and a server have no name to
refer to. Options for the store (the proposal weighs them): **A** two tables in `lado.db`
and a key file per server (taken); **B** one JSON settings file in `LADO_HOME`; **C** a
file per entry. B and C make a second store beside `lado.db` with its own locking,
versioning and backup and no reference check between a model and its server: two sources
of truth. A costs one migration now and one per later kind of setting, and gets
`lado.db`'s backups, migrations and foreign keys.

## Held against the roadmap and the design principles

- **Coming steps.** Settings → Models (next) calls `model_settings` (D3), which raises one-line
  refusals and returns the check's text: the page shows the same texts under its fields.
  The session on a configured model (after it) takes a model by its name: a row of
  `sessions.power` will name a model (the entry holds the CLI, the CLI's model, the
  server's id; effort is a column added later); the server's address, type and APIs and
  the key file are all that the OpenCode/Kilo config content and `{env:…}` need. The
  human's power table becomes a third table in the same store.
- **Neutral core.** Nothing names a provider above `providers/`: the CLI is a provider's
  name, compatibility reads `Provider.server_api`, the list reads `Provider.model_list`.
  All four providers can be saved; whether a session runs on a server is the later work's
  (Claude Code and Codex models on a server are saved by the API rule, question #2733).
- **One source of truth.** A server has a key exactly when its key file is there (no
  column); the server's models are not kept (they change); a model refers to its server by
  id.
- **No silent drops.** Every refusal names its reason; a list LADO cannot read gives a
  warning, not a silent save; a server a model uses is not removed; a key over plain
  `http://` to a public host is warned about.
- **Only what is used.** No API method without its page; no `--with-models`, no model
  `--replace`, no rename.

## Decisions (design.md)

D1 the store and the migration 37 → 38 · D2 the key file `<LADO_HOME>/model-servers/<id>/key`
with `project_secrets`' writer · D3 `model_settings.py` · D4 names (visible one line, 1-64,
`casefold`) · D5 the command named in a probe's messages · D6 the plain-http warning ·
D7 a server a model uses · D8 the order of a model's checks, a verdict against a server's
list · D9 doctor · D10 the CLI and `NOT_MIGRATING` by subcommand · D11 no API method now.

## Test layers per requirement

| Requirement | Layer | Why that layer |
|---|---|---|
| model-servers: add saves a server; a server that fails the probe is not saved; --replace | unit (`tests/test_model_settings.py`, `tests/test_cli_model_settings.py`, in-process fake server) + integration | the real command against the fake server in its own process crosses processes |
| a server's name; a model's name | unit | pure rules |
| the key kept in its own file; the key of add read as the probe's | unit (mode, rename, link refused, argv refusal) + integration canary | the canary needs the real process, its output, `lado.db`, the error journal and every file of `LADO_HOME` |
| list without asking; remove refuses a used server | unit | a request recorder on the fake server proves "no request" |
| plain-http warning | unit (`tests/test_model_servers.py`) | pure rule of a host |
| saved servers in lado.db; the migration | unit (`tests/test_state.py`, `previous_schema`) | SQLite in a temp `LADO_HOME` |
| doctor's line, left-over folders, exit status, no migration | unit (`tests/test_doctor.py`) | fake servers in-process |
| localhost in the container; asks for a key (modified) | unit | text of `ProbeError` with the command |
| configured-models: add, CLI checks, server checks, list, remove | unit (a fake provider's `model_list`, the fake server) + integration (one add with a server, one refusal) | the CLI's list and the server cross processes in the real command |
| no session uses them | unit (`lado start` path reads no entry) + the existing integration `test_session_model.py` in the regression run | behaviour unchanged |
