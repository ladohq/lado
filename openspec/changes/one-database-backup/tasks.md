The plan with each task's tests: `docs/superpowers/plans/2026-10-24-one-database-backup.md`.

## 1. Core

- [ ] 1.1 `update.release_schema`: a release's schema from its wheel on the index, the
  sha256 checked; `agent_helpers.wheel` and wheel files in `pypi_index`; the comment on
  `state.SCHEMA_VERSION` (D2). Check: `tests/test_update.py`.
- [ ] 1.2 `self_update`: no `_back_up`, the schema read before the installer; the
  rollback checks the migration's copy first and restores only a newer schema from it
  (D1, D8, D9). Check: `tests/test_self_update.py`, the rollback tests reworked, none
  dropped, each asserting `backups/` unchanged.
- [ ] 1.3 `self_update.plan(to, index)` with `Restore` or a refusal, the warning in
  `print_plan`, the restore after the version check, the resume of the copy's sessions
  only; `cli._update` passes the index (D3-D7). Check: `tests/test_self_update.py`.

## 2. End to end

- [ ] 2.1 `tests/integration/test_update_process.py`: the older-version test with a
  wheel of the same schema; a downgrade across a schema with an "old" install that
  really refuses the newer schema, the old `lado ls` seeing its session; a downgrade
  without the copy stopping nothing. Check: `uv run pytest -m integration -n auto
  tests/integration/test_update_process.py`.

## 3. Release candidates

- [ ] 3.1 `scripts/rc_check.py`: `upgrade` keeps the migration's copy when the schema
  moved (after one `lado ls`); `rollback` puts it into `backups/` and leaves the restore
  to `lado update <final>`, starting only the copy's sessions; the docstring (D10, D11).
  Check: `uv run pytest tests/test_rc_check.py -n0`.

## 4. Documents

- [ ] 4.1 `docs/install.md` (What it does, When something goes wrong, Going back to an
  older version; Docker unchanged; old `lado.db.<version>` files may be removed),
  `docs/design/modules.md` (`self_update.py`, `update.py`, `state.py`'s migration),
  `docs/release.md` 4.4 (D12). Check: read against the spec; `make lint`.
- [ ] 4.2 CHANGELOG.md under `## 0.43.0 (unreleased)`: the Improved item on going back
  rewritten, a Fixed item for the deleted backup (D13). Check: docs/release.md's rules
  for items.

## 5. Regression

- [ ] 5.1 `make lint`, `make test`, the integration file with `-m integration`,
  `openspec validate one-database-backup --strict`, `openspec validate --specs --strict`,
  a trial archive in a scratch copy, CI green.
