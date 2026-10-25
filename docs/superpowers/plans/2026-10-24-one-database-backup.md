# One database backup Implementation Plan

**Goal:** `lado update` keeps no copy of `lado.db` of its own and never touches
`LADO_HOME/backups/`; its rollback and an update to an older schema both use the
migration's `backups/lado.db.schema-<N>`, the latter learning the old version's schema from
its wheel, warning before it asks, refusing without the copy, and restoring it after the
installer; `scripts/rc_check.py` works on the same single copy.

**Architecture:** `update.release_schema` reads `SCHEMA_VERSION` from a release's wheel
named by the index. `self_update.plan(to, index)` builds a `Restore` (or refuses) for a
downgrade; `print_plan` warns; `_Update` drops `_back_up`, reads the schema before the
installer, restores after the version check of a downgrade, and resumes only the sessions
the copy has; `_roll_back` checks the copy first and restores only a newer schema.
`rc_check.py` keeps the migration's copy and leaves the restore to `lado update`.

**Tech Stack:** Python 3.10+ (standard library: `urllib`, `hashlib`, `zipfile`,
`sqlite3`), pytest (unit, integration with the fake agent and a fake install).

**Spec:** `openspec/changes/one-database-backup/` (proposal with AC-1..AC-9, `design.md`
D1-D13, delta specs `update-database`, `schema-migration`, `release-candidates`) and
`docs/superpowers/specs/2026-10-24-one-database-backup-design.md` (the human's view and
the manual check).

## Global Constraints

- Python 3.10+, standard library only; no new dependency; no schema migration; no MCP,
  API or UI change; `mcp_server.py`, `hooks.py`, `providers/` untouched.
- After the installer `self_update` imports nothing new: `hashlib`, `zipfile` and the
  rest are imported at the top (its docstring's rule).
- No path writes, renames or removes a file in `backups/` but `state._back_up` (the
  migration) and `rc_check.py rollback` (D11).
- No path overwrites `lado.db` but after the plan's warning and the human's yes (or
  `--yes`), or the rollback of a migration the update itself caused.
- Texts, verbatim (the spec's):
  - `lado: WARNING: LADO <X> knows lado.db up to schema <S>; lado.db has schema <M>.`
    then `  lado.db goes back to <path>, made <YYYY-MM-DD HH:MM> by the upgrade from
    schema <S>. Everything LADO recorded since then is lost: sessions, runs, gates,
    messages, projects. Repositories, worktrees and project folders stay on disk.` (wrapped
    as in the design doc) and `  Sessions not in that copy are not started again: <names>`;
  - `lado: cannot learn which lado.db schema LADO <X> needs: <reason>; nothing was stopped`;
  - `lado: LADO <X> needs lado.db at schema <S>, and lado.db has schema <M>; <backups>
    holds no lado.db.schema-<S> to go back to (docs/install.md, Going back to an older
    version); nothing was stopped`;
  - `Restored lado.db from <path> (schema <S>)`;
  - `<why>; not rolled back: lado.db has schema <M> and backups/ holds no
    lado.db.schema-<N> for LADO <old>, so LADO <new> stays installed`.
- Tests never touch the user's home or network: `LADO_HOME`, `HOME` in `tmp_path`, the
  index a local file (`LADO_UPDATE_INDEX`), each wheel a `file://` URL to a zip the test
  writes.

## Review Focus

- Every outcome of `run()` (ok, partial, failed before and after the installer,
  rolled_back, rollback_failed, the downgrade's restore and its failures) leaves
  `backups/` byte for byte as it was, but for what the new version's own migration wrote.
- The refusals of a downgrade happen before `update.lock`'s result `running`, before any
  stop: `plan()` raises, `run()` is not reached.
- `_roll_back` after a downgrade's restore restores nothing (D8); after a forward update
  whose new version migrated, it restores `schema-<old>`; without that file it stops
  nothing (D9).
- The digest check of the wheel: a wrong sha256 is a refusal, never a schema.

## Task 1: The schema of a release (D2)

**Files:** `src/lado/update.py`, `src/lado/state.py` (a comment on `SCHEMA_VERSION`),
`tests/test_update.py`, `tests/agent_helpers.py`.

- [ ] `agent_helpers.wheel(path, schema)` writes a zip with `lado/state.py` holding
  `SCHEMA_VERSION = <schema>` and returns its sha256; `pypi_index` accepts a release
  given as files with `packagetype`, `filename`, `url`, `digests`.
- [ ] Failing tests: `release_schema` reads 31 from a `file://` wheel; a wrong digest, a
  release with only an sdist, a wheel without `lado/state.py` or without the line, a yanked
  wheel, an unreachable URL each raise with the reason in the text.
- [ ] Implement `update.release_schema(data, version) -> int` (`urllib.request.urlopen`
  with `INDEX_TIMEOUT`, `hashlib.sha256`, `zipfile.ZipFile` on the bytes, the regex
  `^SCHEMA_VERSION = (\d+)$` with `re.M`).
- [ ] `state.SCHEMA_VERSION`'s comment: `lado update` of a later LADO reads this line from
  this release's wheel; keep its form.
- [ ] `uv run pytest tests/test_update.py -n0`; commit.

## Task 2: The update keeps no copy (D1, D9, D8)

**Files:** `src/lado/self_update.py`, `tests/test_self_update.py`.

- [ ] Rework the unit tests first (none dropped without a replacement):
  - `test_lado_db_is_backed_up_before_the_installer_and_only_one_backup_is_kept` →
    `test_the_update_writes_and_removes_nothing_in_backups` (a `lado.db.0.0.1` and a
    `lado.db.schema-30` there stay; the installer sees the same listing; no "Backed up"
    line);
  - `test_a_wrong_version_rolls_back_and_restores_lado_db_when_its_schema_moved`: the
    fake installer's `bump_schema()` now also writes `backups/lado.db.schema-<old>` as a
    migration would (a helper `migrate_like_the_new_version()`), and the restore is from
    it; the copy is still there after;
  - new `test_a_rollback_without_the_migrations_copy_keeps_the_new_version`: the schema
    moved, no copy → `rollback_failed` with the reason text, the installer called once,
    no `stop` of the resumed session;
  - `test_a_rollback_keeps_lado_db_when_its_schema_did_not_move`,
    `test_a_failed_reinstall_of_the_old_version_is_a_failed_rollback`,
    `test_a_failed_installer_rolls_nothing_back_and_keeps_lado_db`,
    `test_a_session_that_does_not_resume_is_partial_and_rolls_nothing_back`,
    `test_a_server_that_does_not_come_up_on_the_new_version_rolls_back`,
    `test_a_new_server_that_answers_with_another_version_rolls_back`,
    `test_a_loop_that_does_not_end_in_the_rollback_leaves_lado_db_as_it_is`: kept, their
    texts that name `self.backup` now name the migration's copy, each also asserts
    `backups/` unchanged.
- [ ] Implement: remove `_back_up` and `self.backup`; `self.schema =
  state.schema_version()` before the installer; `_roll_back` begins with the copy check
  (D9) and restores when `state.schema_version() > self.schema` from
  `backups() / f"lado.db.schema-{self.schema}"`; its texts name that path.
- [ ] `make test`; commit.

## Task 3: An update to an older schema (D3-D7)

**Files:** `src/lado/self_update.py`, `src/lado/cli.py`, `tests/test_self_update.py`,
`tests/test_self_update.py`'s CLI tests (`main(["update", …])`).

- [ ] Failing tests:
  - plan to an older release, `lado.db` at 35, wheel at 31, `schema-31` there with a set
    mtime, sessions `app` (in the copy) and `web2` (not): `Plan.restore` has the copy, 31,
    the time and `["web2"]`; `print_plan` prints the warning verbatim on stderr, and no
    "an older LADO may refuse" line;
  - same schema (wheel 35): no `restore`, no warning; no `lado.db`: no wheel fetched (the
    index's URL points at a missing file and nothing fails); a newer target: no fetch;
  - refusals: no `schema-31` (only `schema-35`), an unreadable wheel: `plan()` raises
    `LadoError` with the texts; `cmd_update` exits 1, nothing stopped (the recorder sees
    no `stop`), no `update-result.json` written;
  - run: after the installer and the version check, `lado.db` holds the copy's rows and
    schema 31, the copy stays, `Restored lado.db from … (schema 31)` is said, `start` is
    called for `app` only, the result is `ok` with `database` `restored`;
  - a restore that raises `sqlite3.Error` → `_roll_back`, `lado.db` at 35, `rolled_back`,
    `kept`; X's server not coming up after the restore → the version before reinstalled,
    nothing restored (`kept`), `lado.db` at 31 (the old version's resume would migrate).
- [ ] Implement `Restore`, `plan(to, index=None)`, the warning in `print_plan`, the
  restore step and the filtered resume in `_Update.run`; `cli._update` passes `index`.
- [ ] `make test`; commit.

## Task 4: End to end (AC-1, AC-3, AC-5)

**Files:** `tests/integration/test_update_process.py`.

- [ ] `test_update_back_to_an_older_lado_resumes_with_its_public_commands`: the index's
  0.1.0 gets a wheel of schema `state.SCHEMA_VERSION` (same schema: no warning, nothing
  restored); its assertion on "an older LADO may refuse lado.db" goes.
- [ ] New `test_update_to_an_older_schema_restores_the_migrations_copy_and_the_old_lado_sees_its_session`:
  - session `old` started on this working copy (fake provider), then stopped;
    `agent_helpers.previous_schema()` turns `lado.db` back to N-1 (N =
    `state.SCHEMA_VERSION`); `lado start` of `old` on this working copy migrates it,
    writing `backups/lado.db.schema-<N-1>` with `old` in it, and runs it;
  - session `new` started on this working copy: it is not in the copy;
  - the "old" install: `Install` whose sitecustomize, under `LADO_TEST_SCHEMA`, sets
    `state.SCHEMA_VERSION` to N-1 and drops `state.MIGRATIONS[N-1]`, so it refuses schema
    N as 0.42.0 refuses 35; the index's 0.1.0 has a `file://` wheel saying N-1;
  - `lado update 0.1.0 --yes`: stderr has the warning naming `new`; the installed lado is
    asked to `start` `old` only;
  - after it: the installed (old) `lado ls` exits 0 and lists `old`, not `new`;
    `backups/` holds the same `schema-<N-1>` file; `update-result.json` is `ok` with
    `database` `restored`.
- [ ] New `test_update_to_an_older_schema_without_its_copy_stops_nothing`: the copy
  removed → exit 1 with the refusal, the session's loop still runs, the installer never
  called.
- [ ] `uv run pytest -m integration -n auto tests/integration/test_update_process.py`;
  commit.

## Task 5: `scripts/rc_check.py` (D10, D11)

**Files:** `scripts/rc_check.py`, `tests/test_rc_check.py`.

- [ ] Rework its tests: `upgrade` from a final keeps `~/.lado-rc/lado.db.<final>` from
  `backups/lado.db.schema-<before>` when the fake `lado update` moved the schema (it
  writes that copy as the migration would), keeps nothing and says `lado update <final>`
  alone goes back when it did not, runs `lado ls` once after the update; the pre-release
  and not-installed cases as before; `rollback` writes the copy into
  `backups/lado.db.schema-<copy schema>` before `lado update <final>`, restores nothing
  itself (the fake `lado update` does the restore, as the RC would), checks the schema,
  starts only the planned sessions the copy has; the refusals as before.
- [ ] Implement; the module docstring's `upgrade`/`rollback` lines follow.
- [ ] `uv run pytest tests/test_rc_check.py -n0`; commit.

## Task 6: Documents (D12, D13)

**Files:** `docs/install.md`, `docs/design/modules.md`, `docs/release.md`, `docs/cli.md`
(only if it names the update's backup: it does not today), `CHANGELOG.md`.

- [ ] `docs/install.md`: "What it does" without step 3 (and a line that the database's
  copy is the migration's, `~/.lado/backups/lado.db.schema-<N>`); "When something goes
  wrong" restores from that copy and keeps the new version without it; "Going back to an
  older version": `lado update X` checks X's schema, warns and puts the copy back; the
  0.43.0 → 0.42.x paragraph without copying by hand; a line that `lado.db.<version>`
  files of earlier updates may be removed; the Docker path unchanged.
- [ ] `docs/design/modules.md`: the `self_update.py` paragraph (no backup, the plan's
  `Restore`, the restore step, the rollback's copy check) and `update.py`
  (`release_schema`); `state.py`'s migration paragraph without "leaves `lado update`'s
  `lado.db.<version>`" as an owner.
- [ ] `docs/release.md` 4.4: `rollback` leaves the restore to `lado update <final>`;
  the user's own way back sentence (no "until then").
- [ ] CHANGELOG.md `## 0.43.0 (unreleased)`: rewrite the Improved item "The guide says how
  to go back from 0.43.0 to 0.42.0" to "`lado update` back to an older version puts the
  database back itself" (warns first, refuses without a copy); a Fixed item "`lado
  update` no longer deletes the migration's backup of the database".
- [ ] `make lint`; commit.

## Regression run

`make lint`; `make test`; `uv run pytest -m integration -n auto
tests/integration/test_update_process.py`; `openspec validate one-database-backup
--strict`; `openspec validate --specs --strict`; a trial archive in a scratch copy
(`openspec archive one-database-backup -y`, then `openspec validate --specs --strict`);
CI green (the full integration suite runs there).

## Tests per requirement

| Requirement (spec) | Layer | Tests |
|---|---|---|
| lado update keeps no copy of lado.db of its own (update-database) | unit; integration | `test_the_update_writes_and_removes_nothing_in_backups`, the reworked rollback tests' `backups/` asserts; Task 4's tests |
| The rollback restores the migration's copy | unit | `test_a_wrong_version_rolls_back_and_restores_lado_db_when_its_schema_moved`, `test_a_rollback_keeps_lado_db_when_its_schema_did_not_move`, `test_a_server_that_does_not_come_up_on_the_new_version_rolls_back` |
| A rollback without the migration's copy keeps the new version | unit | `test_a_rollback_without_the_migrations_copy_keeps_the_new_version` |
| An update to an older version learns its schema from its wheel | unit | Task 1's `release_schema` tests; Task 3's no-fetch tests |
| The plan of an update to an older schema says what it loses | unit; integration | Task 3's plan tests; Task 4's warning assert |
| An update to an older schema refuses when it cannot go back | unit; integration | Task 3's refusal tests; `test_update_to_an_older_schema_without_its_copy_stops_nothing` |
| An update to an older schema puts the copy back after the installer | unit; integration | Task 3's run test; `test_update_to_an_older_schema_restores_the_migrations_copy_and_the_old_lado_sees_its_session` |
| A failed way back to an older schema returns to the version before | unit | Task 3's restore-failure and server-failure tests |
| LADO backs lado.db up before it upgrades the schema (schema-migration, modified) | unit | the existing `state.migrate` tests (`The update's backup stays` scenario) |
| Moving onto a release candidate keeps the final's database (release-candidates) | unit | Task 5's `upgrade` tests |
| upgrade migrates lado.db before it keeps the copy (release-candidates, added) | unit | Task 5's `upgrade` test with no session running (the fake `lado ls` migrates) |
| rollback hands the copy to lado update (release-candidates, added) | unit | Task 5's `rollback` test: `backups/` holds the copy before the fake `lado update` runs |
| upgrade keeps the copy only when the release candidate is installed | unit | Task 5's existing not-installed and partial tests, reworked |
| rollback installs the final, restores lado.db and starts again what ran | unit | Task 5's `rollback` tests |

The real 0.42.0 is checked by the lead by hand (the design doc's Manual check) and at
0.43.0rc1 by release 4.4: no layer of `make check` downloads a real release.
