# Usage stats: design

Task: LAD-34. Change: `openspec/changes/usage-stats/` (proposal, deltas `usage-stats` and
`usage-telemetry`, `design.md` D1-D9).

## Problem

What a human did with LADO is in `lado.db`, but only the telemetry sender counts it
(`state.usage_counts`), and only for the maintainers. And `lado forget` deletes a
session's events, so every count of the past, the sender's too, shrinks with each forget.

## What the user sees

- `lado stats` prints the counts of the last 30 days: sessions started or resumed, agents
  spawned per agent CLI, flow runs started, gates opened, turns ended on an error and
  LADO's own errors. `--days N` takes another period, `--all` everything kept. The first
  line names the period in UTC and says nothing is sent. A second line names the earliest
  record when the history is shorter than the period (and always with `--all`).
- Nothing goes to the network: the command reads `lado.db` and `errors.jsonl`, and it does
  not start the statistics sender as other commands do.
- After `lado forget` the counts stay the same: the forget keeps one anonymous row per
  counted record (kind, agent CLI, time). Sessions forgotten before 0.38.0 are not
  counted. The daily telemetry report counts the same way, with the same fields.

```
$ lado stats
Usage from 2026-09-14 to 2026-10-14 (UTC, 30 days) on this machine; nothing is sent.
Earliest record: 2026-10-01.
  sessions started or resumed   12
  agents spawned                41  (claude 30, codex 8, kilo 3)
  flow runs started              9
  gates opened                  17
  turns ended on an error        4
  LADO's own errors              2  (errors.jsonl keeps only its latest part)
```

## Options

| Option | Long-term cost | Verdict |
|---|---|---|
| Count what is left; say forgotten sessions are missing | none now; totals fall with each forget, the report is short too | refused with the human |
| Keep an anonymous copy of the counted records at forget | one table, one schema step, a few rows per forgotten session; a new count adds its kind to one list | **chosen** |
| Counters incremented at each event | a second source of truth that drifts from `events` | refused |

## Architecture

- `state.py`: `forgotten_usage` (schema 27), `USAGE_KINDS`, the copy in `delete_session`,
  `usage_counts` over both tables, `usage_start`.
- `stats.py` (new): the period and the lines.
- `telemetry.py`: `lado_errors`, renamed from `_lado_errors`.
- `cli.py`: the parser, `cmd_stats`, and `stats` among the commands that do not kick.

## Release

A minor release, 0.38.0: a CLI command and a schema migration. CHANGELOG.md's heading
`0.37.1 (unreleased)` becomes `0.38.0 (unreleased)`.

## Questions settled with the human

1. Forget: keep an anonymous copy (option 2).
2. Period: 30 days by default, `--days N`, `--all`, and the earliest record named.
3. Counts: exactly the daily report's, plus LADO's own errors with the journal's bound.
4. UI: none in this task.
5. Format: text only, no `--json`.
