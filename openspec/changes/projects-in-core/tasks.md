The plan with each task's tests and code: `docs/superpowers/plans/2026-10-21-projects-in-core.md`.

## 1. The workspace

- [x] 1.1 `src/lado/projects.py` with `WORKSPACE_VAR`, `DEFAULT_WORKSPACE`, `workspace()`,
  `workspace_source()` (D1); `clone.py`, `scratch.py`, `runtime.py`, `cli.py`,
  `server/launch.py`, `server/clones.py` take it, the old names go (D2). Check: unit
  tests of the workspace, the clone's and a fresh start's default folder without and with
  `LADO_REPOS`, the container's warning (`tests/test_projects.py`, `test_clone.py`,
  `test_scratch.py`, `test_runtime.py`, `test_server_clones.py`, `test_server_launch.py`).
- [ ] 1.2 `doctor.check_workspace` always a line; `(LADO_REPOS)`/`(default)`, not made
  yet, the ignored relative value, a file, unwritable (D4, D11). Check:
  `tests/test_doctor.py`.
- [ ] 1.3 `GET /api/repos-folder` answers `Workspace{path, made}`; the window's
  placeholders, Workspace row and hints per D12; `make web-types`. Check:
  `tests/test_server_launch.py`, `web/src/Launch.test.tsx`, `make web`.

## 2. Projects

- [ ] 2.1 Schema 32: the table `projects`, its state functions and
  `creating_project`; `tests/agent_helpers.schema_before` (D5). Check: `tests/test_state.py`
  (migration from `previous_schema` with its backup).
- [ ] 2.2 The id rule, titles, `owned_by_human`, `foreign`, `create`, `rename`, `listed`
  (D6, D7). Check: `tests/test_projects.py`.
- [ ] 2.3 The unpushed scan and `delete` (link, outside check, rmtree failure) (D8).
  Check: `tests/test_projects.py` with real git.
- [ ] 2.4 `lado project list|create|show|rename|delete`, agents refused (D9, D10).
  Check: `tests/test_cli.py`.
- [ ] 2.5 `doctor.check_projects` (D11). Check: `tests/test_doctor.py`.

## 3. End to end

- [ ] 3.1 `tests/integration/test_projects.py`: the commands as processes, folders made
  and removed, every create refusal, the agent refusal, delete with unpushed work, doctor
  with and without `LADO_REPOS` and its Projects findings; the clone's default in
  `~/workspace`. Check: `uv run pytest -m integration -n auto <files>`.
- [ ] 3.2 `tests/ui/test_launch.py`: Where without and with `~/workspace`, screenshots.
  Check: `uv run pytest -m ui <file>`.

## 4. Documents and version

- [ ] 4.1 `docs/cli.md`, `docs/design/modules.md`, `docs/design/projects.md`,
  `docs/design/ui.md`, `docs/install.md`, AGENTS.md (Layout line of `projects.py`).
  Check: `uv run pytest tests/test_agents_md.py`.
- [ ] 4.2 S1's leftover "the repositories' toolchains" in `docker/Dockerfile`,
  `docs/install.md`, `docs/design/modules.md`, `tests/container/test_toolchains.py`
  (D13).
- [ ] 4.3 CHANGELOG: `## 0.43.0 (unreleased)`, two lines (D14).
- [ ] 4.4 The grep by meaning of AC-10 finds no default-folder claim of `~/lado` and no
  "no workspace without LADO_REPOS" outside the historical documents.

## 5. Regression

- [ ] 5.1 `make lint`; `make test` (counts; the leftover check of LAD-121 named if it is
  the only red); the changed integration and UI files with their markers; `make web`;
  `openspec validate projects-in-core --strict`; `openspec validate --specs --strict`;
  CI `ci-ok` green.
