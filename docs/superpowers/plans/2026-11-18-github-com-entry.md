# github.com in the list of git servers: Implementation Plan

**Goal:** github.com becomes a saved git server; today's GitHub login is taken over into it
once; afterwards agents and LADO's own git and `gh` use only the entries (github.com and
GitHub Enterprise), and the outside login is named as unused by doctor and the commands;
the page lists and adds github.com as any server; Docker and the docs lose the old login; the leftovers of the last change are fixed.

**Architecture:** the GitHub kind asks `api.github.com` for github.com (D1); schema 43 keeps
the takeover's record (D2); `github_takeover.run()` before agents
and at the UI server's start (D3); `agent_env` drops the GitHub names from every layer and
`git_servers.gh_variables` gives them from the entries (D4); `github_takeover.unused` names
the outside login for doctor and `project set` (D5); Docker without the system
helper (D6); the page treats github.com as any server (D7); clone hints (D8); GitHub Enterprise's host (D9); the
leftovers (D10).

**Tech Stack:** Python 3.10+ (standard library), FastAPI/pydantic (existing), React +
TypeScript (existing), pytest (`-n auto`, `-m integration`, `-m ui`, `-m container`),
vitest, Playwright's Chromium, git ≥ 2.36.

**Spec:** `openspec/changes/github-com-entry/` (proposal, deltas, `design.md` D1–D11) and
`docs/superpowers/specs/2026-11-18-github-com-entry-design.md` (texts, tests per
requirement, docs, manual check). Mockup: the run's `mockup-github-server.html`.

## Global Constraints

- Nothing outside LADO is changed or removed: the outside folder, the shell, `gh`'s login,
  a project's secrets.
- No token in any text, answer, log line, lado.db, the error journal or a file under
  `LADO_HOME` but its token file (and the launch file, removed when read).
- Schema 43: bump `SCHEMA_VERSION`, `MIGRATIONS[42]`, `tests/agent_helpers.previous_schema`.
- The texts are those of the deltas and the design doc, word for word; another wording needs
  a reason in the build report.
- Tests use no network: `tests/fake_git_api.py`, `tests/fake_git_server.py`,
  `ConnectProxy` with a test CA for `github.com` and `api.github.com`, a stub `gh`.
- Nothing in code, docs, specs or the UI names the epic's stages or `docs/epics/`.
- CHANGELOG: extend 0.48.0 (unreleased); no new version.
- The pull request carries the design doc's manual check from the start.

## Review Focus

1. The takeover runs once and never again after a removal of github.com, also when two starts race
   (the lock; `test_two_starts_take_over_once`).
2. No layer's GitHub variable reaches an agent, a spawned worker or LADO's own git
   (`test_github_variables_from_no_layer`, `test_a_worker_gets_its_own_gh_variables`).
3. `gh auth token` failing for a reason other than no login records nothing
   (`test_a_gh_failure_runs_again`).
4. Rollback: the copy of schema 42 has no github.com row; outside files untouched
   (`test_update_to_an_older_schema_forgets_the_github_entry`).

## Task 1: github.com's API and add/remove (D1)

Files: `src/lado/git_kinds/github.py`, `src/lado/git_kinds/base.py` (if `request` needs the
host), `src/lado/git_servers.py` (`check_not_github` → `github_address`, probe/check ask
the GitHub kind only for github.com), `src/lado/cli.py`, `src/lado/server/git_entries.py`.

- [ ] Write failing tests: `tests/test_git_kinds.py::test_github_com_asks_api_github_com`,
  `::test_ghe_asks_api_v3`; `tests/test_git_servers.py::test_github_com_is_added_through_the_proxy`,
  `::test_www_and_api_are_github_com`, `::test_github_com_with_a_port_or_path_is_refused`,
  `::test_kind_with_github_com_is_refused`, `::test_github_com_probe_asks_one_request`;
  remove `test_github_com_is_not_added`.
- [ ] Implement; `make test PYTEST_ARGS="-n0 tests/test_git_kinds.py tests/test_git_servers.py"`.
- [ ] Commit.

## Task 2: Schema 43 (D2)

Files: `src/lado/state.py`, `tests/agent_helpers.py`.

- [ ] Tests: `tests/test_state.py::test_upgrade_from_42_keeps_servers_and_has_no_takeover`,
  `::test_previous_schema_drops_43`.
- [ ] `github_takeover` table, `SCHEMA_VERSION = 43`, `MIGRATIONS[42]`, state accessors;
  `previous_schema` drops it.
- [ ] Commit.

## Task 3: The takeover (D3)

Files: new `src/lado/github_takeover.py`; calls in `src/lado/runtime.py` (before layers are
merged) and the UI server's start (`src/lado/server/run.py` or `app.py`); the line in
`src/lado/cli.py`.

- [ ] Tests `tests/test_github_takeover.py`: each source in order (outside folder, shell,
  `GITHUB_TOKEN`, `gh` stub), `saved`/`unchecked`/`refused`/`none`/`kept`, once, after
  remove nothing again, the refused line, `test_a_gh_failure_runs_again` (exit 1 with a keychain line, a stub
  sleeping 11 s), `test_two_starts_take_over_once`, the printed line, the server log, no
  token in lado.db or the journal.
- [ ] Implement; commit.

## Task 4: The agents' and LADO's own GitHub variables (D4)

Files: `src/lado/agent_env.py` (`GITHUB_VARIABLES` dropped in `merge`/`for_git`),
`src/lado/git_servers.py` (`gh_variables`), `src/lado/runtime.py` (`_ours`).

- [ ] Tests: `tests/test_agent_env.py::test_github_variables_from_no_layer` (shell, outside,
  project), `::test_for_git_drops_github_variables`; `tests/test_runtime.py::test_gh_token_from_the_entry`,
  `::test_gh_config_dir_is_the_agents_own_and_empty`, `::test_ghe_token_of_the_origins_server`,
  `::test_the_only_ghe`, `::test_two_ghe_neither_origin`, `::test_a_worker_gets_its_own_gh_variables`.
- [ ] The agent-variables tests whose examples were `GH_TOKEN` move to `YOUGILE_API_KEY` /
  `GIT_SSH_COMMAND` (delta of `agent-variables`).
- [ ] Implement; commit.

## Task 5: The unused login named (D5) and doctor (D10's busy lado.db)

Files: `src/lado/github_takeover.py` (`unused`), `src/lado/doctor.py`, `src/lado/cli.py`
(`project set`).

- [ ] Tests `tests/test_doctor.py`: the `GitHub login outside LADO` warn line (outside
  folder, shell, project), the gh info line (stub), none, the takeover's info/warn/pending
  lines, `test_a_busy_lado_db_is_one_warning` (a held write lock past 10 s, patched wait);
  `tests/test_cli.py::test_project_set_github_variable_warns`.
- [ ] Implement; commit.

## Task 6: Clone hints (D8) and the two-line hint, the port (D10)

Files: `src/lado/clone.py`, `src/lado/runtime.py` (`Hint` with several commands), the
callers that print a hint, `web/src/` FolderHint if it renders the command list.

- [ ] Tests `tests/test_clone.py`: github.com saved refused (two lines), unsaved login and
  403 (`Add it as a git server with a token:`), not_found without hint, a kit's `explain`, a
  server with a port named `git.test:8443`; the existing github.com tests updated.
- [ ] Implement; `make web-types` if `CloneRefused` changes; commit.

## Task 7: The page lists and adds github.com as any server (D7) and the author buttons (D10)

Files: `src/lado/server/git_entries.py` (no github.com refusal in the address check and
add), `web/src/GitServers.tsx` (Servers' ⓘ, the Add refusal of github.com gone, `?add=` with
github.com), no new API field.

- [ ] `tests/test_server_git_entries.py`: the address check of `github.com` answers GitHub
  (fake API through the proxy), add saves it, it is listed among `servers`.
- [ ] vitest `web/src/GitServers.test.tsx`: github.com in Servers with any server's panel,
  Add with `github.com` (`GitHub answers.`, the token page `https://github.com/settings/tokens`,
  `scope repo`), no line of its own; Edit and Set author off while Remove/Undo asks.
- [ ] UI e2e `tests/ui/test_git_servers_section.py`: add github.com, Check, Commit author,
  Remove — fake API through the proxy, no network; screenshots.
- [ ] Commit.

## Task 8: (merged into Task 7)

## Task 9: Docker (D6)

Files: `docker/Dockerfile`, `docker/compose.yaml`, `docker/install.sh`, `tests/test_docker.py`,
`tests/container/`.

- [ ] `tests/test_docker.py`: headers name Git servers, not `GH_TOKEN`/`gh auth login`;
  no system helper line. Container: `git credential fill` for github.com with a `gh` login
  on the home volume and no entry prints no password; with an entry the real `gh auth
  status` takes `GH_TOKEN` and the agent's `GH_CONFIG_DIR` (fake API through the proxy).
- [ ] Commit.

## Task 10: The end-to-end tests (the brief's)

- [ ] `tests/integration/test_github_takeover.py`, cases 1–6 of the design doc.
- [ ] `tests/integration/test_update_process.py::test_update_to_an_older_schema_forgets_the_github_entry`.
- [ ] Run `uv run pytest -m integration -n auto tests/integration/test_github_takeover.py
  tests/integration/test_update_process.py tests/integration/test_git_server_access.py`;
  commit.

## Task 11: Docs and CHANGELOG

- [ ] `docs/cli.md`, `docs/design/ui.md`, `docs/design/modules.md`, `docs/install.md`,
  `docs/design/projects.md`, AGENTS.md's module line, CHANGELOG.md 0.48.0 — by the design
  doc's Docs list. Commit.

## Regression run

`make lint`; `make test`; `uv run pytest -m integration -n auto` on the changed and added
integration files; `uv run pytest -m ui tests/ui/test_git_servers_section.py
tests/ui/test_launch.py`; `make web`; `openspec validate github-com-entry --strict`; the trial
archive of the settings; CI runs the rest (container tests included).
