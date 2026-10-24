# LAD-141 doctor-older-schema: review report

Pull request #164 `hotfix/lad-141-doctor-older-schema` → `main`. Scale: hotfix, planned
for precision, widened to breadth in round 1 because the diff touches `runtime.py` (the
migration of user data) and `cli.py`. Head reviewed last: `a305270d` (= the remote head).
`runtime.py` changed (`migration_due`, shared with `migrate_if_safe`), so the human may
want live tests before the merge; `migrate_if_safe`'s behaviour is unchanged and its tests
are untouched. Schema migration: no.

## Rounds

- **Round 1** (local, breadth, `origin/main...6dc435fd`): spec, tests, silent failures,
  comments and docs, types, the architecture against AGENTS.md. One important finding (F1).
- **Round 2** (local, precision, `6dc435fd..a305270d`): F1 resolved, nothing new; the
  read-only `schema_version()`, the `tmux` import of `doctor.py`, `docs/cli.md` and the
  pull request description checked.
- **External 1 of 1** (Claude Code GitHub Action, request comment 6380953116, delta
  `8eeb850a..a305270d`, the whole pull request): "no requested changes", three minor
  (E1-E3). It read the diffs of every source file (`cli.py`, `doctor.py`, `runtime.py`,
  `state.py`); the tests only by grep, the documents and the openspec change not at all
  (checked locally). Reply with the decisions: comment 6380967832. The reviewer is of the
  same model family, so its "nothing found" weighs less.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | without tmux, on an older `lado.db` with a session not marked stopped, `check_database()` → `runtime.migration_due()` → `tmux.has_session()` raised `TmuxMissing` and `lado doctor` printed only the tmux error and exited 1, losing the whole report | confirmed | important | fixed in `a305270d`: `check_database` catches `tmux.TmuxError` and says the running sessions were not checked; test `test_without_tmux_the_doctor_still_reports_an_older_lado_db` |
| E1 | 2 | external 1 | in the no-tmux branch, a `lado.db` removed between `read_schema_refusal()` and `schema_version()` gives `schema None` | confirmed | minor | declined: a race in a diagnostic line, not reachable in practice |
| E2 | 2 | external 1 | the `?mode=ro` opening repeats in `read_schema_refusal`, `schema_version`, `pending_migration` | confirmed | minor | declined: the pattern predates the pull request; a refactor out of a hotfix's scope |
| E3 | 2 | external 1 | a read-only open of a WAL database may leave `-wal`/`-shm`; the docs could say so | confirmed | minor | declined: the promise is about `lado.db` itself, kept and tested; the side files are in `pending_migration`'s docstring |

## Checks

`make lint` green; `make test` 4247 passed, 2 skipped; `openspec validate
doctor-older-schema --strict` valid, `--specs --strict` 47 passed; integration
`tests/integration/test_agents.py` with `-m integration` 32 passed (round 1; round 2's
delta does not touch it, CI ran it); CI on `a305270d` 23/23, `ci-ok` pass.

## Not checked

The full `make test-integration` and the UI tests locally (excluded by the settings, CI
green); live tests; the external reviewer's reading of the tests and documents.

## Found on the way

None.
