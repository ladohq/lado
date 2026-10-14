# LAD-52 docker-install-research: review report

Pull request #33 `fix/lad-52-docker-research` → `main`. Scale: tweak, precision review.
Docs only: the research report `docs/research/docker-install.md`, the prototype's
Dockerfile and compose file, two screenshots, the openspec change and a BACKLOG.md entry;
no version bump and no CHANGELOG line. Head reviewed last: `75f3ff8` (= the remote head);
the archive commit follows it. `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
`agent_env.py` and `tests/live/` did not change, so live tests are not needed before the
merge. As the report is research, each of its claims about LADO was checked against the
code (AC-3). After reading the report the human asked for a revision (the run's artifact
`report-changes`): its verdict is now "Docker as the main way in".

## Rounds

- **Round 1** (local, `origin/main..41584b0`): F1, F2 important; F3, F4 minor.
- **Round 2** (local, `41584b0..059f8f0`, and external round 1 of 1 by the Claude Code
  Action, comment 6163796151): F1-F4 resolved; the external round gave four minor
  findings and one refuted; the answer is comment 6163950067. Converged.
- **Round 3** (a return after `merge_ok`, empty delta): converged; the human held the
  merge to read the report.
- **Round 4** (a return after `merge_ok`, the revision by `report-changes`,
  `059f8f0..d8c7380`, the report read again whole): F5 important; E1, E2, E3, E5 resolved.
- **Round 5** (local, precision, `d8c7380..75f3ff8`): F5 resolved, F6 minor declined. No
  external round: the tweak's cap of one was used in round 2.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | Section 5.1 lacked `LADO_AGENT_ENV=inherit`, by which compose's variables reach the agents (`agent_env.py`) | confirmed | important | fixed in `2d99144` |
| F2 | 1 | local | H6: after a prune, finish does not take the worktree as gone but fails (`runtime.gone` looks only at the folder); reproduced | confirmed | important | fixed in `2d99144` |
| F3 | 1 | local | Two names for one variable (section 5.6, task 3) | confirmed | minor | fixed in `2d99144` |
| F4 | 1 | local | "five code changes" against four tasks (sections 7 and 8) | confirmed | minor | fixed in `2d99144`, recounted in `d8c7380` |
| E1 | 2 | external | Summary and 5.1 on Claude Code's login on a Linux host | confirmed | minor | fixed in `d8c7380` (the human's decision) |
| E2 | 2 | external | The ssh socket line of compose holds only for Docker Desktop | confirmed | minor | fixed in `d8c7380` (the human's decision) |
| E3 | 2 | external | A needless `-it` in a Dockerfile comment | confirmed | minor | fixed in `d8c7380` (the human's decision) |
| E4 | 2 | external | The count of code changes in section 7 | refuted | — | dropped |
| E5 | 2 | external | No `safe.directory` in the image task | confirmed | minor | fixed in `d8c7380` (the human's decision) |
| F5 | 4 | local, by hand | The uid fit by the owner of `/projects` was proposed for every host; on Docker Desktop a bind mount's owner is `0:0`, so `lado` would become root (Dev Containers' `updateRemoteUserUID` is Linux only) | confirmed | important | fixed in `75f3ff8`: 5.4 and task 4 limit it to Docker Engine on Linux, owner 0 skipped |
| F6 | 5 | local | Task 4 mounts projects at the host's path (5.3), but names `/projects` in `safe.directory` | confirmed | minor | declined: a task draft; whoever builds it picks the path; the report's conclusions do not change |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 6 (F1-F6) | 0 | 0 |
| external, Claude Code Action | 4 (E1-E3, E5) | 1 (E4) | 0 |

## Checks

- `openspec validate docker-install-research --strict` valid; `openspec validate --specs
  --strict` 17 passed at the archive.
- CI on `75f3ff8` green: check (3.10, 3.13), js, ui, smoke × 8 (Linux, macOS).
- `make lint` and `make test` not run by the reviewer: no code in the diff; CI ran both.
- Every task of `tasks.md` checked (H4 inside task 1.4 is `not checked`, said there).

## Found on the way

- FW1 (P3): finish fails on a worktree git has forgotten; in BACKLOG.md by `059f8f0`.

## Not checked

- H4 (Codex): from documentation only.
- Windows and Linux hosts: from documentation, the uid fit on Linux included.
- A tool installed by a LADO agent itself through mise.
- `LADO_AGENT_ENV=inherit` in the container was not run by hand.
- The image was built for arm64 only.
- The Russian comment on LAD-52 was not opened by the reviewer.
- No external round after the revision: sections 5.1, 5.2, 5.4, 5.7, 5.14, 5.16 and 8 were
  read by the local reviewer only. The external reviewer is the same model family.
