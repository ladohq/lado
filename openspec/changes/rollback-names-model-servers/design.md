## Context

`self_update._way_back` already opens the copy of `lado.db` read-only to learn which sessions
it lacks, and `print_plan` prints the warning from the `Restore` it returns. The keys live in
`<LADO_HOME>/model-servers/<id>/key` (`model_settings.KEYS`, `model_settings.KEY`). Model
servers came with schema 38, so a copy may or may not have the table.

## Decisions

### D1. `Restore` gets `keys`, read in `_way_back`

`Restore.keys: list[Path]` holds the folders to name, sorted. `_way_back` fills it in the same
connection that reads the sessions, and `print_plan` only prints it, as with `missing`.

### D2. The copy decides, not the target's schema number

The ids come from `SELECT id FROM model_servers` on the copy; `sqlite3.OperationalError` for a
missing table means no ids. Comparing `schema` with 38 would be a second record of when the
table came, and would miss a server added after the copy was made when both versions know
servers.

### D3. Only folders with a key file

A server saved with no key has a folder or none, and it holds no secret. The line is about
keys, so a folder without `key` (`os.path.lexists`, as `model_settings` tests it) is not listed.
`lado doctor`'s left-over line still names every folder.

### D4. An unreadable `model-servers/` does not stop the way back

The way back is a recovery, and a warning must not block it. An `OSError` other than
`FileNotFoundError` gives `keys = [<LADO_HOME>/model-servers]`, so that nothing is dropped
silently and the human still sees where to look. This differs on purpose from an unreadable
copy, which refuses, because the way back needs the copy and does not need the keys.

### D5. The warning's exact words

```text
lado: WARNING: LADO 0.44.0 knows lado.db up to schema 35; lado.db has schema 39.
  lado.db goes back to <copy>, made 2026-11-01 10:12
  by the upgrade from schema 35. Everything LADO recorded since then is lost: sessions,
  runs, gates, messages, projects, model servers, models, default models.
  Repositories, worktrees and project folders stay on disk.
  Sessions not in that copy are not started again: onsrv
  Model server keys stay on disk; remove them when you no longer need them:
    <LADO_HOME>/model-servers/ed6044c73df5
```

The first three lines and the sessions' line keep their words, so
`tests/integration/test_update_process.py` needs no change.

### D6. Test layer: unit

The change is the text of a plan and one read of a local SQLite file, so `tests/test_self_update.py`
can catch all of it. No new behaviour crosses processes: the integration test of the way back
already runs the warning through a real `lado update`.

### D7. The comment names `tests/live_models.py`

`tests/local_models.py` became `tests/live_models.py` in LAD-231. The new file no longer
speaks of LM Studio's Responses API; the task names this path, and the rule itself stands in
the spec `codex-model-server`, so the comment changes only the path.

### D8. How the live run is made

Per provider, from the worktree, the key only from the environment, the output in a log outside
the tree:

```bash
LADO_LIVE_ENDPOINT=https://openrouter.ai/api/v1 LADO_LIVE_API_KEY="$OPENROUTER_API_KEY" \
LADO_LIVE_MODEL=qwen/qwen3.7-flash LADO_LIVE_IMAGE=1 make test-live PROVIDER=<provider> \
  > <temp dir>/live-<provider>.log 2>&1
```

`<provider>` is `opencode`, `kilo` and `codex`, never empty, as an empty one would start Claude
Code. A run of skips proves nothing: the report gives the counts per provider, and only
`tests/live/test_codex_login.py` may skip. The log is checked for the key's value without
printing it. A failure from a model or provider gets one repeat, then the report names it. A
failure from the epic's code stops the step with a question to the human.

## Against the principles and the roadmap

Neutral core: nothing here depends on an agent CLI. One source of truth: the folder's names
come from `model_settings`, the ids from the copy itself. No silent drops: D4. Only what is
used: one field, read by one warning. The roadmap's coming stages do not touch the way back.
