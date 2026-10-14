Follows docs/superpowers/plans/2026-10-15-projects-at-host-path.md; each task there has
the tests' code and the commit.

## 1. The doctor's write check

- [x] 1.1 Unit tests first (layer 1), `tests/test_doctor.py`: a folder LADO may not write
  in warns `LADO may not write in LADO_REPOS <path>: <reason>` with the hint and leaves no
  file; a writable folder is `ok` and holds no file after. Plan, Task 1.
- [x] 1.2 `doctor.check_repos_folder`: the probe file (D8). `uv run pytest
  tests/test_doctor.py -n0`.

## 2. The entrypoint, the sudo rule and git's trust

- [x] 2.1 Unit tests first, `tests/test_docker.py`: profile.sh without `LADO_REPOS`, the
  entrypoint under tini, the sudo rule's line, mode and `visudo -cf`, the marker,
  `safe.directory '*'`, the allowlist with `docker/entrypoint.sh`, the root branch deleting
  the rule and marker before anything else, `lado-repos.sh` written. Plan, Task 2.
- [x] 2.2 `docker/entrypoint.sh`, the Dockerfile (sudo, rule, marker, entrypoint, git
  config, header), `docker/profile.sh`, the dockerignore (D2-D7). `uv run pytest
  tests/test_docker.py -n0`; with Docker, `make docker` and the existing `make
  test-container` green.

## 3. Compose at the host's path

- [x] 3.1 Tests first: `tests/test_docker.py` (the same-path volume and `LADO_REPOS`),
  `test_compose_serves_on_lado_port` (the doctor's `Repositories folder` line on the
  compose project's projects path). Plan, Task 3.
- [x] 3.2 `docker/compose.yaml` and its header (D1). `uv run pytest tests/test_docker.py
  -n0`; `make test-container`.

## 4. Container tests of the path and the owner

- [x] 4.1 Helpers: a given home volume, a projects volume of a given owner, the Claude
  session's setup shared with `test_image.py` (D9). Plan, Task 4.
- [x] 4.2 Container tests (layer 7), `tests/container/test_projects.py`: a worker's
  worktree on the host (status, no `prunable`, files and commit objects the host user's,
  the agent's `LADO_REPOS`); the projects owner's uid, no sudo left, `docker exec lado ui`,
  a restart under 8 s keeping the uid; recreated with another uid and the same home; owner
  0 keeps 1000 and warns; `LADO_REPOS` not mounted warns. `make docker && make
  test-container`.

## 5. Docs and the regression run

- [x] 5.1 AGENTS.md (Layout `docker/`, Commands' container tests) and CHANGELOG.md 0.39.0
  (D11). Plan, Task 5.
- [x] 5.2 Regression: `make lint`, `make test`, `openspec validate --specs --strict`,
  `openspec validate projects-at-host-path --strict`; with Docker `make test-container`.
- [ ] 5.3 The pull request's CI: `container (amd64)`, `container (arm64)` and `ci-ok`
  green (the Linux runner's uid 1001 is AC-3), the jobs' times in the build report.
- [ ] 5.4 By hand on a Mac (AC-9): a session in the UI on a project of the folder mounted
  at its path, a worker commits, `git worktree list` on the host clean; screenshots as run
  artifacts.
