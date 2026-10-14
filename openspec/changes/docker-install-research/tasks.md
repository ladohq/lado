## 1. Prototype

- [x] 1.1 Write the prototype's Dockerfile and compose file under
  `docs/research/docker-install/` (design D2-D5). Check: the image builds for
  linux/arm64.
- [x] 1.2 Run H1 and H2 (doctor, the UI from the host's browser, a session from the New
  session window, an agent's terminal). Check: results with evidence in a draft of
  section 4.
- [x] 1.3 Run H5-H8 (local model, worker on the bind mount, restart and recreate, push
  with the host's ssh agent on a scratch repository). Check: as 1.2.
- [x] 1.4 Ask the human once, with exact steps, for the Claude Code and Codex logins; run
  H3 and H4. Check: as 1.2; the volumes with logins removed after the run. H4 is
  `not checked`: the human has no ChatGPT/Codex subscription (described from
  documentation).
- [x] 1.5 Run H9 (mise in the home volume, the agents' `PATH`, after a recreation) on a
  fresh volume without logins. Check: as 1.2; the volume removed after the run.

## 2. Report

- [x] 2.1 Write `docs/research/docker-install.md` with the eight sections of the
  proposal (AC-1-AC-5), each claim with its source. Check: by reading against AC-1-AC-5.
- [x] 2.2 Redact the evidence and the prototype files (AC-7). Check: `git diff
  origin/main --stat` and a grep for tokens, e-mails and `/Users/`.
- [x] 2.3 `openspec validate docker-install-research --strict` and `make lint` pass.
- [x] 2.4 Revise the report by the human's list after reading it (the run's artifact
  `report-changes`): the verdict, first start and models, toolchains, file ownership,
  publishing, the agents' versions, isolation levels, section 8, the reviewer's minor
  notes. Check: each item of the list against the diff; 2.2 and 2.3 again.

## 3. Tracker

- [x] 3.1 Post a Russian comment on LAD-52 with the summary and the proposed tasks
  (AC-6); create no task. Check: the comment by its id in the task.
- [x] 3.2 Post a new Russian comment on LAD-52 with the revised summary and tasks (2.4).
  Check: as 3.1.
