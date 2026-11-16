Task: LAD-291

## Why

A saved git server gives agents its token, but their commits there still carry the author of
the human's own git settings (`~/.gitconfig`, or `LADO_GIT_NAME`/`LADO_GIT_EMAIL` in LADO's
image): a personal email ends up in a company GitLab's history, and a server whose push rules
check the author's email refuses the push. The human needs "commit to this server as this
name and email" without touching the global or system git config, and an agent may work with
repositories of several servers at once.

Root cause: git takes the author from `user.name`/`user.email` by scope (system, global,
local, command), never by the remote a repository talks to; LADO gives agents no author of
its own. Options weighed (cost over the coming work: "Check", github.com in the list, the
company certificate, `glab`):

- A (taken): per saved server with an author, `includeIf "hasconfig:remote.*.url:<pattern>"`
  entries among the `GIT_CONFIG_*` variables LADO already lays over an agent's environment,
  each pointing to a file in the agent's own config folder that holds only `[user] name` and
  `email`. git picks the author per repository by the address of its remotes, so one agent
  commits to each server's repositories as that server's author and elsewhere as before. The
  condition exists from git 2.36; an older git skips it silently, so LADO refuses it where an
  author is set (the human's answer to #7165 q1).
- B: `GIT_AUTHOR_*`/`GIT_COMMITTER_*` in the agent's environment when its session's repository
  is on a listed server. Rejected: every repository the agent touches, of any host, would get
  that author; it cannot serve an agent with repositories of two servers.
- C: `user.name`/`user.email` written into each worktree's own config. Rejected: it writes the
  human's repositories (not under `LADO_HOME`), misses repositories the agent clones itself,
  and leaves the setting behind after the author is removed.

## What Changes

- A saved git server may have a **commit author**, a name and an email together, kept in
  lado.db in the server's row (schema 42); adding the same server again keeps it.
- `lado git-server author <address> --name <name> --email <email>` sets it,
  `lado git-server author <address> --clear` removes it, `lado git-server author <address>`
  shows it; `lado git-server list` gets a last column `AUTHOR` (`-` for none).
- Settings → Git servers: ✎ `Commit author` on a server's row opens a form under the row
  (Name, Email, Save author, Remove author when one is set, Cancel); a row with an author has
  a third line `commits as <name> <<email>>` (mockup `mockup-commit-author.html`, option 1).
- An agent launched while a server has an author commits to a repository with a remote on
  that server (`https://host[:port]/…`, the same with a user, `git@host:…`,
  `ssh://git@host[:22]/…`) with that name and email as author and committer; to any other
  repository as before. The server's author wins over a repository's own `user.name`; the
  variables `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME` and
  `GIT_COMMITTER_EMAIL` of the agent's environment win over it, and the launch warns so.
- git 2.36 or newer is needed where an author is set: setting one is refused with an older
  git on LADO's PATH, and a launch is refused while an author is set and the agents' git is
  older. Without an author, 2.31 stays enough.
- Docs: `docs/cli.md`, `docs/design/ui.md`, `docs/design/agents.md`,
  `docs/design/modules.md`, CHANGELOG.md's 0.48.0 entry of git servers.

## Scope

`src/lado/state.py` (schema 42, the author columns, `set_git_server_author`),
`src/lado/git_servers.py` (the author's checks, the include entries and files, the git 2.36
check), `src/lado/runtime.py` (the launch: files in the agent's config folder, the refusal,
the warning), `src/lado/cli.py` (`lado git-server author`, list's column),
`src/lado/server/git_entries.py`, `src/lado/server/app.py`, `src/lado/server/models.py`,
`web/src/GitServers.tsx`, `web/src/styles.css` if needed, `web/openapi.json`,
`web/src/api.gen.ts`, `tests/agent_helpers.py` (`previous_schema`), tests (unit, integration,
smoke, vitest, UI e2e), the docs above.

## Out of scope

- "Check" of a saved server, `lado doctor`'s servers, clone hints and the small things of the
  page from the last review: the next task of the same work.
- github.com in the list, the company certificate, `glab`: later tasks of the same work.
- ssh keys and commit signing (GPG or ssh): outside this work.
- The author in the Add server form: the human's answer to #7165 q4; the form stays as it is,
  the author is set on the saved row.
- An author for LADO's own git (kits, packs, clones): LADO commits nothing to a server's
  repository.
- git older than 2.36 with an author (an environment-variable fallback for the session's
  repository): the human's answer to #7165 q1; refused loudly instead.
- Choosing between two listed servers' authors in one repository (remotes on both): the
  server later in the list by host wins, documented (#7165 q3).
- Commits made before a repository has a remote carry the usual author (#7165 q3).
- A half author (a name without an email or the other way round): the human's answer to
  #7165 q5; both or none.
- Telling running agents of a change: they get the author at their launch, as the token.

## Impact

- Minor version: a CLI command, server API and a schema migration (41 → 42); 0.48.0 is
  already the next minor (unreleased), so no further bump.
- Way back: a rollback restores `backups/lado.db.schema-41`; the authors are gone with it,
  and the author files live only in agents' config folders, written anew at each launch and
  removed when the agent stops, so none stays in use.
- A launch with an author set and git older than 2.36 is refused (new refusal).
