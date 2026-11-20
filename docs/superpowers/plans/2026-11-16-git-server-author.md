# The commit author of a git server: Implementation Plan

**Goal:** a saved git server may carry a commit author (name and email); agents commit to its
repositories with it as author and committer, elsewhere as before; set, shown and cleared by
`lado git-server author` and in Settings → Git servers; nothing global changes.

**Architecture:** schema 42 adds two columns (D4); `git_servers.check_author`, `set_author`,
`clear_author` (D5) shared by `cli.py` and `server/git_entries.py`; `git_servers.author_entries`
and `variables(…, authors=)` give `includeIf hasconfig` entries (D1) pointing to files the
launch writes in the agent's config folder (D3); `runtime._check_commands` refuses git older
than 2.36 where an author is set (D6) and the launch warns of `GIT_AUTHOR_*` (D8); the page's
✎ form (D10).

**Tech Stack:** Python 3.10+ (standard library), FastAPI/pydantic (existing), React +
TypeScript (existing), pytest (`-n auto`, `-m integration`, `-m ui`, `-m smoke`), vitest,
Playwright's Chromium, git ≥ 2.36 in the test environments (CI and the image have 2.39).

**Spec:** `openspec/changes/git-server-author/` (proposal, deltas, `design.md` D1–D10) and
`docs/superpowers/specs/2026-11-16-git-server-author-design.md` (lines, tests per requirement,
docs, manual check). Mockup: run artifact `mockup-commit-author.html`, option 1.

## Global Constraints

- Never write `~/.gitconfig`, the XDG git config or the system config, nor a repository's
  `.git/config`: only process environment and files under `LADO_HOME` (agents' config
  folders). Every integration test checks the fake HOME's `~/.gitconfig` and the
  `GIT_CONFIG_SYSTEM` file byte for byte.
- The author file holds only `[user] name` and `email`: no token, no path (#7167).
- The globs cover exactly the forms `server_for` takes (D1), the `git@` form included; the
  integration test clones by `git@`.
- git 2.36 only where an author is set; without one, nothing about launches or `check_git`
  changes.
- One schema migration (41 → 42) with `tests/agent_helpers.previous_schema` updated; CHANGELOG:
  extend the 0.48.0 git servers entry, no new version.
- Nothing in code, docs, specs or the UI names the work's stages or `docs/epics/`.
- The pull request carries the design doc's manual check from the start.

## Review Focus

1. A glob that misses a form or matches another host (`git@gitlab.corp.ru:` vs
   `git@gitlab.corp.ru.evil:`; `https://corp.ru/gitlab` vs `https://corp.ru/gitlabX`): task 2's
   tests.
2. A name or email that breaks the config file's syntax (`"`, `\`, `#`, `;`): task 2's tests
   read the file back with `git config --file`.
3. The author lost on a second `add` of the server: task 1's test.

## Task 1: Storage (D4)

**Files:** `src/lado/state.py`, `tests/agent_helpers.py`, `tests/test_state.py`.

- [ ] Write the failing tests: `test_schema_41_gets_author_columns_and_keeps_the_servers`
  (a schema-41 lado.db with a server migrates to 42, the server kept with no author,
  `backups/lado.db.schema-41` holds the old table), `test_set_git_server_author` (set, read
  back, clear, unknown id → None), `test_a_git_server_saved_again_keeps_its_author`,
  `test_the_schema_41_backup_put_back_has_no_author`.
- [ ] Run `uv run pytest tests/test_state.py -n0 -k "author or schema_41"`: they fail.
- [ ] Implement: `SCHEMA_VERSION = 42`, the columns in `GIT_SERVERS_TABLE`'s successor for a
  new database, `MIGRATIONS[41]`, `GitServer.author_name/author_email`, `_git_server`,
  `set_git_server_author`; update `previous_schema`.
- [ ] Run the tests: pass; `make test`: the schema tests elsewhere still pass.
- [ ] Commit `Keep a git server's commit author in lado.db (LAD-291)`.

## Task 2: The rules (D1, D3, D5, D6)

**Files:** `src/lado/git_servers.py`, `src/lado/runtime.py` (`GIT_AUTHOR_MIN`),
`tests/test_git_servers.py`.

- [ ] Failing tests: `check_author` (each refusal, its field, trimming, 256);
  `author_entries` for `https://gitlab.corp.ru`, `https://git.test:8443`,
  `https://corp.ru/gitlab`, `http://[::1]:8080`: the six globs, the value the given path;
  each glob checked with real git (`git -c includeIf… config user.name` in a temp repo per
  remote form, and the two near-miss hosts of Review Focus 1 not matching); `variables` with
  `authors` puts them after the server's five entries, without `authors` is as before;
  `write_author_file` (`"`, `\`, `#`, `;` round-trip through `git config --file … user.name`,
  mode 600, no other key); `set_author`/`clear_author` (unknown server refused; set calls
  `check_author_git`; clear needs no git); `check_author_git` with a fake git 2.34.1 / 2.36.0.
- [ ] Run: fail. Implement. Run: pass.
- [ ] Commit `Give agents a git server's commit author by the repository's remote (LAD-291)`.

## Task 3: The launch (D2, D3, D6, D8)

**Files:** `src/lado/runtime.py`, `tests/test_runtime_git_servers.py`.

- [ ] Failing tests: a launch with an author writes `<config dir>/git-authors/<id>.gitconfig`
  and the agent's env has the entries; `agent_env.for_git` has none; `_check_commands`
  refuses git 2.34.1 with an author (the line names 2.36 and `--clear` with the address),
  goes without an author; `GIT_AUTHOR_EMAIL` in the layers → the warning in `Started.warnings`
  and in a spawn's held lines; none without an author.
- [ ] Run: fail. Implement in `_ours`, `_check_commands`, the warnings. Run: pass.
- [ ] Commit `Refuse an old git and name GIT_AUTHOR variables where a commit author is set (LAD-291)`.

## Task 4: End to end (integration, smoke)

**Files:** `tests/integration/test_git_server_author.py` (new), `tests/smoke/test_codex_git_server.py`.

- [ ] Integration (fake agent, `fake_git_server`, a fake HOME with its own `~/.gitconfig`
  author and a `GIT_CONFIG_SYSTEM` file): server saved with token and author; the agent clones
  by `https://…` and by `git@<host>:team/app.git` (remote stays `git@`), commits, pushes → the
  server's repository has the commit with author and committer = the server's; a repo with a
  remote on `https://other.example/x.git` and one with none → `~/.gitconfig`'s author; a repo
  with a local `user.name` → the server's; the agent's author file is exactly the `[user]`
  section, no token canary, no path; clear the author, restart the agent → the human's
  author; after the agent stops its author file is gone; `~/.gitconfig` and the system file
  unchanged.
- [ ] Smoke: inside `codex sandbox`, a repository with a `git@` remote on the saved server
  commits with the server's author (the sandbox reads the agent's author file).
- [ ] Run `uv run pytest -m integration -n auto tests/integration/test_git_server_author.py`:
  pass. The smoke test: "written, run in CI" unless the CLI is here.
- [ ] Commit `Test a git server's commit author end to end (LAD-291)`.

## Task 5: The command (D9)

**Files:** `src/lado/cli.py`, `tests/test_cli_git_server.py`.

- [ ] Failing tests per the design doc's table (set, show, clear, clear with none, unknown
  exit 1, bad address exit 2, half author exit 2, `--clear` with a value exit 2, list's
  `AUTHOR`, `--help` names the options).
- [ ] Run: fail. Implement `cmd_git_server_author` and the column. Run: pass.
- [ ] Commit `Add lado git-server author (LAD-291)`.

## Task 6: The server API (D10)

**Files:** `src/lado/server/models.py`, `src/lado/server/git_entries.py`,
`src/lado/server/app.py`, `web/openapi.json`, `web/src/api.gen.ts`,
`tests/test_server_git_servers.py`.

- [ ] Failing tests: PUT sets and answers `{server, line}`, DELETE clears; refusals 400 with
  `field` `name`/`email`/""; unknown host 400; `GET /api/git-servers` carries the author.
- [ ] Implement; `make web-types`. Run the tests and `make web`: pass.
- [ ] Commit `Set and clear a git server's commit author through the server API (LAD-291)`.

## Task 7: The page (D10)

**Files:** `web/src/GitServers.tsx`, `web/src/api.ts`, `web/src/GitServers.test.tsx`,
`web/src/styles.css` (only if a rule is missing), `tests/ui/test_git_servers_section.py`.

- [ ] Failing vitest: the third line; ✎ opens the form with the saved values and focus on
  Name; one panel at a time with 🗑; Save author off until both filled and changed; Remove
  author only when saved; Esc cancels; the refusal under its field; the done lines.
- [ ] Implement to mockup option 1. `make web`: pass.
- [ ] UI e2e: set an author (row line, `lado git-server list`), a wrong email under Email,
  remove it; screenshots at 1440 px light and dark and 390 px for the build report.
  `uv run pytest -m ui tests/ui/test_git_servers_section.py`: pass.
- [ ] Commit `Set a git server's commit author in Settings → Git servers (LAD-291)`.

## Task 8: Docs and the pull request

- [ ] `docs/cli.md`, `docs/design/ui.md`, `docs/design/agents.md`, `docs/design/modules.md`,
  CHANGELOG.md's 0.48.0 entry (design doc, Docs). `uv run pytest tests/test_agents_md.py`.
- [ ] Commit `Document a git server's commit author (LAD-291)`.
- [ ] Regression run (design doc, Regression) and the openspec checks of `.lado/sdlc.md`.
- [ ] The pull request's description with the manual check of the design doc.
