## 1. Measurement

- [x] 1.1 Write `docs/research/ci-speedup-check/measure.py` (standard library, `gh`
  read-only) printing points 1-8 of the proposal for a window `--since`/`--until`, with
  the definitions of design D2-D7. Check: `python3 docs/research/ci-speedup-check/measure.py
  --help` runs; a grep shows no `gh api` with `-X`/`--method` other than GET (AC-1);
  `make lint` passes.
- [x] 1.2 Run it for "before" (2026-11-05T21:00Z..2026-11-09T12:30Z) and "after"
  (2026-11-09T12:30Z..2026-11-13T00:00Z), and read the cache usage and list. Check: each
  table's sample size; "before" against the baseline artifacts `ci-analysis` and
  `ci-external`, each difference noted with its cause (AC-2).

## 2. Report

- [x] 2.1 Write `docs/research/ci-speedup-check.md` (English): summary; what changed in CI
  and when (LAD-248, LAD-249, Team, LAD-236 and the later changes of design "Context");
  the before/after table of points 1-8 with windows, samples and commands; the four
  conclusions; the critical path after the change; proposed tasks (AC-2-AC-4). Check: by
  reading against AC-2-AC-4.
- [x] 2.2 For each flaky test of the window "after", search the tracker for an open task;
  name it, or draft a new task (D7). Check: the report's list against the search results.
- [x] 2.3 Redact (AC-7). Check: a grep of the new files and `git log -p origin/main..` for
  tokens, e-mails and `/Users/`.
- [x] 2.4 `openspec validate ci-speedup-check --strict` and `make lint` pass.

## 3. Artifact and tracker

- [x] 3.1 Write the run's artifact `ci-report`: the report in Russian (AC-5). Check: the
  artifact exists and its numbers match the report.
- [x] 3.2 Post a Russian comment on LAD-252 with the before/after table, the conclusions
  and the proposed tasks (AC-5). Check: the comment by its id in the task.
- [x] 3.3 Ask the human once (`ask_human`, the drafts in its details) for "yes, create" on
  the proposed tasks; create only those, each with the label `component lado`, linked to
  LAD-252 as `derived` (AC-6). Check: each new task by its key; with a "no", the build
  report says so and nothing is created.
