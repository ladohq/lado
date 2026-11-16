The plan with each task's tests: `docs/superpowers/plans/2026-11-16-git-servers-page.md`.

## 1. The core

- [x] 1.1 `git_servers.Refused` with `field`, `page`, `page_hint` on every refusal (D2).
  Check: `tests/test_git_servers.py`.
- [x] 1.2 `check_host` and its check inside `save`; `git_servers.add` shared by the command
  (D1, D5). Check: `tests/test_git_servers.py`, `tests/test_cli_git_server.py`.
- [x] 1.3 `git-servers/` removed with the last server; `_write_token` retries once (D6).
  Check: `tests/test_git_servers.py`.

## 2. The address check without a token

- [ ] 2.1 `Kind.request` without a token, `git_servers.hint`, the fake API's profiles that
  ask for a credential (D3). Check: `tests/test_git_servers.py`, `tests/test_fake_git_api.py`.

## 3. The server API

- [ ] 3.1 `server/git_entries.py`, the models, the four routes, `SECRET_ROUTE`; `make
  web-types` (D4). Check: `tests/test_server_git_servers.py`, `make web`.

## 4. The page

- [ ] 4.1 The section in `settingsSections.ts` and `Settings.tsx`; the list (D7). Check:
  `web/src/Settings.test.tsx`, `uv run pytest -m ui tests/ui/test_settings_pages.py`.
- [ ] 4.2 The add form and Remove. Check: `web/src/GitServers.test.tsx`, `make web`.
- [ ] 4.3 The UI e2e test with the fake APIs and the gitlab.com proxy (D8); screenshots for
  the build report. Check: `uv run pytest -m ui tests/ui/test_git_servers_section.py`.

## 5. Docs and the pull request

- [ ] 5.1 `docs/design/ui.md`, `docs/cli.md`, `docs/design/modules.md`, AGENTS.md's `server/`
  line, CHANGELOG.md's 0.48.0 entry. Check: `uv run pytest tests/test_agents_md.py`.
- [ ] 5.2 The pull request's description with the manual check (design doc). Check: the
  regression run of the plan's task 7.
