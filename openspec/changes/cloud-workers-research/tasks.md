## 1. Reports

- [x] 1.1 Write `docs/research/cloud-workers/r1-lado-coupling.md`, `r2-prior-art.md`,
  `r3-cloud-survey.md`, `r4-credentials.md` by moving them from the change's `inputs/`
  (`git mv`), unchanged (design D3, D8). Check: `grep -nE '/Users/|/tmp/|/private/|scratchpad'`
  over the folder finds nothing.

## 2. Report and plan

- [x] 2.1 Write `docs/research/cloud-workers.md` with the seven sections of the proposal,
  translated from `inputs/lad-100-research.md` (sections 1-5, 7). Check: by reading against AC-1.
- [x] 2.2 Write `docs/research/cloud-workers-plan.md` with the five sections of the
  proposal: the decisions of 2026-10-18, step 0 and stages A-E from the summary's
  section 6, the technical details from R1 sections 2-6 and R4 sections 1.1-1.4, 2.6,
  3 and 4.4 (design D4), risks and open questions. Check: by reading against AC-2.
- [x] 2.3 Add the line to `ROADMAP.md` under "Later (after stage 7)" (AC-5).
- [x] 2.4 Check AC-4 and AC-7: a grep of `git diff origin/main` for the reference
  projects' names and nicknames (from the supervisor) and for `r5`; every
  relative link of the new files resolves (a short script or by hand).
  `openspec validate cloud-workers-research --strict` and `make lint` pass.
- [x] 2.5 Delete `openspec/changes/cloud-workers-research/inputs/` (its content is now in
  `docs/research/`). Check: `git status` shows the folder gone; 2.4 again.

## 3. Tracker

- [ ] 3.1 After the pull request is open, post a Russian comment on LAD-100 with the short
  result, the files and the pull request's link (AC-6); create no task. Check: the
  comment by its id in the task.
