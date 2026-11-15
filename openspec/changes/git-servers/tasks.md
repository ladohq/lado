The plan with each task's tests: `docs/superpowers/plans/2026-11-15-git-servers.md`.

## 1. Kinds and the probe

- [ ] 1.1 `model_servers`: `ask`, `no_answer`, `NoRedirect`, `Answer` public (renames only,
  D2). Check: `uv run pytest -n auto tests/test_model_servers.py`.
- [ ] 1.2 `tests/fake_git_api.py` with its profiles. Check: `tests/test_fake_git_api.py`.
- [ ] 1.3 `src/lado/git_kinds/` (`base`, `github`, `gitlab`, `KINDS`) (D1, D2). Check:
  `tests/test_git_kinds.py`.
- [ ] 1.4 `git_servers.address` and `git_servers.probe` with the texts of the design doc's
  table (D2, D3). Check: `tests/test_git_servers.py`.

## 2. The store

- [ ] 2.1 `state.py`: table `git_servers`, `SCHEMA_VERSION = 41`, `MIGRATIONS[40]`,
  `GitServer` and its functions; `tests/agent_helpers.schema_before` (D4). Check:
  `tests/test_state.py`.
- [ ] 2.2 `git_servers` save/replace/remove with the token file by `project_secrets` (D4).
  Check: `tests/test_git_servers.py` (modes, link refused, canary, replace keeps the id).

## 3. The git variables and the helper

- [ ] 3.1 `git_servers.variables` (D5) and `git_servers.check_git` (D8,
  `runtime.git_numbers`). Check: `tests/test_git_servers.py`.
- [ ] 3.2 `src/lado/git_credential.py` (D6, D7). Check: `tests/test_git_credential.py` with
  real `git credential fill|approve` and `git ls-remote --get-url`.

## 4. The command

- [ ] 4.1 `lado git-server add|list|remove` and the bare command (D9). Check:
  `tests/test_cli_git_server.py`.

## 5. Agents and LADO's own git

- [ ] 5.1 `runtime._ours` lays the variables; the launch's old-git check (D5, D8). Check:
  unit tests of the launch env.
- [ ] 5.2 `agent_env.for_git(project, remote)`; `gitcache._git` and `clone._env` pass the
  remote (D5, D8). Check: `tests/test_agent_env.py`, `tests/test_gitcache.py`,
  `tests/test_clone.py`.
- [ ] 5.3 `doctor.check_git`'s hint names git servers. Check: `tests/test_doctor.py`.

## 6. End to end

- [ ] 6.1 `tests/fake_git_server.py` (TLS, `git http-backend`, Basic auth, fake API) (D13).
- [ ] 6.2 `tests/integration/test_git_servers.py`: the plan's task 6, cases 1–9. Check:
  `uv run pytest -m integration -n auto tests/integration/test_git_servers.py`.

## 7. Codex's sandbox and the way back

- [ ] 7.1 Smoke: `codex sandbox -- git credential fill` and `git ls-remote` (D12); stop and
  ask the human if the sandbox blocks the helper or the token. Check: CI's smoke cells.
- [ ] 7.2 `self_update`: `git servers` among the loss, the token folders that stay (D11).
  Check: `tests/test_self_update.py`, a case in
  `tests/integration/test_update_process.py`.

## 8. Docs and regression

- [ ] 8.1 `docs/cli.md`, `docs/design/modules.md`, `docs/design/agents.md`,
  `docs/install.md`, AGENTS.md's Layout, CHANGELOG.md (the design doc's "Docs").
- [ ] 8.2 The pull request's manual check (the plan's task 8).
- [ ] 8.3 Regression: `make lint`, `make test`, the integration files of the plan's task 8,
  `openspec validate git-servers --strict` and the trial archive.
