# Usage stats: design

Task: LAD-34. Change: `openspec/changes/usage-stats/` (proposal, deltas `usage-stats` and
`usage-telemetry`, `design.md` D1-D11).

## Problem

What a human did with LADO is in `lado.db`, but only the telemetry sender counts a part of
it (`state.usage_counts`), only for the maintainers, and `lado forget` deletes the rows it
counts, so every count of the past shrinks with each forget.

## What the user sees

- `lado stats` prints the counts of the last 30 days on this machine (`--days N`,
  `--all`): sessions started and resumed; agents started per CLI and per role, agents that
  ended by themselves, turns that ended on an error per CLI and error kind; flow runs
  started per flow, ended, cancelled; gates opened per kind, closed per answer, how often
  the answer was the lead's recommended one; questions agents asked; messages that failed
  to be delivered or were dropped; LADO's own errors. The first line names the period in
  UTC and says nothing is sent; the earliest record is named when the history is shorter.
- Nothing goes to the network, and the command starts no statistics sender.
- The counts survive `lado forget`: each counted fact is recorded as it happens in a
  local, anonymous table (kind, a short key such as a role or flow, the CLI, the time). At
  the upgrade the table is filled from what `lado.db` still holds.
- The telemetry report has the same fields and asks nothing new; its numbers now also
  count forgotten sessions.

The output: `design.md` D7.

## Options

| Option | Long-term cost | Verdict |
|---|---|---|
| Count what is left; say forgotten sessions are missing | totals fall with each forget | refused |
| Copy the counted rows at forget | forget must know every count; another cleanup loses them | first design, replaced |
| Record each fact as it happens, by trigger, backfilled at the upgrade | a schema step; a new count is a trigger migration | **chosen** |
| Counters incremented in code | ten places to keep in step | refused |

## The counts, chosen with the human

Taken: sessions (started, resumed), agents (per CLI and role), agents ended by
themselves, turn errors (per CLI and kind), flow runs (started per flow, ended,
cancelled), gates (opened, closed, agreement with the lead), questions to the human,
failed and dropped messages, LADO's errors.

Left for later: durations (session time, agents' busy time, run time, the human's
waiting time) and rework, which need totals at a session's end and a definition; the
human's own messages, automatic resumes and read-only repository changes (little use);
a per-session view; new telemetry fields.

## Architecture

- `state.py`: `usage` (schema 27), `USAGE_KINDS`, `USAGE_TRIGGERS`, the backfill
  `usage_from_history`, `usage_counts` from `usage`, `usage_summary`, `usage_start`.
- `stats.py` (new): the period and the lines.
- `telemetry.py`: `lado_errors`, renamed from `_lado_errors`.
- `cli.py`: the parser, `cmd_stats`, and `stats` among the commands that do not kick.

## Release

A minor release, 0.38.0: a CLI command and a schema migration. CHANGELOG.md's heading
`0.37.1 (unreleased)` becomes `0.38.0 (unreleased)`.

## Questions settled with the human

1. Forget: the counts must survive it (round 1), recorded as facts happen (round 3, the
   human's idea, with triggers and a backfill).
2. Period: 30 days by default, `--days N`, `--all`, the earliest record named.
3. Counts: the list above (round 4, as the lead recommended); durations and rework later.
4. No per-session view; the telemetry report's fields unchanged.
5. UI: none in this task. Format: text only, no `--json`.
6. The migration's risk was asked about and answered (`design.md`, Risks).
