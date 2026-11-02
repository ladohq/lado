## Context

The epic branch has `lado model-server probe` (`model_servers.py`: `address`, `probe`,
`Probe`, `ProbeError`, `lines`; the key read by `cli._read_secret`, refused in argv by
`_ProbeParser.error` and the `_NO_VALUE` sentinel), each provider's `server_api`
(`providers/base.py`), and the session model's check (`model_check.py`: `check`,
`verdict`, `Verdict`) against `Provider.model_list(env)` (`base.ModelList`: aliases,
models or None with why, the command that prints the list). `lado.db` is at schema 37
(`sessions.power`). A project's secrets are files written by `project_secrets._write`,
which opens every folder from `LADO_HOME` down without following a link, makes them 700
and the file 600, and writes by rename. `cli.NOT_MIGRATING` keeps `model-server` (the
probe) from migrating `lado.db`. `lado doctor` reads `lado.db` without migrating
(`state.SchemaError` → "not at schema"). `lado uninstall` deletes `LADO_HOME` whole.

The human's answers: the epic's concept (D18: models and servers set once under names, the
rest refers to a name; the server is an entry of its own; the key belongs to the server,
D15), and question #2733 of this change (1а a server a model uses is not removed; 2а
`--replace`; 3а a model on a server that does not answer is refused; 4а Claude Code and
Codex models on a server are saved by the API rule; 5а names ignoring case; 6а the commands'
output as drafted, the plain-http warning in `probe` too).

## Goals / Non-Goals

Goals: one place for the human's model settings; servers and models as named entries,
added, listed and removed from the CLI, checked on adding; the key in a file of its own
and nowhere else; `doctor` checks the servers. Non-goals: the proposal's Out of scope.

## Decisions

### D1. The store: two tables in lado.db, the key in a file per server

Schema 37 → 38, `MIGRATIONS[37] = [MODEL_SERVERS_TABLE, MODELS_TABLE]`:

```sql
CREATE TABLE IF NOT EXISTS model_servers (
    id TEXT PRIMARY KEY,            -- uuid4 hex[:12], never changes: the key file's folder
    name TEXT NOT NULL,             -- as the human gave it
    folded TEXT NOT NULL UNIQUE,    -- name.casefold(): the name is taken ignoring case
    address TEXT NOT NULL,          -- the probe's root (model_servers.address)
    kind TEXT NOT NULL,             -- the probe's type
    apis TEXT NOT NULL,             -- JSON list of the APIs it proved, in SERVER_APIS order
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS models (
    folded TEXT PRIMARY KEY,        -- name.casefold()
    name TEXT NOT NULL,
    cli TEXT NOT NULL,              -- a provider's name
    model TEXT NOT NULL,            -- as the CLI names it
    server TEXT REFERENCES model_servers(id),  -- NULL: the CLI's own way to its models
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

`folded` makes SQLite enforce the case-insensitive name (SQLite's `NOCASE` folds ASCII
only; `Быстрая`/`быстрая` need Python's `casefold`). The server's reference is its id, so
`--replace` and a later rename touch one row. `PRAGMA foreign_keys = ON` (state.connect)
refuses deleting a server a model refers to; the command checks first to name the models
(D7). Whether a server has a key is the key file's presence, not a column (one source of
truth). The server's models are not kept: they change on the server (proposal, Out of
scope). The human's power table later is a third table beside these. `state.py` gets
`ModelServer` and `ConfiguredModel` dataclasses and `add_model_server`,
`replace_model_server`, `model_servers`, `model_server` (by name), `remove_model_server`,
`add_model`, `models`, `model` (by name), `remove_model`, `models_on(server_id)`.
`tests/agent_helpers.schema_before` undoes step 37 (drops both tables).

The way back: an `lado update` rollback restores `lado.db` from its backup; an older LADO
refuses schema 38 (state.connect), as for every migration; the key files of a rolled-back
home are left over and `doctor` names them (D9).

### D2. The key file

`<LADO_HOME>/model-servers/<id>/key`, written by `project_secrets`' link-refusing writer:
`_write`, `_remove` and `_open_chain` become public as `write_at(parts, where, name,
value)` and `remove_at(parts, where, name)` (the project's and LADO's secrets keep calling
them), with `parts = ("model-servers", id)` and `name = "key"`. Folders 700, file 600,
rename over the old key, a link on the way refused. The id is hex, so no name the human
gave reaches the file system. A folder per server (not `model-servers/<id>.key`) because
the writer's file name must be a variable name and the id may start with a digit. Removing
the server removes the file, then its empty folder (`os.rmdir` relative to the opened
`model-servers` folder). The key file is never read into an agent here; `model_settings`
reads it (`agent_env`'s folder reader is for variable folders: a plain read of one file,
mode and link checked, refusing anything but a regular file).

Order on `add`: probe (network, nothing written) → write the key file → insert the row; an
insert that fails (name taken by a concurrent add) removes the key file it wrote. On
`--replace`: probe with the new or kept key → write the new key (rename: the old is whole
until then) → update the row; a failed update leaves the new key with the old address, said
in the error. On `remove`: delete the row (refused while models refer) → remove the key file
and folder; a removal that fails exits 1 naming the folder, and `doctor` names it as left
over.

### D3. model_settings.py: the entries' rules

A new module `src/lado/model_settings.py` holds what the commands do, so the next work's
UI server calls the same functions: `check_name(name)`, `add_server(name, address, key,
replace)`, `remove_server(name)`, `server_key(server) -> str | None`, `add_model(name, cli,
model, server_name)`, `remove_model(name)`, `doctor_lines()`. It raises
`model_settings.Refused` (one line, exit 1) and lets `ValueError` of the address through
(exit 2), and returns the verdict's text and warnings for the CLI to print. `state.py`
keeps the SQL; `model_servers.py` keeps the probe; `project_secrets.py` keeps the writer.

### D4. Names

`check_name`: `text.one_line(name) == name` (no hidden or control character, no line break,
no spaces at the ends), `1 <= len(name) <= 64`. Taken is decided by `folded`; found by
`folded`. A name that starts with `-` is fine to keep but argparse takes it as an option:
`docs/cli.md` says `--` ends the options (`lado model remove -- -x`).

### D5. The command named in a probe's messages

`model_servers.probe(text, key, command="lado model-server probe")`: `ProbeError`'s
"asks for a key" line and `_container_hint` format the command given. `cli.py` passes
`lado model-server add "<name>"` (and ` --replace` when given). The name is quoted with
double quotes always (it may hold spaces); a name with a `"` is shown as it is (a hint,
not a shell line). No other text of the probe changes.

### D6. The plain-http warning

`model_servers.plain_http_warning(root, key) -> str | None`: with a key, an `http://` root
whose host is not `localhost`, `host.docker.internal`, or an IP address that is loopback,
private or link-local (`ipaddress`; IPv6 `fc00::/7` and `fe80::/10` count) gives
`the key goes to <host> over plain http://, unencrypted; use https:// if the server has it`.
No name is resolved (a lookup could leak the name and would make the rule depend on the
network). `cli.py` prints it as `lado: warning: …` before the probe of `probe` and `add`.
`host.docker.internal` counts as local: it is the human's own machine seen from the
container.

### D7. Removing a server a model uses

`remove_server` reads `state.models_on(id)` and refuses with the models' names sorted
(question #2733, 1а); the foreign key backs it against a race. No `--with-models`.

### D8. Adding a model

Order, each step refusing before the next: name free (D4) → CLI is a provider's name
(`providers.names()`; refusal names them) → model not empty after `strip()` → server named
and saved (`state.model_server`) → for a server: provider's `server_api` not empty →
`model_servers.probe(server.address, key)` (a `ProbeError` refuses with its line and
`LADO cannot check <model>`, question #2733, 3а) → `server_api in found.apis`, else
`<server> does not suit <title>: it has no <api>; it suits <titles>` from `found.clis()` →
the model against `base.ModelList(models=found.models, why=found.models_why,
command=f"lado model-server probe {server.address}")` → for no server:
`model_check.check(provider, model, agent_env)` with the agents' environment as `lado
start --model` reads it. `model_check.verdict` gains `whose: str | None = None` (default
the CLI's title) so the texts say `in LM Studio дома's list of models`. REFUSED → refused,
WARN → saved with the warning, OK → saved. The probe uses the fresh answer, not the APIs
kept at the server's adding: the server may have changed. Claude Code and Codex models on a
server are saved by this rule (question #2733, 4а).

### D9. doctor

`doctor.check_model_servers()`: reads the servers with `state` (no migration; a
`SchemaError` gives `INFO` "not checked: lado.db is not at this LADO's schema"), probes them
in threads at once (each probe already caps itself at about 10 s, so the line takes about
10 s at most whatever the count), checks each key file there is (a server has a key exactly when
its file is there, so a missing file is a server without a key: the check is a regular
file, mode 600, no link), and lists the folders of
`model-servers/` whose name is no server's id as left over. `OK` when all answer and all
key files are right, else `WARN`; never `FAIL` (a server in the network being off is not
LADO's fault and must not fail doctor's exit). Not in the UI's System panel: doctor's
`run_checks` is called by `lado doctor` only (`server/app.py` uses `system_info`), so the
UI never waits on the network for it.

### D10. The CLI

`lado model-server add|list|remove` and `lado model add|list|remove` with argparse
subparsers; `lado model` alone prints help. `add` of `model-server` uses `_ProbeParser` (its
own `error()` names no word of argv, since a word may be a key) and the `_NO_VALUE`
sentinel for `--key`, as `probe`; words left over refused with the fixed line, its text
naming `add`. `NOT_MIGRATING` goes from command names to (command, sub) pairs:
`("model-server", "probe")` stays non-migrating; `add`, `list`, `remove` of both migrate,
as `lado ls` does, since they need schema 38. Exit codes: 0 done, 1 refused, 2 an address
the probe does not take. Tables are printed with columns padded to the widest cell, by
characters (wide scripts may misalign; as `lado ls`).

### D11. No API method now

The UI's methods for Settings → Models come with that page in the next work (only what is
used); `model_settings` is shaped for them (D3).

## Risks / Trade-offs

- A server that is off when a model is added refuses the model (question #2733, 3а): the
  human starts the server first. Accepted.
- `--replace` without `--key` keeps the old key: a key cannot be dropped without removing
  the server. Rare; out of scope.
- `doctor` takes up to about 10 s more when a saved server hangs. Accepted: it says why.
- Names compare by `casefold`, which may differ from what a future UI's search does; the UI
  will call `model_settings`.
