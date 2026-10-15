Tests first in each section; each task is one commit.

## 1. The backup and the result of `state.migrate`

- [x] 1.1 Unit tests (layer 1, `tests/test_state.py` or the file that tests `migrate`): a
  migration writes `backups/lado.db.schema-<N>` with the old schema's content, removes an
  earlier `lado.db.schema-*` and keeps `lado.db.<version>`; nothing to migrate writes
  nothing; a backup that cannot be written raises and leaves the schema; a failing step
  leaves the schema and keeps the backup; the result names both versions and the path
  (D1-D4).
- [x] 1.2 `state.migrate`: the backup by SQLite's backup API (the copy shared with
  `self_update.restore`), the kept files, the result and the errors. `uv run pytest
  tests/test_state.py tests/test_self_update.py -n auto`.

## 2. The line and the message

- [x] 2.1 Unit tests (`tests/test_runtime.py` / `tests/test_cli.py`): `lado ls` on an
  older schema prints the upgrade line; a failing step exits 1 with the message, no
  traceback, `install the LADO you had before`, and an `errors.jsonl` line; with
  `LADO_CONTAINER=1` the `LADO_IMAGE` way back; a backup failure's message; `lado stop
  --all`'s migration prints the line too.
- [x] 2.2 `runtime.migrate_if_safe` and `stop_all`'s migration path (D4). `make test`.

## 3. Compose's way back

- [ ] 3.1 `docker/compose.yaml` header (D5); `tests/test_docker.py` checks the block
  names `lado.db.schema-` and `LADO_IMAGE`.

## 4. Container tests

- [ ] 4.1 Helper: a home volume seeded with a `lado.db` made on the host (D6).
- [ ] 4.2 `tests/container/test_migration.py` (layer 7): the migration on start (health,
  schema, backup, `docker logs` line, `lado ls` lists the session); a migration that
  fails (the message in `docker logs`, no traceback, schema kept); the compose header's
  steps put the backup back. `make docker && make test-container`; CI's `container
  (amd64)` and `container (arm64)` green.

## 5. Documents

- [ ] 5.1 AGENTS.md (Layout: `state.py`'s migration and backup, `docker/`; Commands: the
  container tests' list), CHANGELOG.md under 0.39.0. `make lint`.
