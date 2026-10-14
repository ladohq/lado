# LAD-64 docker-image-in-ci: review report

Pull request #50 `feature/lad-64-docker-image` → `main`. Scale: full, breadth-first
review. Head reviewed last: `65d0b8c` (= the remote head); the archive commit follows it.
`src/` did not change; `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
`agent_env.py` and `tests/live/` did not change, so live tests are not needed before the
merge.

## Rounds

- **Round 1, local** (breadth pass over `origin/main...48038cb`): 1 important, 3 minor.
- **Round 2, local** (precision pass over `48038cb..b089e16`): clean but minor F5.
- **Round 1, external** (Claude Code GitHub Action, request comment 6179223540, answer
  6179227169): no blocker; E1-E5 answered in comment 6179249632.
- **Back from `merge_ok`:** the human asked for the by-hand checks of AC-9 in this task.
  The developer ran them on a Mac: `docker run` on port 8765 and compose `-p lado-2` on
  8766, both links opened by the human. The check found M1, fixed in `65d0b8c`.
- **Round 3, local** (precision pass over `b089e16..65d0b8c`): no new defect. `export
  LADO_PROJECTS=~/projects` expands `~` in the assignment (bash and zsh); the
  `-p lado-2` example takes the variable from that export; the new test parses the
  header right and can fail. The old lines of the plan under `docs/superpowers/plans/`
  stay on purpose: they record how the work was planned.
- **Round 2, external** (request comment 6179712024 at 22:16:36Z, "Claude finished"
  6179715859, newer than the request): no blocker, one minor (E6); the reviewer called
  the loop converged.

External rounds used: 2 of 2.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local, silent failures / spec | a failed container test kept no `docker logs` and LADO logs when it failed in setup or in a test without the `container` fixture, against the CI spec and AGENTS.md | confirmed | important | fixed in `b089e16` (shown red on a broken image) |
| F2 | 1 | local, comments | AGENTS.md promised a check for leftover volumes and compose projects that did not exist; the name prefix matched other runs | confirmed | minor | fixed in `b089e16` |
| F3 | 1 | local | `make docker` removes all of `dist/` | confirmed | minor | declined: needed for the one-wheel rule; `dist/` is rebuilt |
| F4 | 1 | local, comments | AGENTS.md's Dependabot line not reflowed | confirmed | minor | fixed in `b089e16` |
| F5 | 2 | local, comments | a 106-character line in AGENTS.md's Container tests paragraph | confirmed | minor | declined: cosmetic |
| E1 | ext 1 | external | bind mount owner on Linux with uid ≠ 1000, `safe.directory` | refuted for this PR | — | out of scope: plan steps T4/T5 |
| E2 | ext 1 | external | `gh` from apt and its keyring not pinned | refuted | — | the spec pins base images by digest; apt checks signatures |
| E3 | ext 1 | external | no `HEALTHCHECK` | refuted | — | not a defect |
| E4 | ext 1 | external | `health()` retries only on `OSError` | confirmed | minor | declined: no sign of it in CI |
| E5 | ext 1 | external | job `container` has no `permissions:` | refuted | — | the repository's default workflow permissions are `read` |
| M1 | by hand | developer, at the human's request | `docker/compose.yaml`'s header showed `docker compose exec …` without `LADO_PROJECTS`, which compose reads in every command | confirmed | important | fixed in `65d0b8c`: the header exports it; regression test `test_the_compose_headers_commands_all_have_the_projects_folder` (seen red); design doc example fixed |
| E6 | ext 2 | external | the new test also accepts `"LADO_PROJECTS=" in line` in prose | confirmed | minor | declined: only `docker compose` lines are checked |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 5 (F1-F5) | 0 | 0 |
| external, Claude Code Action | 2 (E4, E6) | 4 (E1, E2, E3, E5) | 0 |
| by hand | 1 (M1) | 0 | 0 |

## Checks

- Reviewer on `65d0b8c`: `make lint` clean; `uv run pytest tests/test_docker.py -n0`
  15 passed. Unit tests: 3134 passed on `48038cb` (reviewer), 3135 on `65d0b8c`
  (developer).
- CI run 38645152267 on `65d0b8c`: `ci-ok` and the other 22 jobs success; the artifact
  `container-arm64` shows 7 passed, none skipped.
- At archive: `openspec validate --specs --strict` 24 passed.

## Found on the way

None.

## Not checked

- `make test-container` not run locally by the reviewer: CI (amd64 and arm64, 7 passed,
  none skipped) and the developer's runs.
- The full `make test` not rerun by the reviewer on `65d0b8c`.
- No one showed the teardown red on a left-over volume or container.
- Dependabot's grouping of digest-only updates shows only live.
- A Linux host with uid ≠ 1000: step T5.
- Claude Code's login and a real model in the container: steps T8/T10.
- The external reviewer is the same model family.
