## 1. Measurements

- [x] 1.1 Write `docs/research/merge-path/measure.py` (design D2): CI wall time by
  period, per job and per step; CI runs and reruns per pull request; failed jobs and
  steps by attempt; opening to merge per pull request; time per flow state from a
  read-only copy of `lado.db`. Check: `python3 docs/research/merge-path/measure.py
  --help` runs; a grep of the script shows no `gh api` call with `-X`/`--method` other
  than GET and the database opened with `mode=ro` (AC-6).
- [x] 1.2 Run it for 11-14 October 2026 with `--split 2026-10-13T16:00:00Z` and a copy of
  `~/.lado/lado.db`. Check: its tables against design.md's "Measurements"; each
  difference noted for the report (D3).

## 2. Report

- [x] 2.1 Write `docs/research/merge-path.md` with the six sections of the proposal
  (AC-1-AC-5): the measurements from 1.2, the practices with source links, R1-R8 with
  gain, risk and the rule each changes, drafts A and B. Check: by reading against
  AC-1-AC-5.
- [x] 2.2 Redact (AC-8). Check: `git diff origin/main --stat` and a grep of the new files
  for tokens, e-mails and `/Users/`.
- [x] 2.3 `openspec validate merge-path-research --strict` and `make lint` pass.

## 3. Tracker

- [ ] 3.1 Post a Russian comment on LAD-58 with the summary and the proposed tasks
  (AC-7). Check: the comment by its id in the task.
- [ ] 3.2 Ask the human once for "yes, create" on tasks A and B as drafted; create them
  only on that yes, each with the label `component lado`, linked to LAD-58 as `derived`
  (D5). Check: each new task by its key; when the human says no, the ledger says so and
  nothing is created.
