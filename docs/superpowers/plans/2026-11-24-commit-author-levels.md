# Commit authors on three levels: Implementation Plan

**Goal:** LADO's own commit author and a project's, kept in lado.db, set from Settings, the
project page and the CLI, given to agents and to LADO's own first commits by one order
(project → git server → LADO's → git's own); a fresh start without a terminal.

**Architecture:** `state` gets schema 44 (D1); a new module `commit_authors` holds the
levels, the checks and the author in effect (D2, D5); `git_servers.variables` lays LADO's
entries before the servers' and the project's after them (D3); `runtime` passes them, refuses
git < 2.31 and warns about author variables (D6, D7); `scratch`, `setup` and `projects` take
the author in effect for their first commit and refuse with the new hint (D4); `cli`,
`server`, `doctor` and the entrypoint follow (D8–D10); the web UI is built to the design
flow `ui-design/lad-312-ui` (D11).

**Tech Stack:** Python 3.10+ standard library, SQLite, git ≥ 2.31, pytest (`-n auto`, `-m
integration`, `-m ui`, `-m container`), React + TypeScript (vitest), Playwright.

**Spec:** `openspec/changes/commit-author-levels/` and
`docs/superpowers/specs/2026-11-24-commit-author-levels-design.md` (texts, the table of tests
per requirement, docs, the manual check). The screens: `ui-design/lad-312-ui`'s `spec` and
`mockup.html` as the human approved them at the flow's gate.

## Global Constraints

- Nothing is written into `~/.gitconfig`, the system config or a repository's `.git/config`;
  tests check those files unchanged (their bytes before and after).
- Tests set `GIT_CONFIG_GLOBAL` to a file of their own (or `/dev/null`) and
  `GIT_CONFIG_NOSYSTEM=1` where git's own author must be absent; never the developer's.
- The texts are the deltas', the design doc's and the flow spec's, word for word; another
  wording needs a reason in the build report.
- No author value in a log, a journal entry (`telemetry`) or `lado doctor`'s output.
- Schema: `SCHEMA_VERSION = 44`, `MIGRATIONS[43]`, `tests/agent_helpers.previous_schema`.
- CHANGELOG: a `## 0.49.0 (unreleased)` heading on top when missing (minor: schema, CLI, API).
- `make web-types` after the API models change; commit `web/openapi.json` and
  `web/src/api.gen.ts`.

## Review Focus

1. The order of the entries in `variables`: LADO's first, the servers' (with their includes)
   in between, the project's last; with no server and an author, the entries are still laid
   (today `variables` returns `{}` without a server). Tests in Task 3.
2. `agent_env.for_git` and LADO's network git get no author entry (D3). Test in Task 3.
3. `in_effect` and git agree: for every combination of levels the unit test compares
   `in_effect`'s answer with `git config --get user.name` run under the laid variables in a
   real repository. Test in Task 2/3.
4. A project session's worker and a session the supervisor proposes get the project's
   author (the session's project, not the folder's path). Test in Task 4.
5. The refusal's hint no longer depends on `LADO_CONTAINER`, and `LaunchSetup` no longer
   tells the container by the hint's text. Tests in Tasks 5 and 9.

## Tasks

### Task 1: storage, schema 44 (D1)

Files: `src/lado/state.py` (`COMMIT_AUTHOR_TABLE`, `PROJECTS_AUTHOR`, `MIGRATIONS[43]`,
`Author`, `commit_author()`, `set_commit_author(name, email)`, `clear_commit_author()`,
`set_project_author(id, name, email)`, `Project.author_name/author_email`),
`tests/agent_helpers.py`, `tests/test_state.py`.

- [ ] Test: a fresh db has no LADO author; set, read, set again (one row), clear; a project's
  author set and cleared, gone with the project's row; 43 → 44 keeps projects, servers and
  their authors, LADO and projects without one, `backups/lado.db.schema-43` there; the
  rollback by the backup.
- [ ] Implement; `make lint`, `uv run pytest -n0 tests/test_state.py`; commit.

### Task 2: the levels (D2, D5, D6)

Files: `src/lado/commit_authors.py` (new), `src/lado/git_servers.py` (`check_author` →
`commit_authors.check`, kept as a name), `tests/test_commit_authors.py`.

Interfaces — produces: `Author`, `text`, `check`, `lado`, `set_lado`, `clear_lado`,
`project`, `set_project`, `clear_project`, `entries`, `git_own(path)`,
`in_effect(path, project=None) -> InEffect(author, source)`, `author_variables(env)`.

- [ ] Test: `check`'s refusals unchanged (the git-servers cases moved or reused); set with
  git 2.30 on PATH refused with 2.31; `git_own` under `GIT_CONFIG_GLOBAL` of a test file,
  `/dev/null`, and in a repository with its own `user.name`; `in_effect` for: nothing,
  git's only, LADO's over git's (and the repository's own), a server's over LADO's (https,
  `git@`, two servers: the later by host), the project's over all; `author_variables`
  picks the four names only.
- [ ] Implement; commit.

### Task 3: the entries (D3)

Files: `src/lado/git_servers.py` (`variables(env, servers, authors=None, lado=None,
project=None)`), `tests/test_git_servers.py`.

- [ ] Test: no server, no author → `{}`; LADO's only → two entries and the count; LADO's,
  one server with an author, the project's → the order; with `GIT_CONFIG_COUNT=2` in `env`
  the numbering starts at 2; under the laid variables a real `git config --get user.name`
  answers as `in_effect` (Review Focus 3); `for_git` lays no `user.*` entry.
- [ ] Implement; commit.

### Task 4: the launch (D3, D6, D7)

Files: `src/lado/runtime.py` (`_ours`, `_check_commands`, `_git_server_warnings`),
`tests/test_runtime_git_servers.py`, `tests/test_runtime_projects.py`.

- [ ] Test: `_ours` of an agent of a session without a project has LADO's entries; of a
  project's session (supervisor, worker, a proposed session) the project's last; git 2.30
  refuses the launch naming 2.31 and the command that clears (LADO's; the project's); the
  warning `GIT_AUTHOR_EMAIL is set for w1: it wins over LADO's commit authors` for LADO's
  author, for the project's, for a server's, and for a project variable of that name; none
  without any author.
- [ ] Implement; commit.

### Task 5: LADO's own first commits (D4)

Files: `src/lado/scratch.py` (`author_problem(path, project=None)`, `NO_AUTHOR`,
`AUTHOR_HINT`, `make`'s `-c`), `src/lado/setup.py`, `src/lado/projects.py` (`add_new`
passes the project), `tests/test_scratch.py`, `tests/test_setup.py`,
`tests/test_project_repos.py`.

- [ ] Test: with `GIT_CONFIG_GLOBAL=/dev/null` and LADO's author the start makes the
  repository and the commit's `%an <%ae>`/`%cn <%ce>` is LADO's; a project's author for a
  project's repository; git's own when neither; nobody → the refusal's text and hint (also
  with `LADO_CONTAINER=1`), nothing made; git's config files unchanged.
- [ ] Implement; commit.

### Task 6: the command line (D8)

Files: `src/lado/cli.py` (`cmd_git_server_author` with an optional address,
`cmd_git_server_list`, `cmd_project_author`, `project show`), `src/lado/git_servers.py`
(`AUTHOR_CLEARED`), `tests/test_cli_git_server.py`, `tests/test_cli.py`.

- [ ] Test: every output of the design doc's command-line section word for word; half an
  author exit 2; unknown project exit 1; inside an agent (`LADO_AGENT=w1`) LADO's author and
  `lado project author` refused, a server's still allowed; list's first line with and
  without servers.
- [ ] Implement; commit.

### Task 7: doctor and the container (D10)

Files: `src/lado/doctor.py`, `docker/entrypoint.sh`, `docker/compose.yaml` (header),
`tests/test_doctor.py`, `tests/container/test_access.py`.

- [ ] Test: the three lines of `git author`, never the name or email; the container: the new
  log line without the variables; a clean container (no `LADO_GIT_NAME`) with `PUT
  /api/git-author` and `POST /api/projects/{id}/repos` from scratch makes a commit by Ann
  Lee while `git config --global user.name` prints nothing.
- [ ] Implement; `make docker` then `uv run pytest -m container -n0
  tests/container/test_access.py -k author` (or leave it to CI and say so); commit.

### Task 8: the server API (D9)

Files: `src/lado/server/models.py`, `src/lado/server/git_entries.py`,
`src/lado/server/app.py` (the projects' routes), `src/lado/server/launch.py`,
`tests/test_server_git_servers.py`, `tests/test_server_projects.py`,
`tests/test_server_launch.py`, `web/openapi.json`, `web/src/api.gen.ts`.

- [ ] Test: `GET /api/git-servers` with LADO's author, git's own, the variables; `PUT` /
  `DELETE /api/git-author` and the refusal under `email`; the routes under the token;
  `GET /api/projects/{id}` with the author and each repository's `commit_author`; `PUT` /
  `DELETE /api/projects/{id}/author`; the scratch and setup infos with the new text and
  hint, the project's author counted for a project's target.
- [ ] Implement; `make web-types`; `make web`; commit.

### Task 9: the web UI (D11)

Files: `web/src/GitServers.tsx`, `web/src/Projects.tsx` (or `ProjectAuthor.tsx`), a shared
`AuthorMissing` component, `web/src/LaunchWhere.tsx`, `web/src/LaunchSetup.tsx`,
`web/src/Launch.tsx`, `web/src/ProjectRepos.tsx`, `web/src/styles.css`, their `*.test.tsx`,
`tests/ui/test_commit_author_pages.py` (new), `tests/ui/test_git_servers_section.py`,
`tests/ui/test_project_page.py`.

- [ ] Vitest: each state, text and accessible name of the flow's spec (Settings A-screens,
  project B-screens, refusal C-screens); `?author` opens the form once and is dropped; the
  window checks again on focus; one result line and one form at a time.
- [ ] UI e2e: the main scenario (New empty folder with nobody known → Set it in Settings ↗
  in a new tab → save → back → the note goes → Create and start; the repository's first
  commit is Ann Lee's); the project's author set and removed with Undo; a phone width
  without horizontal scroll; screenshots of each changed screen as run artifacts.
- [ ] Implement; `make web`; `uv run pytest -m ui -n auto <files>`; commit.

### Task 10: end to end with the fake agent

Files: `tests/integration/test_commit_author_order.py` (new),
`tests/integration/test_git_server_author.py` (the cases whose `THEN` changed).

- [ ] Test: an agent with `GIT_CONFIG_GLOBAL=/dev/null` and LADO's author commits in a
  repository without a remote as Ann Lee; with a server's author over LADO's in a clone of
  `https://git.test:8443/…`; a project session's agent in a repository on that server with
  the project's author; the repository's own `user.name` loses to LADO's; `lado start
  --new` with LADO's author alone; after clearing LADO's author and a restart, git's own;
  the `GIT_AUTHOR_EMAIL` warning in the launch notes. Git's config files unchanged.
- [ ] `uv run pytest -m integration -n auto tests/integration/test_commit_author_order.py
  tests/integration/test_git_server_author.py`; commit.

### Task 11: docs and CHANGELOG

Files: `docs/cli.md`, `docs/design/ui.md`, `docs/design/projects.md`,
`docs/design/agents.md`, `docs/design/modules.md`, `CHANGELOG.md`, `AGENTS.md` (the module
line of `commit_authors.py` in Layout).

- [ ] Write; `uv run pytest -n0 tests/test_agents_md.py`; commit.

### Task 12: the regression run

- [ ] `make lint`; `make test`; the integration files of Task 10 with `-m integration`; the
  UI files of Task 9 with `-m ui`; `make web`; `openspec validate commit-author-levels
  --strict`; the trial archive of the settings' Checks. Report numbers in `build-report`.
