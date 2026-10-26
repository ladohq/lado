Task: LAD-156

## Why

Symptom: after a temporary API error (`turn_error`, e.g. `server_error` when DNS was
gone) LADO plans the agent's resume (`agents.resume_at`) and it never comes: the run
stands, the UI shows nothing and the supervisor is not told. `~/.lado/loop.log` has, on
every pass of the session loop, `sqlite3.IntegrityError: NOT NULL constraint failed:
messages.body` from `state.take_resume`, and once a minute `the same error again, 30
times`. Found at the manual check of 0.43.0rc2, 2026-10-26 (report finding N-1); not a
regression of 0.43: auto-resume (0.25.0) never worked on such databases.

Cause: `take_resume` is the one insert into `messages` that leaves `body` to its
DEFAULT. A database made by this LADO declares `body TEXT NOT NULL DEFAULT ''`. One made
before LADO 0.7.0 (schema below 5) had `text TEXT NOT NULL` with no DEFAULT, which
migration 4 renamed to `body`; SQLite cannot add a DEFAULT to an existing column, so it
has none to this day. Checked by replaying history: a database made by 0.1.0 and
migrated by every release's own code up to 0.43.0rc2 differs from a new one in that one
column alone, and every other insert into `messages` names `body`. The exception also
ends the whole `runtime.sweep` pass for the session: while `resume_at` stays due, no
agent of the session gets its unconfirmed messages retried or its queue handed over by
the loop.

Options weighed:

- A (taken): `take_resume` inserts `body` `''` itself, and a unit test holds every insert
  into `messages` to naming `body`. One line of code, no schema change, safe to go back
  to 0.42.0. Long-term cost: the old databases keep a column without DEFAULT, so the
  rule lives in a test instead of the schema.
- B: a migration that rebuilds `messages` with the DEFAULT (create, copy, drop, rename,
  with its indexes and the journal's triggers). The schema would then be one again, but
  it is a schema migration (a minor bump, not allowed while main is frozen for the RC),
  touches the largest table of every user's database, and the way back to 0.42.0 would
  need the backup.
- C: A now and B later: B's cost stays for no behaviour gained, as long as the test of A
  holds.

## What Changes

- `src/lado/state.py`: `take_resume` names `body` with `''` in its insert.
- Unit tests in `tests/test_state.py`: a schema-1 database (`SCHEMA_V1`) migrated to the
  current schema queues a due resume (red before the fix); every `INSERT INTO messages`
  in `state.py` names `body`.
- CHANGELOG.md, `## 0.43.0 (unreleased)` → Fixed: a line that an agent whose turn ended on
  a temporary API error is resumed again on a database from before 0.7.0, and the session
  loop no longer stops on it.
- docs/release.md, 4.3, the check of projects' secrets on the Mac: the recipe sets
  `LADO_REPOS=$(mktemp -d)` too (without it `lado` refuses when the checker's own
  `~/workspace/projects` holds a project). The human's decision #1755.
- BACKLOG.md: the entry "Agents may be asked to read kit files outside their allowed
  folders" notes that 0.43.0rc2 confirmed it live (a developer of kit sdlc 0.7.0 on Claude
  Code in mode default stopped on a dialog for `review-loop/references/lenses.md`,
  reached through its link into `~/.lado/cache`). The human's decision #1755.
- Patch-level: a fix inside 0.43.0 (unreleased), no schema change, no version bump.

## Scope

- The insert of `take_resume`, the guard test over all inserts into `messages`, the
  checklist line of 4.3 and the BACKLOG note.

## Out of scope

- Rebuilding `messages` to give old databases the DEFAULT (option B): a schema migration
  during the RC freeze, for nothing a user sees once A is in.
- Keeping one failing step of `runtime.sweep` from ending the session's whole pass: a
  change of the session loop's behaviour that needs its own design and integration test,
  not an RC fix; recorded in BACKLOG.md instead (see tasks).
- The other findings of the rc2 report (N-0 Safari, N-2 by-hand way back, N-3 and N-4
  Codex in the image): their own tasks.
- A live or integration test of auto-resume on an old database: the defect is one SQL
  insert against one schema, which the unit layer catches; the loop's path to
  `take_resume` is covered by the existing tests.
