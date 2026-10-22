The plan with each task's tests: `docs/superpowers/plans/2026-10-22-project-repositories.md`.

## 1. Core

- [x] 1.1 The name rule and the add target: `check_repo_name`, `new_repo_folder`,
  `NoSuchRepository` (D1, D2). Check: `tests/test_project_repos.py` (new).
- [x] 1.2 `project` in `clone.check_target`/`clone.clone` and
  `scratch.check_target`/`scratch.make`; `projects.add_clone`, `projects.add_new` (D3,
  D4). Check: `tests/test_clone.py`, `tests/test_scratch.py`, `tests/test_project_repos.py`
  (a failed and a cancelled clone leave nothing).
- [x] 1.3 `_checkout_lines`, `removal`, `remove_repo` (D6, D7, D8). Check:
  `tests/test_project_repos.py`, `tests/test_projects_core.py` (`unpushed` unchanged).
- [ ] 1.4 The refusal's hints and the text for a project without repositories (D10).
  Check: `tests/test_projects_core.py`, `test_clone.py`, `test_scratch.py`,
  `test_server_launch.py`, `test_runtime_projects.py`.

## 2. CLI and server

- [ ] 2.1 `lado project repo add|remove`, human only (D5, D8). Check: `tests/test_cli.py`.
- [ ] 2.2 The clone job into a project, `POST /api/projects/{id}/repos`, `GET
  …/repos/{name}/removal`, `DELETE …/repos/{name}`; `make web-types` (D9). Check:
  `tests/test_server_clones.py`, `tests/test_server_projects.py` (new), `make web`.

## 3. End to end

- [ ] 3.1 `tests/integration/test_project_repositories.py`: add by clone and from scratch,
  then start in each; an ended and a failed clone leave nothing; removal refused while a
  session runs, the worker's unpushed branch shown, nothing without `--yes`, folder and
  session gone with it, the neighbours intact; both refused from an agent. Check: `uv run
  pytest -m integration -n auto tests/integration/test_project_repositories.py`.

## 4. Documents and version

- [ ] 4.1 `docs/cli.md`, `docs/design/projects.md`, `docs/design/modules.md`,
  `docs/design/ui.md` (D12). Check: `uv run pytest tests/test_agents_md.py`.
- [ ] 4.2 CHANGELOG: one line under `## 0.43.0 (unreleased)`.

## 5. Regression

- [ ] 5.1 `make lint`; `make test` (counts); the changed and neighbouring integration files
  with `-m integration`; `make web`; `openspec validate project-repositories --strict`;
  `openspec validate --specs --strict`; the trial archive in the scratchpad; CI `ci-ok`
  green (container and smoke cells included).
