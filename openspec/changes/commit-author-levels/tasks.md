The plan with each task's tests: `docs/superpowers/plans/2026-11-24-commit-author-levels.md`.

## 1. Storage

- [x] 1.1 Schema 44: table `commit_author`, `author_name`/`author_email` on `projects`, the
  state functions, `previous_schema` (D1). Check: `tests/test_state.py` (43 → 44, the
  rollback by the backup, a project's author gone with it).

## 2. The rules

- [x] 2.1 `lado.commit_authors`: the checks, LADO's and the project's author, `git_own`,
  `in_effect`, `author_variables` (D2, D5, D6). Check: `tests/test_commit_authors.py`.
- [x] 2.2 `git_servers.variables` with LADO's entries first and the project's last; none in
  `for_git` (D3). Check: `tests/test_git_servers.py` (a real `git config --get` under the
  variables agrees with `in_effect`).

## 3. The launch

- [x] 3.1 `_ours` passes LADO's and the session's project's author; the 2.31 refusal; the
  author variables' warning for any LADO author (D3, D6, D7). Check:
  `tests/test_runtime_git_servers.py`, `tests/test_runtime_projects.py`.

## 4. LADO's own first commits

- [x] 4.1 `scratch.author_problem(path, project)`, the new text and hint, `make` and
  `setup.make` commit as the author in effect, `projects.add_new` passes its project (D4).
  Check: `tests/test_scratch.py`, `tests/test_setup.py`, `tests/test_project_repos.py`.

## 5. The command line

- [x] 5.1 `lado git-server author` without an address, list's first line, the server's
  cleared line, `lado project author`, `project show`'s line, human-only (D8). Check:
  `tests/test_cli_git_server.py`, `tests/test_cli.py`.

## 6. doctor and the container

- [x] 6.1 `git author`'s three lines, the entrypoint's warning, compose's header (D10).
  Check: `tests/test_doctor.py`; `tests/container/test_access.py` (CI's container job).
- [x] 6.2 A clean container makes a repository from scratch with LADO's author set through
  the API. Check: `tests/container/test_access.py`.

## 7. The server API

- [x] 7.1 `GitServers.author/git_author/author_variables`, `PUT`/`DELETE /api/git-author`,
  `ProjectInfo.author/author_variables`, repositories' `commit_author`, `PUT`/`DELETE
  /api/projects/{id}/author`, the scratch and setup infos (D9); `make web-types`. Check:
  `tests/test_server_git_servers.py`, `tests/test_server_projects.py`,
  `tests/test_server_launch.py`, `make web`.

## 8. The web UI

- [x] 8.1 Settings → Git servers: LADO's author block, the server's minor line, `?author`
  (the flow's spec). Check: `web/src/GitServers.test.tsx`, `tests/ui/test_git_servers_section.py`.
- [x] 8.2 The project page's author line. Check: `web/src/Projects.test.tsx`,
  `tests/ui/test_project_page.py`.
- [x] 8.3 `AuthorMissing` in New empty folder, the folder set-up and Add repository → From
  scratch; check again on focus. Check: `web/src/Launch.test.tsx`,
  `web/src/LaunchSetup.test.tsx`, `web/src/ProjectRepos.test.tsx`.
- [x] 8.4 The main scenario end to end, screenshots as run artifacts. Check:
  `uv run pytest -m ui tests/ui/test_commit_author_pages.py`.

## 9. End to end

- [x] 9.1 The fake agent commits as LADO's, a server's and a project's author by the order;
  `lado start --new` with LADO's author alone; the warning (D12). Check: `uv run pytest -m
  integration tests/integration/test_commit_author_order.py
  tests/integration/test_git_server_author.py`.

## 10. Docs

- [x] 10.1 `docs/cli.md`, `docs/design/ui.md`, `docs/design/projects.md`,
  `docs/design/agents.md`, `docs/design/modules.md`, AGENTS.md's Layout line, CHANGELOG.md's
  `0.49.0 (unreleased)`. Check: `tests/test_agents_md.py`.

## 11. Regression

- [x] 11.1 `make lint`, `make test`, the changed integration and UI files with their markers,
  `make web`, `openspec validate commit-author-levels --strict`, the trial archive. Check:
  the numbers in `build-report`.
