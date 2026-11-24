Task: LAD-312

## Why

The only commit author the UI sets today is a git server's, and it applies only in
repositories with a remote on that server. A new project from scratch has no remote, so LADO
looks at git's own `user.name`/`user.email` and, without them, refuses the start with a
terminal command (`git config --global …`; in LADO's container: variables in `.env` and a
restart). A person without a terminal cannot start a project, and LAD-311 (the first-run
guide) has no field to point its step "Git" at.

Root cause: LADO keeps no author of its own. git takes the author from its config scopes
(system, global, local, command) and from `GIT_AUTHOR_*`; LADO adds a server's author through
`includeIf hasconfig:remote…` entries of the command scope, so an author exists only where a
repository has a remote on a server with one.

Options weighed (cost over the coming work: LAD-311's guide, projects that outlive
sessions, a LADO manager running several instances):

- A (taken): LADO keeps a general author and a project's author in lado.db and gives them to
  agents as plain `user.name`/`user.email` entries among the `GIT_CONFIG_*` variables it
  already lays over an agent's environment: LADO's author first, the servers' conditional
  includes after it, the project's author last, so the later wins. LADO's own first commits
  (a fresh start, a folder's set-up, a project's repository from scratch) take the same
  author. One source of truth (lado.db), nothing written outside `LADO_HOME`, neutral to the
  agent CLI.
- B: write LADO's author into the human's `~/.gitconfig` (`git config --global`).
  Rejected: AGENTS.md's "never touch the user's global config"; in the container the home
  volume would carry it, and the UI could not tell LADO's author from the human's.
- C: write the project's author into each repository's `.git/config`. Rejected: every
  worktree of a repository shares that file, a repository cloned by hand into the project
  misses it, and the setting stays behind after the author is cleared or the project is
  deleted.
- D: `GIT_AUTHOR_*`/`GIT_COMMITTER_*` in the agent's environment. Rejected: they win over
  every config, so a server's author could no longer win in its repositories.

## What Changes

- **LADO's author**: a commit author of the whole LADO, name and email together, kept in
  lado.db (schema 44). It is set and cleared on Settings → Git servers (a block of its own
  above the servers) and by `lado git-server author` without an address. The page shows the
  author agents commit as now: LADO's, the human's own git config's, or none ("agents cannot
  commit").
- **A project's author**: optional, set and cleared on the project page and by `lado project
  author <id>`; shown by `lado project show`; it goes with the project.
- **A git server's author**: as today, optional; on the page it becomes less visible.
- **Priority**: project → git server → LADO's author → the human's own git config (global,
  system and the repository's `.git/config`). LADO's authors win over every git config file,
  as a server's does today (#8082/#8086); `GIT_AUTHOR_*`/`GIT_COMMITTER_*` of the agent's
  environment win over all, and the launch warns when any LADO author applies.
- **LADO's own commits**: a fresh start (`lado start --new`, New session → New empty folder),
  a plain folder's set-up and a project's repository from scratch commit as the author an
  agent of that place would get (the project's, else LADO's, else git's own), and are
  refused only when there is none. The refusal no longer sends the human to a terminal or to
  `.env`: it names Settings → Git servers and `lado git-server author --name … --email …`;
  the New session window and Add repository show a link to that page and Check again, no
  fields of their own (#8080).
- `lado doctor`'s `git author` is `ok` when LADO's author is set; its hint names the page
  and the command. The container's log warning names the page too.
- The UI of the three places follows the design flow `ui-design/lad-312-ui` (screens,
  texts and the less visible server's and project's author).
- Docs: `docs/cli.md`, `docs/design/ui.md`, `docs/design/projects.md`,
  `docs/design/agents.md`, `docs/design/modules.md`, `docker/compose.yaml`'s header,
  CHANGELOG.md.

## Scope

`src/lado/state.py` (schema 44: table `commit_author`, columns `author_name`,
`author_email` on `projects`), a new module `src/lado/commit_authors.py` (the levels, the
author in effect, the entries), `src/lado/git_servers.py` (`variables` with LADO's and the
project's entries), `src/lado/runtime.py` (the launch: entries, the 2.31 refusal, the
warning), `src/lado/scratch.py`, `src/lado/setup.py`, `src/lado/projects.py` (the author
check and LADO's own commits), `src/lado/doctor.py`, `src/lado/cli.py`,
`src/lado/server/` (`git_entries.py`, the projects' routes, `launch.py`, `models.py`,
`app.py`), `web/src/GitServers.tsx`, `web/src/Projects.tsx` (or a new `ProjectAuthor.tsx`),
`web/src/LaunchWhere.tsx`, `web/src/LaunchSetup.tsx`, `web/src/ProjectRepos.tsx`,
`web/openapi.json`, `web/src/api.gen.ts`, `docker/entrypoint.sh`, `tests/agent_helpers.py`
(`previous_schema`), tests (unit, integration, vitest, UI e2e, container), the docs above.

## Out of scope

- The first-run guide and its spotlight on the field: LAD-311, which this task unblocks.
- Fields for the author inside the New session window or Add repository: the human's answer
  #8080; a link to Settings instead.
- An author of a session or of an agent: no one asked; a project or a server covers the
  cases named.
- Letting a repository's own `.git/config` author win over LADO's: the human's answer
  #8086 (it matters little; the server's and the project's must count).
- Moving `LADO_GIT_NAME`/`LADO_GIT_EMAIL` of the container into LADO's author: they stay a
  git config level, written at the container's start (recommended to the human in #8082,
  not changed by #8086).
- Making a server's author human-only in the CLI: it is today any caller's; this change
  makes only LADO's author human-only (it reaches every repository).
- Commit signing (GPG, ssh), and `GIT_AUTHOR_*` set as a project variable: such a variable
  already wins over every config, as an outside one does, and the launch names it.
- Telling running agents of a change: they get the author at their launch, as today.

## Impact

- Minor version: a schema migration (43 → 44), CLI (`lado git-server author` without an
  address, `lado project author`) and API changes. CHANGELOG gets a `0.49.0 (unreleased)`
  heading unless one is there.
- Way back: a rollback restores `backups/lado.db.schema-43`; LADO's and the projects'
  authors are gone with it, nothing of them is written outside lado.db.
- A launch with LADO's or a project's author set and the agents' git older than 2.31 is
  refused (a new refusal; git servers already need 2.31).
