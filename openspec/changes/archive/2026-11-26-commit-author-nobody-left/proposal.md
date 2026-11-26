Task: LAD-313

## Why

Symptom (found in the manual check of LAD-312, PR #357): on a LADO without a git author of
its own and with git knowing none, `lado git-server author --clear` says `LADO has no commit
author and git knows none: agents cannot commit.` and then `Agents started from now on commit
so; restart running agents to give it to them.`; `lado project author shop --clear` says
`Project shop has no commit author now: its agents commit as LADO's or a git server's.` and the
same restart line. Agents started after that cannot commit, and the human is not told.

Cause: LAD-312 adds the restart line after every change of an author without asking whether
anybody is left to sign the commits, and the project's and a server's lines after a clear or
on a show are fixed texts naming a fallback that may be empty. The CLI already has the one
answer (`lado.commit_authors.in_effect`, source `none`) but asks it only for LADO's own line.

Options weighed:

- A (taken): after a clear and on a show, the CLI asks `in_effect` for each place the author
  covers (the project's repositories, else its folder; for a server and LADO, outside any
  repository) and, when nobody signs there, says so, names how to set one (Settings → Git
  servers or the command) and replaces the restart promise with a line that running agents
  keep the author they started with. Long-term cost: one small helper over `in_effect`, the
  texts as constants next to the existing ones; the same rule for the three levels.
- B: drop the restart line whenever an author is cleared. Cheaper, but the project's and the
  server's lines still name a fallback that is not there.
- C: refuse a clear that leaves nobody. It takes from the human a choice that is theirs (they
  may set git's own author next) and makes a clear depend on git.

## What Changes

- `lado git-server author --clear` (LADO's author) with nobody left: its last line is
  `Running agents keep the author they started with until they restart.` instead of the
  restart promise. The hint line of "nobody known", here and in the show, becomes `Set one in
  Settings → Git servers, or run: lado git-server author --name "Your Name" --email
  you@example.com`.
- `lado project author <id> --clear` and the show without options: when nobody signs the
  commits in any repository of the project (none: its folder), `Project <id> has no commit
  author now, and nobody else signs its agents' commits: they cannot commit.` (the show
  without `now`), the hint `Set one: lado project author <id> --name "Your Name" --email
  you@example.com, or LADO's in Settings → Git servers.`, and after a clear the running-agents
  line. When nobody signs in some of its repositories only: `Project <id> has no commit
  author now: its agents cannot commit in <repo>, <repo> (nobody signs there).`, the hint and
  the running-agents line.
- `lado git-server author <address> --clear` and its show: when LADO has no author and git
  knows none, `Agents cannot commit to <address> now: it has no commit author, LADO has none
  and git knows none.` (the show: `<address> has no commit author, LADO has none and git
  knows none: agents cannot commit there.`), LADO's hint line, and after a clear the
  running-agents line.
- Where somebody is left, every output stays as it is.
- docs/cli.md says so; the commit-authors spec gets a requirement for it and the new hint.
- A patch: a fix users see, a CHANGELOG.md line under `## 0.49.0 (unreleased)`, Fixed.

## Scope

- `src/lado/cli.py` (`cmd_project_author`, `_lado_author`, `cmd_git_server_author`),
  `src/lado/commit_authors.py` (texts, the helper), `src/lado/git_servers.py` (a server's
  texts), their unit tests in `tests/test_cli.py` and `tests/test_cli_git_server.py`,
  docs/cli.md, CHANGELOG.md.

## Out of scope

- The UI: Settings → Git servers already shows `⚠ Nobody: agents cannot commit` and the
  project's page the source `none` per repository (LAD-312); the API's `line` of
  `DELETE /api/git-author` stays `LADO has no commit author now.`, as the page shows the
  author block under it.
- Refusing a clear that leaves nobody (option C): the choice is the human's.
- The exit status: a clear that leaves nobody is done and exits 0, as now.
- `lado doctor`: it already warns `no LADO commit author and no user.name or user.email:
  agents cannot commit`.
- `GIT_AUTHOR_*` variables of the agents' environment, which could sign where LADO sees
  nobody: the launch warns of them (LAD-312); the CLI's lines speak of LADO's and git's
  authors, as `in_effect` does.

## Acceptance criteria

- AC-1: With git knowing no author and LADO's author set, `lado git-server author --clear`
  prints `LADO has no commit author now.`, the "nobody known" line, `Set one in Settings → Git
  servers, or run: lado git-server author --name "Your Name" --email you@example.com` and
  `Running agents keep the author they started with until they restart.`, and exits 0; no
  line says agents commit.
- AC-2: With git and LADO knowing no author and the project `shop` (repository `frontend`,
  no remote) having one, `lado project author shop --clear` prints the project's "nobody
  else signs" line, its hint and the running-agents line, exit 0; `lado project author shop`
  then prints the show's line and the hint.
- AC-3: When only some repositories of the project have nobody (another one's remote is on a
  saved server with an author), the clear's line names exactly the repositories with nobody.
- AC-4: With git and LADO knowing no author, `lado git-server author <address> --clear` and
  the show of that server say agents cannot commit there and give the hint; the clear ends
  with the running-agents line.
- AC-5: Where an author is left (git's own, LADO's, a server's), every output is unchanged,
  the restart line included.
- AC-6: A git that cannot read its config is said in one line, exit 1, after the clear's
  first line, as LADO's clear does now.
- AC-7: `make lint`, `make test`, `openspec validate commit-author-nobody-left --strict` and
  the trial archive pass; the pull request's CI is green.

## Impact

- Users of the CLI: a clear or a show that leaves agents unable to commit says so and how to
  fix it. The UI and the API are unchanged.
- Specs: commit-authors.
