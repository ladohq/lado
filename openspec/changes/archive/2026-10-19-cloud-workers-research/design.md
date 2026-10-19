## Context

LAD-100 is research: how LADO can run agents in a cloud without lock-in, with any agent
CLI, as an option next to the local mode. The research ran in the design dialogue of
LAD-100 as five reports (session artifacts `r1-lado-coupling`, `r2-prior-art`,
`r3-cloud-survey`, `r4-credentials`, `r5-references`) and a Russian summary with a staged
plan (`lad-100-research`), which the human approved on 2026-10-18. The human's words:
save the plan with its technical details and the intermediate results ("they may be
useful later"), documentation only. The precedent is LAD-52: `docker-install.md`, the
living `docker-install-plan.md` and the folder `docker-install/` of evidence.

## Decisions

- D1. Two documents, not one: `cloud-workers.md` is the research report and stays as
  written; `cloud-workers-plan.md` is the living plan, updated after each step (status of
  each step, decisions taken). This follows `docker-install.md` /
  `docker-install-plan.md`, so a plan update never rewrites the research.
- D2. The intermediate reports keep their artifact names as file names
  (`r1-lado-coupling.md` ...), so the summary's and the plan's references "R1"..."R4" stay
  recognisable; they sit in `docs/research/cloud-workers/` beside the report, as
  `docker-install/` holds its evidence.
- D3. The reports are kept as written, not rewritten: they are evidence with dated
  sources. Only local paths are removed (R1's first paragraph names the machine's
  checkout: it becomes "the repository root"). The code references of R1 stay as they
  are, pinned to the commit it names (033705e); the plan's coupling table names that
  commit too, so a reader knows the line numbers may have moved.
- D4. The plan carries the technical details itself (coupling table, backend interface
  sketch, node protocol, launch bundle, git options, credentials constraints), condensed
  from R1 and R4 with a pointer to the section of origin, so the next task's analyst
  starts from the plan and opens a report only for evidence.
- D5. `r5-references` is not committed and nothing names its subjects (public
  repository); where the summary drew on it, the plan states the reasoning as LADO's own.
  The check is a grep of the diff for the reference projects' names and nicknames (the
  developer gets them from the supervisor, never into any file).
- D6. No delta spec: no behaviour rule changes; archived with `--skip-specs`, as
  `docker-install-research` was.
- D7. No CHANGELOG line and no version bump: research documents are not something users
  see, as with LAD-52 and LAD-58.
- D8. The session's artifacts are committed as files under the change's `inputs/`
  (temporary), because the human continues in another LADO installation whose
  `LADO_HOME` does not hold them. They sit inside the change, not in `docs/`, so they are
  clearly sources for the build, and the build deletes the folder when it is done. Before
  the commit the two private traces were removed (the summary's line on `r5-references`,
  R1's local path); `r5-references` and every artifact are also kept outside the
  repository, in a private folder of the human's home.
