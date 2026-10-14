Task: LAD-58

## Why

The way from a task to its merge into `main` feels slow, and the checks around the merge
are suspected. LAD-58 asks where the time actually goes (CI, reviews, waiting for the
human, bringing `main` in) and what other projects do about it (merge queues, path
filters, fast required checks with slow ones run later, caches, sharding, a flake policy,
caps on review rounds), and wants recommendations for LADO with their gain and risk.

The analyst measured LADO's own history in the design step (11-14 October 2026: 156 CI
runs, 36 pull requests, 10 flow runs of LAD tasks); the human chose what to implement
(design dialogue). This change writes that up as a research report with a script that
measures it again. It builds nothing users get: implementation tasks are drafted at the
report's end and created in the tracker only on the human's separate yes.

## What Changes

- A new research report, `docs/research/merge-path.md` (English), with these sections in
  this order:
  1. **Summary**: the verdict in at most 15 lines: where the time goes, the recommendations
     taken and their expected gain.
  2. **How we merge today**: the CI workflow (jobs, what runs on a pull request and on
     `main`), the ruleset of `main` (required checks `check (3.10)`, `check (3.13)`, `js`,
     `ui`; no up-to-date requirement), and the steps of kit sdlc's flow `task` that wait
     for CI (review's stop criterion, the integrator's merge of `main` and its wait).
  3. **Measurements**: the tables of design.md's "Measurements" (CI wall time before and
     after LAD-41, per job and per step; CI runs and reruns per pull request; failures by
     job; time per flow state), each with the window, the sample size and the command that
     produced it.
  4. **What others do**: merge queues and the "not rocket science" rule, path filters and
     a single aggregate required check, fast required against slow post-merge or nightly
     checks, caching, test sharding, cancelling superseded runs, flake policies
     (quarantine, automatic retry), review round caps; each with a source link and
     whether it fits LADO.
  5. **Recommendations**: R1-R8 of design.md, each with what changes, the expected gain
     (from section 3), the risk, and the rule of AGENTS.md, docs/release.md or
     `.lado/sdlc.md` it changes, named explicitly; taken or not, and why.
  6. **Proposed tasks**: drafts A and B of design.md (title in Russian, what it does, size,
     dependencies), in the order to build them.
- A script, `docs/research/merge-path/measure.py` (standard library; `gh` and a copy of
  `lado.db` given by path), that prints section 3's tables for a window, so the gain can
  be measured again once the tasks land.
- A comment on LAD-58 in Russian with the summary and the proposed tasks.

## Scope

- Measurements of this repository's CI history (GitHub Actions API through `gh`), its
  pull requests, and the flow runs of LAD tasks in this machine's `lado.db`.
- Desk research of other projects' practices, with links.
- Recommendations as the human chose them: R1-R6 taken, R7 (merge queue) and R8 (caching,
  sharding the unit tests, review round caps) not taken, each with its reason.

## Out of scope

- Changing `ci.yml`, the ruleset of `main`, `.lado/sdlc.md`, AGENTS.md or kit sdlc: the
  drafted tasks A and B do it, the human's decision ("implementation in separate tasks").
- Removing or bypassing the gate `merge_ok`: half of a task's time is spent there, but it
  is the human's own review of what reaches `main` (the human's decision: keep it).
- A merge queue: R7, not now; the report names when to revisit it.
- Creating tracker tasks: only on the human's separate "yes, create" for the final list.

## Acceptance criteria

- AC-1: `docs/research/merge-path.md` exists, in English, with the six sections of What
  Changes in that order; its Summary names where the time goes and the recommendations
  taken.
- AC-2: Section 3 holds design.md's measurements, refreshed by `measure.py` for the window
  11-14 October 2026 (or a stated later window); each table names its window, sample and
  command, and the numbers agree with what the script prints.
- AC-3: Section 4 covers each practice listed in What Changes with at least one source
  link and a verdict for LADO.
- AC-4: Section 5 has R1-R8, each with gain, risk and the rule it changes named
  explicitly (AGENTS.md "Commands"/"Testing", docs/release.md, `.lado/sdlc.md`,
  `tests/test_ci_workflow.py`), and marked taken (R1-R6) or not taken (R7, R8) with the
  reason.
- AC-5: Section 6 has drafts A and B with size and dependencies; no tracker task is
  created without the human's "yes, create" for that list.
- AC-6: `python3 docs/research/merge-path/measure.py --help` runs with the standard
  library only; the script changes nothing on GitHub or in `lado.db` (read-only API calls,
  the database opened read-only).
- AC-7: LAD-58 has a Russian comment with the summary and the proposed tasks.
- AC-8: No token, personal path or e-mail is in the report, the script or the commits.

## Impact

- Docs only: `docs/research/merge-path.md` and `docs/research/merge-path/measure.py`
  (new). No code, API, schema, spec or CHANGELOG change: nothing users get, no version
  bump (neither minor nor patch).
