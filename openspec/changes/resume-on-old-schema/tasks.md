## 1. A resume is queued on a database from before 0.7.0

- [x] 1.1 `tests/test_state.py` (unit: one insert against one schema, no process
  crossed): a test that writes `SCHEMA_V1` into a fresh `LADO_HOME`, runs
  `state.migrate()`, makes the agent `w1` of session `s` busy, adds a `TURN_ERROR` event,
  `schedule_resume`, sets it idle and calls `take_resume` once the resume is due: it
  returns a message id, the message is `lado`'s, pending, with its summary and body `''`,
  and the agent's `resume_at` is None. Red before 1.2 with `NOT NULL constraint failed:
  messages.body`.
- [x] 1.2 `src/lado/state.py`, `take_resume`: the insert names `body` and passes `''`.
  1.1 passes.
- [x] 1.3 `tests/test_state.py`: a guard test that reads `src/lado/state.py` and finds
  every `INSERT INTO messages (` column list (the string literals joined, as the code
  writes them over several lines), asserts there is at least one, and that each names
  `body`; its docstring says why (databases from before 0.7.0 have `messages.body`
  without DEFAULT). Red before 1.2.

## 2. Documents

- [x] 2.1 CHANGELOG.md, `## 0.43.0 (unreleased)` → `### Fixed`: a bold-titled line (at
  most three lines, the user's words) that an agent whose turn ended on a temporary API
  error is resumed again on a LADO home made before 0.7.0, and the session loop no
  longer stalls on it.
- [x] 2.2 docs/release.md, 4.3, the item "Projects' secrets on the Mac": the recipe
  reads `LADO_HOME=$(mktemp -d) LADO_REPOS=$(mktemp -d) LADO_TELEMETRY=0`, with a short
  reason (without `LADO_REPOS` `lado` refuses when your own workspace's `projects/`
  holds a project).
- [x] 2.3 BACKLOG.md, the entry "Agents may be asked to read kit files outside their
  allowed folders": a line that 0.43.0rc2 confirmed it live (2026-10-26: a developer of
  kit sdlc 0.7.0 on Claude Code in mode default stopped on a permission dialog for
  `review-loop/references/lenses.md`, reached through the skill's link into
  `~/.lado/cache`), and "Wanted" no longer asks for the live check, only for the fix.
- [x] 2.4 BACKLOG.md, P1, a new entry by the file's template (`Size:`, `Why here:`,
  `Found:` 2026-10-26, manual check of 0.43.0rc2, LAD-156): "One failing step of the
  session loop's sweep stops the whole session's pass": an exception in `runtime.sweep`
  for one agent (as `take_resume` raised) ends the pass, so no agent of the session gets
  its unconfirmed messages retried or its queue handed over until the cause goes, and the
  UI shows nothing; wanted: each agent's steps guarded, the error journaled and the pass
  going on, with an integration test. The human's decision #1760.

## 3. Regression

- [x] 3.1 `make lint`, `make test`, `openspec validate resume-on-old-schema --strict`,
  `openspec validate --specs --strict`; the pull request's CI.
