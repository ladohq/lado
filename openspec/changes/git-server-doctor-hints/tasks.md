The plan with each task's tests: `docs/superpowers/plans/2026-11-18-git-server-doctor-hints.md`.

## 1. lado doctor

- [ ] 1.1 `git_servers.check(at, save_login=True)`; doctor's `check_git_servers`, one line per
  server, asked at once beside the model servers, never `FAIL`, nothing written (D1, D2).
  Check: `tests/test_doctor.py` (working and refused servers, none saved, another schema, no
  answer, token file missing, an address no longer taken, asked at once, exit status, no
  login saved), `tests/test_git_servers.py` (`save_login=False` writes nothing).

## 2. The clone's git server texts

- [ ] 2.1 The kind `access_denied` and github.com's text for it (D4). Check:
  `tests/test_clone.py`.
- [ ] 2.2 The saved server git took the token of, and the check and add texts (D3, D5).
  Check: `tests/test_clone.py` (each kind for a saved server, the ssh form, an unsaved host's
  login and 403, its not found and unreachable without hint, another scheme, github.com
  unchanged, a kit's `explain`, another schema); integration
  `tests/integration/test_git_server_access.py` (a refused saved token, an unsaved host, with
  real git).
- [ ] 2.3 `CloneError.server` and `CloneRefused.git_server`; `make web-types` (D6). Check:
  `tests/test_server_clones.py`; `make web`.

## 3. The UI's note and the page's address

- [ ] 3.1 `GitServerNote` in the New session window and Add repository (D7). Check: vitest
  `Launch.test.tsx`, `ProjectRepos.test.tsx`.
- [ ] 3.2 `?check=` and `?add=` of Settings → Git servers (D8). Check: vitest
  `GitServers.test.tsx`; UI e2e `tests/ui/test_launch.py` (both notes and their tabs).

## 4. The page's leftovers

- [ ] 4.1 One Replace token; no ✓ before `Works:` (D9). Check: vitest `GitServers.test.tsx`.
- [ ] 4.2 An open tip follows its button across a layout switch (D10). Check: UI e2e
  `tests/ui/test_git_servers_section.py`.
- [ ] 4.3 The author's Remove and Undo off while they ask (D11). Check: vitest
  `GitServers.test.tsx`.

## 5. Docs and housekeeping

- [ ] 5.1 `docs/cli.md` (doctor, the clone texts, the `invalid_token` gateway line),
  `docs/design/ui.md`, `docs/design/modules.md`, CHANGELOG.md's 0.48.0 (D12). Check: read
  against the code; `make lint`.
- [ ] 5.2 BACKLOG.md without the Kilo smoke entry (LAD-295 holds it). Check: `grep -n "Kilo
  smoke on macOS" BACKLOG.md` finds nothing.
- [ ] 5.3 The regression run of the plan; `openspec validate git-server-doctor-hints
  --strict` and the trial archive.
