Task: LAD-182

## Why

A human who wants LADO's agents on a model of their own (haiku for light work, a Qwen on
the LM Studio of their laptop, a model behind the company's gateway) has to name it again
everywhere: the CLI's model in `lado start --model`, a server's address and key in every
probe. LADO keeps nothing of it: `lado model-server probe` (capability `model-servers`)
learns what a server is and forgets it, and a session's model (`session-model`) is a CLI
and a model typed at each start.

Root cause: LADO has no place for the human's own settings, so a model and a server have
no name to be referred to by. Every later piece of the work on models (Settings → Models,
a session on a model by its name, the human's power table) needs one.

Options weighed for the store:

- A (taken): two tables in `lado.db`, `model_servers` and `models`, one row per entry;
  each server's key in a file of its own under `LADO_HOME` (mode 600), never in
  `lado.db`. The human's power table later becomes a third table beside them. Long-term
  cost: one schema migration now and one per later kind of setting; entries take part in
  `lado.db`'s backups, migrations and foreign keys (a model cannot point at a server that
  is gone) for free.
- B: one JSON settings file under `LADO_HOME` (`settings.json`), keys beside it in files.
  No migration, but a second store with its own locking, atomic writes, versioning and
  backup next to `lado.db`, and no reference check between a model and its server: two
  sources of truth for what the human set.
- C: a file per entry (`model-servers/<name>.json`). Listing reads a folder, but a name
  with spaces or Cyrillic must be encoded into a file name, renaming touches the
  references by hand, and the same second-store costs as B.

Each entity has one table; a server has a key file besides, because the key stays out of
`lado.db` (the human's decision for the epic: the key belongs to the server, is given only
to its agents and is kept in a file of its own, mode 600).

## What Changes

- New `lado model-server add <name> <address> [--key] [--replace]`: probes the server as
  `lado model-server probe` does, prints the same lines, refuses an address that does not
  answer or is no server LADO knows, and saves the server under the name: its address, type
  and the APIs it proved. `--key` reads the key without echo or from stdin, as the probe's
  does, and keeps it in the server's own key file (mode 600). `--replace` probes a saved
  server's new address (and new key, or the kept one) and replaces them; its models stay.
- New `lado model-server list` (no network: name, address, type, whether a key is kept, the
  CLIs that can use it) and `lado model-server remove <name>` (removes its key file too;
  refused while a model refers to the server, naming the models).
- New `lado model add <name> --cli <cli> --model <model> [--server <name>]`, `lado model
  list`, `lado model remove <name>`. On adding, the model is checked by the session
  model's thresholds: an alias of the CLI or a name in the list (the CLI's own, or the
  server's when a server is named) is saved; a name the list lacks is refused; with no list
  it is saved with a loud warning. A named server must answer and must suit the CLI (the
  API its provider speaks among the APIs the server proves).
- Names of servers and models: one line of visible text, 1 to 64 characters, spaces and
  any script allowed; a name is taken and found ignoring case.
- A key sent over plain `http://` to a host that is neither `localhost`, a loopback, a
  private or link-local address nor `host.docker.internal` gets a loud warning, in `add`
  and in `probe`.
- The messages of a probe that name a command to run (a server asking for a key, the
  container's `host.docker.internal` hint) name the command that was run: `probe` or
  `add`.
- `lado doctor` checks each saved server: whether it answers, and whether its key file is
  there with mode 600; a key file of no saved server is reported as left over.
- `lado.db` goes from schema 37 to 38 (the two tables).

## Scope

- `src/lado/state.py` (the two tables, the migration, their reads and writes),
  `src/lado/model_settings.py` (new: the entries' rules, the key files, the checks on
  adding), `src/lado/model_servers.py` (the command named in its messages, the plain-http
  rule), `src/lado/model_check.py` (a verdict against a server's list),
  `src/lado/project_secrets.py` (its link-refusing writer shared with the key files),
  `src/lado/cli.py` (the commands), `src/lado/doctor.py` (the servers' check).
- Tests: unit (state, model_settings, the CLI commands, doctor, the migration), integration
  (the real commands against `tests/fake_model_server.py` in its own process, the key
  canary).
- Docs: `docs/cli.md`, `docs/design/modules.md`, AGENTS.md's Layout line, CHANGELOG under
  `## 0.45.0 (unreleased)`, `### New`; the delta of `model-servers` and the new capability
  `configured-models`.

## Out of scope

- Settings → Models in the UI, the API methods it needs, ready-made models for the
  installed CLIs: the next work builds them on these entries (only what is used: no API
  method without its page).
- A session on a configured model (`lado start --model <name>`, the launch window's
  choice), agents on a server, the key in an agent's environment, a check before a start:
  later work; no session reads the entries yet.
- What a session does when the model or server it uses is removed: decided with the
  sessions that use them; here a server a model refers to cannot be removed.
- Changing a model (`--replace` for models), renaming a server or a model: a model is
  removed and added again (nothing refers to it yet); renaming was not asked for.
- Removing a server's key without removing the server: a key the server ignores does no
  harm; remove and add again.
- Effort in a model's entry, power tables, roles: later work.
- Claude Code and Codex actually running on a server: later work. Their models with a
  server are saved by the API rule (the human, question #2733: a refusal comes, loudly,
  when a session would start on one before LADO supports it).
- The server's list of models kept in `lado.db`: it changes on the server; it is read
  fresh when a model is added and by `doctor`.
- A server that does not answer when a model naming it is added, saved unchecked: refused
  instead (the human, question #2733), as a server that does not answer is when added.
- Removing a server together with its models (`--with-models`): refused instead, naming
  them (the human, question #2733).

## Impact

- Code: new `src/lado/model_settings.py`; `state.py`, `model_servers.py`, `model_check.py`,
  `project_secrets.py`, `cli.py`, `doctor.py`.
- Schema 37 → 38: two new tables; `tests/agent_helpers.previous_schema` undoes them.
- New files under `LADO_HOME`: `model-servers/<id>/key` (folders 700, files 600);
  `lado uninstall` deletes them with `LADO_HOME`.
- No API, UI or `web/` change (`make web` not needed); no provider changes.
- Version: the minor (new CLI commands, a schema migration), within the epic's
  `## 0.45.0 (unreleased)`.
