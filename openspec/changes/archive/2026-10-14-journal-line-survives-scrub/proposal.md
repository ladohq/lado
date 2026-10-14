Task: LAD-53

## Why

Since change bug-report, `telemetry.record` (src/lado/telemetry.py) makes an exception's
scrubbed form (`scrub`) before it writes the exception's line to `errors.jsonl`, all inside
one `contextlib.suppress(Exception)`. When `scrub` raises, no line is written and nothing
says so: the error is lost silently, against "No silent drops". The sender's own failure
(`_journal_only`) has the same hole, as `_journal` without a scrubbed form calls `scrub`
itself. The defect came with 0.38.0, which is not released yet.

## What Changes

- A failing `scrub` no longer costs the journal line: the line is written without the
  scrubbed fields (`chain`, `stack`, `fingerprint`, `provider` left out), as LADO 0.37
  wrote it; the bug report already groups such a line by its type and `where` and shows it
  without frames. Nothing of that exception is queued: an unscrubbed error is never sent.
- The failure of `scrub` is itself recorded as an error of LADO at `where`
  `telemetry:scrub`: its own line with its own scrubbed form, and, while sending is on,
  queued as any error, so the maintainers learn about the broken scrub. One level only:
  when scrubbing that failure fails too, its line is written without the scrubbed fields
  and nothing more is recorded.
- The same for the sender's own failure (`_journal_only`): its line survives a failing
  `scrub`; it still queues nothing, and the scrub's failure there is journaled only.

## Scope

`src/lado/telemetry.py` (`record`, `_journal`, `_journal_only`), unit tests in
`tests/test_telemetry.py`, AGENTS.md (Layout) and docs/telemetry.md (the `where` row
names `telemetry:scrub`), the spec `error-journal`. No schema, CLI, API or UI change; no
new field is sent (only a new `where` value, `telemetry:scrub`, of the existing field).
Patch level; no CHANGELOG.md line, as the defect never shipped (0.38.0 is unreleased and
brought it).

## Out of scope

- Scrubbing field by field, keeping what each part gives (the human chose against it):
  half-filled lines and a fingerprint of a partial stack, and the scrub's failure still
  silent.
- Counting the unqueued error in `dropped`: `dropped` means a full outbox; the
  `telemetry:scrub` error already tells the maintainers.

## Impact

- `src/lado/telemetry.py`, `tests/test_telemetry.py`, AGENTS.md, docs/telemetry.md.
- Spec `error-journal`: the requirement "Every LADO process writes its unexpected
  exceptions to one journal" says the line survives a failing scrub and the scrub's
  failure is an error of its own.
