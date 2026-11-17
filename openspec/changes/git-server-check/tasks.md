The plan with each task's tests: `docs/superpowers/plans/2026-11-17-git-server-check.md`.

## 1. The core's small fixes

- [ ] 1.1 A trailing dot dropped from the host (D8). Check: `tests/test_git_servers.py`
  (`gitlab.corp.ru.` replaces `https://gitlab.corp.ru`; `...` names no host).
- [ ] 1.2 Author globs in any letter case and with the scheme's port (D8). Check:
  `tests/test_git_servers.py` (each glob against real git, the near-miss hosts not matching,
  the ssh forms unchanged).
- [ ] 1.3 The lock of saving and removing (D9). Check: `tests/test_git_servers.py` (a removal
  waits for a save holding the lock; the 10 s refusal with a held lock; the row and the token
  file agree after a removal racing a replacement in two threads).
- [ ] 1.4 A removal whose folder stays warns (D10); the old-git refusal names every server
  (D11); an author file's failed write leaves no temp file (D12). Check:
  `tests/test_git_servers.py`, `tests/test_runtime_git_servers.py`,
  `tests/test_cli_git_server.py`.
- [ ] 1.5 A token refused by every kind names no kind (D13); `choose_kind` on Add's refusal
  of a server that stopped answering (D14). Check: `tests/test_git_servers.py` against
  `tests/fake_git_api.py`.

## 2. The rights of a token

- [ ] 2.1 `Answer.headers` (D2). Check: `tests/test_model_servers.py` (the headers of an
  answer, lowercased; none without an answer).
- [ ] 2.2 `Kind.needs` and `Kind.rights` for GitHub and GitLab (D3). Check:
  `tests/test_git_servers.py` per kind against the fake API: GitLab's scopes all, without
  `write_repository`, without `read_repository`, `api` alone, 404; GitHub's header with
  `repo`, without, empty, absent.
- [ ] 2.3 Add reads the rights and warns (D4). Check: `tests/test_git_servers.py`,
  `tests/test_cli_git_server.py` (the warning, exit 0, the server saved).

## 3. The check

- [ ] 3.1 `git_servers.check` and its outcomes, the login saved on `ok` (D1, D5). Check:
  `tests/test_git_servers.py`, one test per outcome per kind against the fake API: ok,
  rights not checked, token refused, a scope missing, no answer (timeout, unknown name),
  certificate not trusted (a local TLS server with its own CA), redirect (no request to the
  target), another kind, neither kind; no such server; token missing (no request); the login
  saved on ok only.
- [ ] 3.2 `lado git-server check <address>` (D6). Check: `tests/test_cli_git_server.py`
  (stdout and exit 0; stderr, hint and exit 1 per outcome; exit 2 for a bad address).
- [ ] 3.3 `POST /api/git-servers/{host}/check`, `GitServerSaved.warning` and
  `missing_scopes`, `EntryRefused.choose_kind` (D4, D7, D14); `make web-types`. Check:
  `tests/test_server_git_servers.py` (each outcome's body, 404, 422, the canary token in no
  answer or log), `make web` (stale types).

## 4. The page

- [ ] 4.1 `InfoTip`'s `place`, the heading wrapper, the phone field head (D17). Check:
  `web/src/InfoTip.test.tsx`, `make web`.
- [ ] 4.2 The rows and panels, Sign-in with Check and its results, the closed row's line 2
  of this visit (D1, D16). Check: `web/src/GitServers.test.tsx`.
- [ ] 4.3 Replace token with its states, save without a check (D15). Check:
  `web/src/GitServers.test.tsx`.
- [ ] 4.4 Commit author in the panel with Undo; Remove server in the foot; Add's states
  (already saved → Replace its token, github.com, lost server, missing scope on done); one
  result at a time; the focus table. Check: `web/src/GitServers.test.tsx`.
- [ ] 4.5 UI e2e of the specs' scenarios against a fake API, no network: Add (every state),
  Check (every outcome), Replace token (done, another user, refused, no answer), the author
  with Undo, Remove server, the focus after each action, one result line, the canary token;
  at 1440, 768 and 390 with no horizontal scroll; screenshots. Check: `uv run pytest -m ui
  tests/ui/test_git_servers_section.py`.

## 5. End to end

- [ ] 5.1 Integration: a worker's commit in its own worktree of a session's repository cloned
  by LADO from the local https server carries the server's author; a remote written
  `https://GIT.test:8443/…` too. Check: `uv run pytest -m integration
  tests/integration/test_git_server_author.py`.

## 6. Docs and the pull request

- [ ] 6.1 `docs/cli.md` (`lado git-server check`, the rights, the warning, the removal's
  warning, the trailing dot, the author's forms), `docs/design/ui.md` (Git servers by the new
  layout, the routes and fields), `docs/design/modules.md` (`git_servers.check`, `Kind.rights`,
  the lock), CHANGELOG.md (the 0.48.0 git servers entry gains Check). Check: `uv run pytest
  tests/test_agents_md.py`, the docs checks of `make lint`.
- [ ] 6.2 The regression run and the pull request's description with the manual check of the
  design doc.
