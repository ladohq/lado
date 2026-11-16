The plan with each task's tests: `docs/superpowers/plans/2026-11-16-git-server-author.md`.

## 1. Storage

- [x] 1.1 Schema 42: `author_name`, `author_email` on `git_servers`, `set_git_server_author`,
  `previous_schema`; adding a server again keeps its author (D4, D7). Check:
  `tests/test_state.py` (41 → 42, the rollback by the backup, keep on re-add).

## 2. The rules

- [x] 2.1 `check_author`, `set_author`, `clear_author`, `check_author_git` (D5, D6). Check:
  `tests/test_git_servers.py`.
- [x] 2.2 `author_entries`, `variables(…, authors=)`, the author file (D1, D3). Check:
  `tests/test_git_servers.py` (each form against real git, near-miss hosts, the file read
  back by `git config --file`).

## 3. The launch

- [x] 3.1 The files in the agent's config folder and the entries in `_ours`; none in
  `for_git` (D2, D3). Check: `tests/test_runtime_git_servers.py`.
- [x] 3.2 The 2.36 refusal in `_check_commands` and the `GIT_AUTHOR_*` warning (D6, D8).
  Check: `tests/test_runtime_git_servers.py`.

## 4. End to end

- [x] 4.1 Integration test with the fake agent: https and `git@` clones carry the server's
  author, other repositories the human's, clear + restart, the file's content, global and
  system configs unchanged. Check: `uv run pytest -m integration
  tests/integration/test_git_server_author.py`.
- [x] 4.2 Smoke: a commit inside Codex's sandbox takes the author. Check: CI's smoke job.

## 5. The command

- [x] 5.1 `lado git-server author` and list's `AUTHOR` (D9). Check: `tests/test_cli_git_server.py`.

## 6. The server API

- [x] 6.1 `PUT`/`DELETE /api/git-servers/{host}/author`, `GitServerInfo`'s author, `make
  web-types` (D10). Check: `tests/test_server_git_servers.py`, `make web`.

## 7. The page

- [ ] 7.1 ✎ Commit author, its form, the row's line, the done lines (D10, mockup option 1).
  Check: `web/src/GitServers.test.tsx`, `make web`.
- [ ] 7.2 UI e2e: set, see, refuse, remove; screenshots. Check: `uv run pytest -m ui
  tests/ui/test_git_servers_section.py`.

## 8. Docs and the pull request

- [ ] 8.1 `docs/cli.md`, `docs/design/ui.md`, `docs/design/agents.md`,
  `docs/design/modules.md`, CHANGELOG.md. Check: `uv run pytest tests/test_agents_md.py`.
- [ ] 8.2 The regression run and the pull request's description with the manual check.
