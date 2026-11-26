## 1. The helper and the texts

- [x] 1.1 `src/lado/commit_authors.py`: `unsigned(paths, project_id=None)` (D1); `SET_HINT`
  and `RUNNING_KEEP`, `LADO_NOBODY`'s second line `SET_HINT` (D4); the module docstring names
  them. Check: unit tests of `unsigned` in `tests/test_commit_authors.py` (or the module's
  existing test file): nobody, git's own author, LADO's author, a repository on a server with
  an author.

## 2. The commands

- [x] 2.1 `cli._lado_author`: after a clear, when `_lado_author_line()` gives `LADO_NOBODY`,
  the last line is `RUNNING_KEEP` instead of `AUTHOR_RESTART` (AC-1). Check: a new test in
  `tests/test_cli_git_server.py`, `test_clearing_the_last_ladOs_author`; `NOBODY` there takes
  the new hint; `test_nobody_known` green.
- [x] 2.2 `cli.cmd_project_author`: the clear and the show judge the project's places with
  `unsigned` (D2) and print the "nobody else signs" or the "cannot commit in" line, the
  project's hint, and after a clear `RUNNING_KEEP` (AC-2, AC-3); somebody left: as now
  (AC-5). Check: new tests in `tests/test_cli.py` with an empty `git_config`: the clear and
  the show of `shop` nobody signs for; a project without repositories; `api` on a saved
  server with an author and `site` without a remote; the existing
  `test_project_author_set_shown_and_cleared` unchanged and green (it has git's author).
- [x] 2.3 `cli.cmd_git_server_author` with an address: the clear and the show say agents
  cannot commit there when LADO and git have none (D3), with `SET_HINT`, and after a clear
  `RUNNING_KEEP` (AC-4). Check: a new test in `tests/test_cli_git_server.py`; the existing
  `test_author_sets_shows_and_clears` gets a git config with an author (AC-5).
- [x] 2.4 A git config git cannot read, for the project's and the server's clear and show:
  one line, exit 1, the clear kept (D5, AC-6). Check: the parametrized test
  `test_a_git_config_git_cannot_read_is_said_in_one_line` extended to them.

## 3. Docs

- [x] 3.1 `docs/cli.md`: `lado project author` and `lado git-server author` (with and without
  an address) give the new lines and when. Check: read it.
- [x] 3.2 CHANGELOG.md, `## 0.49.0 (unreleased)`, Fixed: clearing a commit author that leaves
  nobody now says agents cannot commit and how to set one, instead of promising commits.
  Check: read it.

## 4. Regression run

- [x] 4.1 `make lint`, `make test`, `openspec validate commit-author-nobody-left --strict`,
  the trial archive; the pull request's CI green (AC-7).
