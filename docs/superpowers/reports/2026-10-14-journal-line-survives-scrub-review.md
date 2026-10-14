# LAD-53 journal-line-survives-scrub: review report

Pull request #36 `fix/lad-53-journal-line-survives-scrub` → `main`. Scale: tweak, patch
(the defect came with 0.38.0, unreleased, so no CHANGELOG.md line), review depth
precision. Head reviewed last: `966f82d` (= the remote head); the archive commit follows
it. Diff `e731308..966f82d`: 7 files, +254/−18. No API, MCP, CLI or schema change;
`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/`
are untouched.

## Rounds

- **Round 1** (`e731308..966f82d`, the whole pull request): local precision pass over the
  diff, the spec and the architecture. External round 1 by the Claude Code Action (request
  at 10:21:19 UTC, "Claude finished" at 10:21:37 UTC): no blocker, no important finding.
  The external round cap for a tweak (1) is used.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| E1 | 1 | external | a scrub that always fails queues one `telemetry:scrub` event per error | refuted | — | as designed (option 2, the human's choice); the outbox is bounded by `OUTBOX_MAX` with `dropped`, and the sender groups by fingerprint (`_groups`, one `$exception` per kind) |
| E2 | 1 | external | "Once" in `_scrubbed`'s docstring reads ambiguously, "One level" is clearer | confirmed | minor | declined: the sentence goes on to say what it means; no other fix to ride with |

| Source | Confirmed | Refuted |
|---|---|---|
| local | 0 | 0 |
| external, Claude Code Action | 1 (E2) | 1 (E1) |

## Spec check

- "Every LADO process writes its unexpected exceptions to one journal" (modified):
  "The scrub fails" by `test_a_failing_scrub_keeps_the_line_and_is_an_error_of_its_own`,
  "The scrub fails on its own failure too" by
  `test_a_scrub_that_always_fails_leaves_two_bare_lines`; the sender's own failure by
  `test_the_sender_s_own_failure_survives_a_failing_scrub`; the bug report's reading of
  such a line by `test_a_line_without_its_scrub_reads_as_a_kind_without_frames`.
- `_journal` never calls `scrub` itself (its callers: `record`, `_scrubbed`,
  `_journal_only`), so no recursion by construction; only a scrubbed form is queued, and
  `_journal_only` queues nothing.
- AGENTS.md (Layout `telemetry.py`) and docs/telemetry.md (the `where` row) name
  `telemetry:scrub` and the line without its scrub. Every task of `tasks.md` checked;
  nothing beyond the scope.

## Checks

- Reviewer on `966f82d`: `make lint` clean; `tests/test_telemetry.py`,
  `tests/test_error_journal.py`, `tests/test_bug_report.py` 105 passed; the 6 new cases
  fail on `telemetry.py` of `origin/main` (the tests can fail); `openspec validate
  journal-line-survives-scrub --strict` passed.
- Developer: `make test` 2932 passed.
- CI on `966f82d` green: check (3.10, 3.13), js, ui, smoke × 8.

## Found on the way

None.

## Not checked

- The full `make test` locally by the reviewer (CI ran unit and integration on both
  Pythons).
- A real failing `scrub` in a live process: only replaced in unit tests, as designed.
- The order of the two lines (`telemetry:scrub` first) is not in the spec; the tests fix
  it.
