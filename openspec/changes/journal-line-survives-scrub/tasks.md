## 1. The line survives a failing scrub

- [ ] 1.1 Unit tests first (`tests/test_telemetry.py`, layer 1: pure logic in process),
  with `telemetry.scrub` replaced by one that raises for the original exception only
  (`monkeypatch`), red before the fix:
  - `record` with sending off: the original's line is there without `chain`, `stack`,
    `fingerprint`, `provider` and with its time, version, `where`, type, message,
    traceback, session and agent; a second line `where` `telemetry:scrub` with its own
    scrubbed form; nothing queued;
  - `record` with sending on (`telemetry_on`): the outbox holds exactly one event, the
    `telemetry:scrub` one, none of the original;
  - a scrub that raises for every exception: two lines, neither with the scrubbed fields,
    nothing queued, `record` does not raise and does not recurse;
  - `_journal_only` with a raising scrub: its line without the scrubbed fields, the
    `telemetry:scrub` line, nothing queued even with sending on;
  - a line without the scrubbed fields reads in `bug_report.build` as a kind with no frames
    (the existing 0.37 rule, checked once on a line `record` wrote).
- [ ] 1.2 `telemetry.py`: one helper that scrubs or, on an exception, journals the scrub's
  failure at `telemetry:scrub` (queueing it only when the caller may queue) and gives None;
  `_journal` takes a scrubbed form or None and leaves the four fields out for None (never
  calls `scrub` itself); `record` queues only a scrubbed form; `_journal_only` uses the
  helper without queueing. Docstrings say so. `make lint`, `make test`.
- [ ] 1.3 AGENTS.md, Layout `telemetry.py`: the line survives a failing scrub, and the
  scrub's failure is recorded at `telemetry:scrub`; docs/telemetry.md, the `where` row:
  "or LADO's own scrubbing of an error (`telemetry:scrub`)". `openspec validate
  journal-line-survives-scrub --strict`.
