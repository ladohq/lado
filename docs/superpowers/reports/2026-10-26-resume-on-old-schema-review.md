# LAD-156 resume-on-old-schema: review report

Pull request #175 `hotfix/lad-156-resume-on-old-schema` → `main`. Scale: hotfix, reviewed
for precision (one SQL insert and its tests; no table changes, `body` gets the same `''`
a new database's DEFAULT gives). Head reviewed last: `a36319b5` (= the remote head).
`state.take_resume` now names `body` in its insert, so a due resume is queued on a
database made before LADO 0.7.0, whose `messages.body` has no DEFAULT; a guard test holds
every insert into `messages` in `state.py` to naming `body`. CHANGELOG (Fixed),
docs/release.md 4.3 (`LADO_REPOS=$(mktemp -d)`), two BACKLOG entries. `providers/`,
`hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` unchanged: no
live tests needed. Schema migration: no.

## Rounds

- **Round 1** (`origin/main...a36319b5`): a local precision pass over the whole diff
  (code, tests, documents, the openspec change). **External 1** (Claude Code GitHub
  Action, request at 08:54:24Z, "Claude finished" at 08:55:15Z): read `state.py`,
  `test_state.py`, `CHANGELOG.md` and `docs/release.md`, every risky file; not
  `BACKLOG.md` nor the openspec texts (the local pass checked them). No blocker, no
  important finding; one minor.

External rounds used: 1 of 1. The external reviewer is of the same model family, so its
"nothing blocking" weighs less.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | external 1, matching a local note | the guard test's pattern sees only `INSERT INTO messages (`: an insert without a column list, `INSERT OR … INTO messages` or SQL outside `state.py` escapes it | confirmed | minor | declined: all six inserts into `messages` in `src/` are in `state.py` and of that form today |

## Checked against the spec

The requirement "An upgraded lado.db takes every write a new one takes": the scenario "A
resume on a database from before 0.7.0" by
`test_a_due_resume_is_queued_on_a_database_from_before_0_7` (schema 1, `migrate()`,
`take_resume`: `lado`'s message, pending, its summary, body `''`, `resume_at` dropped);
"Every message insert names its body" by the guard test. The root cause checked on its
own: a `SCHEMA_V1` database migrated by the current code differs from a new one, by
`pragma table_info` of every table, only in `messages.body` without DEFAULT, so no other
insert leans on a missing DEFAULT. The guard can fail: on `origin/main`'s `state.py` it
finds six inserts, one (`take_resume`'s) without `body`. Every task of `tasks.md`
checked; nothing out of scope.

## Checks

`make lint` exit 0; `uv run pytest -n0 tests/test_state.py -k "before_0_7 or
names_its_body or resume"` 18 passed (the developer's `make test`: 4313 passed, 2
skipped); `openspec validate resume-on-old-schema --strict` valid; CI on `a36319b5` 23 of
23 pass, `ci-ok` included.

## Not checked

Integration, UI and smoke tests were not run locally (CI ran them on this head). No live
check of auto-resume on a real old database: by design, the unit layer catches the
defect.
