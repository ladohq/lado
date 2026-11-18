The plan with each task's tests: `docs/superpowers/plans/2026-11-18-github-com-entry.md`.

## 1. github.com as a server

- [ ] 1.1 The GitHub kind asks `https://api.github.com/user` for github.com; add, remove,
  check, author of github.com; www./api. taken, port, path and `--kind` refused (D1).
  Check: `tests/test_git_kinds.py`, `tests/test_git_servers.py`, `tests/test_cli.py`.

## 2. Schema 43

- [ ] 2.1 `github_takeover`, migration 42 → 43,
  `previous_schema` (D2). Check: `tests/test_state.py`.

## 3. The takeover

- [ ] 3.1 `github_takeover.run()` before agents and at the UI server's start; sources,
  outcomes, once, retry after a gh failure, the line (D3). Check:
  `tests/test_github_takeover.py`.

## 4. GitHub variables of agents and LADO's own git

- [ ] 4.1 The GitHub names dropped from every layer; `gh_variables` (github.com, GitHub
  Enterprise, `GH_CONFIG_DIR`) (D4); agent-variables' examples moved off `GH_TOKEN`. Check:
  `tests/test_agent_env.py`, `tests/test_runtime.py`.

## 5. The unused login and doctor

- [ ] 5.1 `unused`, doctor's GitHub lines and busy lado.db, `project set`'s warning (D5,
  D10). Check: `tests/test_doctor.py`, `tests/test_cli.py`.

## 6. Clone hints

- [ ] 6.1 github.com's hints as a server's, two-line hint, host with port (D8, D10). Check:
  `tests/test_clone.py`; `make web` if the API changes.

## 7. The page

- [ ] 7.1 github.com listed and added as any server; Servers' ⓘ; the Add refusal of
  github.com gone; Edit and Set author off while asking (D7, D10). Check:
  `tests/test_server_git_entries.py`, vitest `GitServers.test.tsx`, UI e2e
  `tests/ui/test_git_servers_section.py`, screenshots.

## 8. Docker

- [ ] 8.1 No system helper for github.com; headers of Dockerfile, compose.yaml,
  install.sh (D6). Check: `tests/test_docker.py`; container tests in CI.

## 9. End to end

- [ ] 9.1 `tests/integration/test_github_takeover.py` (the design doc's cases 1–6) and the
  rollback in `tests/integration/test_update_process.py` (D11). Check: `uv run pytest -m
  integration -n auto` on those files.

## 10. Docs

- [ ] 10.1 `docs/cli.md`, `docs/design/ui.md`, `docs/design/modules.md`,
  `docs/install.md`, `docs/design/projects.md`, AGENTS.md's module line, CHANGELOG.md
  0.48.0. Check: `tests/test_agents_md.py`, the docs checks of `make test`.
