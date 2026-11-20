# LAD-305 session-screens-test-waits-for-the-feed: review report

Pull request #347 `hotfix/lad-305-session-screens-feed-wait` → `main`. Scale: hotfix, review
depth: precision. Head reviewed: `47bc3a8d`. `test_the_session_screens_changed_hold_at_every_width`
goes to each of its four pages through a new helper `goto_live` (`tests/ui/test_main_screen.py`),
which waits up to 15 s for the banner's status `live` and records the browser's requests of
`/api/events`: a timeout fails with that record, a `live` later than 2 s passes and leaves it as
a `UserWarning`. Tests and docs only: no `src/`, `web/`, schema or API change, no CHANGELOG.md
line, no delta.

## Rounds

1. Local, precision and a check against the design, `8a2c8e99..47bc3a8d`. External 1, Claude
   Code GitHub Action: no blockers, three minor findings (F2–F4); every risky file read, the
   openspec files not read (checked by the reviewer with `openspec validate --strict`).

External rounds used: 1 of 1. Stand-ins: 0.

## The human's decisions

- **Gate `design_ok`, returned once**: a `live` later than about 2 s on a passing test must
  leave the same record in the CI log (D4, a `UserWarning`, AC-3).
- **Gate `merge_ok`, approved** with no comment.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | local: on a refused stream the timeout's message reads `status: ` with an empty word | declined: the shell leaves the status empty on purpose (`web/src/Shell.tsx:315`); the record's `answered 401/503` line names the refusal |
| F2 | minor | external: `status.inner_text()` in the `except` branch may wait 30 s if the element goes between `count()` and the read | declined: only on a path that already fails, in a narrow race; the status is on every page from the first render (`Shell.tsx:324`); `text_content(timeout=1000)` at the helper's next edit |
| F3 | — | external: the time `took` includes the page's load | refuted: by D4 the time counts from the `goto` ("after going to"); the `sent at` / `answered at` lines tell the load from the stream |
| F4 | minor | external: matching requests by `is` deserves a comment | declined: readability only; Playwright's Python wrapper gives one object per request, and the developer's manual run showed `answered` lines |

## Checked against the code

- AC-1, D1: the locator `banner → status` is the banner's one `role="status"`, the same as in
  `test_connection.py`; `to_have_text("live")` matches exactly, 15 s.
- AC-2, AC-3: manual runs with the stream blocked and delayed 3 s by the developer in an
  uncommitted copy; the reviewer checked with a probe under `-n 2` (as CI runs the UI tests,
  `ci.yml:182`) that xdist carries the `UserWarning` to the warnings summary. The project sets
  no `filterwarnings = error`.
- Every task of `tasks.md` checked; nothing out of scope done.

## Checks

| Check | Result |
|---|---|
| `make lint` | exit 0 |
| `openspec validate session-screens-test-waits-for-the-feed --strict` | valid |
| CI run 44692348034 on `47bc3a8d` | green: `ci-ok`, unit, integration (6 shards), ui (4), container (4), web; smoke skipped by CI's skip list |
| The UI shards' logs | no "stream opened" warning: the stream did not stall |

## Metrics

Rounds: local 1, external 1, stand-ins 0. Confirmed: local 1, external 2, all minor. Refuted:
external 1 (F3). Findings in code changed by the developer's clean-up: 0.

## Found on the way

Nothing.

## Not verified (residual risk)

- The manual runs of AC-2 and AC-3 were done by the developer only.
- The stall's cause is not found, by design: the helper records the next occurrence.
- Live and smoke tests were not run: the change does not touch them.

No change in `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
`tests/live/`.
