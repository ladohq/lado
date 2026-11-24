## Context

`lado.git_servers.variables` lays `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_<n>`/`GIT_CONFIG_VALUE_<n>`
over an agent's environment at its launch (`runtime._ours`): per saved server its credential
entries, its ssh rewrites and, for a server with a commit author, `includeIf
"hasconfig:remote.*.url:<glob>".path` entries pointing to a file of the agent's config folder
that holds only `[user] name` and `email` (change `git-server-author`, LAD-291). Without a
saved server it lays nothing. Entries of the command scope win over the system, global and
local configs; within the command scope the later entry wins; `GIT_AUTHOR_*` and
`GIT_COMMITTER_*` win over every config.

LADO's own commits: `scratch.make` (a fresh start, `lado start --new`, New session → New
empty folder, a project's repository from scratch through `projects.add_new`) and
`setup.make` (a plain folder's set-up) commit with git's own author, after
`scratch.author_problem(path)` asked `git config --get user.name|user.email` in the target's
nearest existing folder. The UI shows that problem (`ScratchInfo.author`, `SetupInfo.author`)
with the hint `git config --global …`, or in the container the `.env` text (`LaunchSetup`
tells the container by the hint's text). `lado doctor`'s `git author` asks the same from `/`.

A session refers to its project (`sessions.project`); an agent's environment is built from
layers, the project's variables among them (`runtime.agent_layers(project)`).

The human's answers: three levels, all in the UI, priority project → server → LADO's →
git's own, stored in LADO (task, 24.11.2026); no extra fields in the New session window, a
link to Settings (#8080); the server's and the project's author less visible (#8080); the UI
through the design flow `ui-design/lad-312-ui` (#8080); a repository's own `.git/config`
author matters little, the server's and the project's must count (#8086).

## Goals / Non-Goals

Goals: LADO's and a project's commit author kept in lado.db, set from the UI and the CLI,
given to agents and to LADO's own first commits by the one priority rule; a fresh start
without a terminal. Non-goals: the proposal's Out of scope.

## Decisions

### D1. Storage: lado.db, schema 44

One table for LADO's author, at most one row:

```sql
CREATE TABLE IF NOT EXISTS commit_author (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL,
    email TEXT NOT NULL
)
```

and two columns on `projects`: `author_name TEXT`, `author_email TEXT` (both or neither, as
on `git_servers`). Migration 43 → 44 adds them (`MIGRATIONS[43]`), `SCHEMA_VERSION = 44`,
`tests/agent_helpers.previous_schema` updated. Functions: `state.commit_author() ->
Author | None`, `state.set_commit_author(name, email)`, `state.clear_commit_author()`,
`state.set_project_author(id, name | None, email | None) -> Project | None`; `state.Project`
gets `author_name`, `author_email`. A project's row going takes its author with it; a
rollback to `backups/lado.db.schema-43` loses both kinds, nothing else holds them. Rejected:
a key-value settings table (only what is used: one author), a file under `LADO_HOME` (a
second store beside lado.db).

### D2. One module for the levels: `lado.commit_authors`

`git_servers.py` is already 1600 lines; the levels are not a server's. The new module holds:

- `Author(name, email)` and `text(author) -> "<name> <<email>>"`;
- `check(name, email)`: `git_servers.check_author` moved here unchanged (its refusals keep
  their fields), `git_servers.check_author` kept as a name for it;
- `lado() / set_lado(name, email) / clear_lado()` and `project(id) / set_project(id, name,
  email) / clear_project(id)`: the rules over `state` (checked, git 2.31 on LADO's PATH for
  a set, D6);
- `entries(author) -> [("user.name", name), ("user.email", email)]`;
- `in_effect(place) -> InEffect(author | None, source)` with `source` one of `project`,
  `server`, `lado`, `git`, `none` (D5);
- `git_own(path) -> Author | None`: git's own `user.name`/`user.email` read where `path`'s
  nearest existing folder is, LADO's entries left out (the look `scratch.author_problem`
  has today).

### D3. Agents: plain entries before and after the servers'

`git_servers.variables(env, servers, authors=None, lado=None, project=None)`: LADO's author's
two entries first, then each server's entries as today (its includes after its own), then the
project's two entries; nothing at all only when there is no server and neither author. The
later entry wins in the command scope, so a project's author wins over a server's include and
a server's over LADO's; every one of them wins over the system, global and local configs (the
human's answer #8086), and the `GIT_AUTHOR_*` variables win over all. No file is written for
LADO's or the project's author: a plain entry carries the value (`check` refuses line breaks
and `<`, `>`; `GIT_CONFIG_VALUE_<n>` takes any other text as is). `runtime._ours` passes
`commit_authors.lado()` and the session's project's author; `agent_env.for_git` (LADO's
network git: kits, packs, clones) passes neither, as it passes no server's author today.

### D4. LADO's own first commits take the place's author

`scratch.author_problem(path, project=None)` becomes: none when `commit_authors.in_effect`
for that place has an author; otherwise the refusal `no_author` with the text `nobody signs
the agents' commits: LADO has no commit author and git has no user.name or user.email` and
one hint everywhere, the container too: `Set the commit author in Settings → Git servers, or
run:` with the command `lado git-server author --name "Your Name" --email you@example.com`.
`scratch.make` and `setup.make` commit with `-c user.name=<name> -c user.email=<email>` of
the author in effect when its source is `project` or `lado` (a new repository has no remote,
so no server's applies), and as today when it is `git`. `projects.add_new` passes its
project; `lado start --project … --new` does not exist, so a fresh start outside a project
passes none. The UI's `LaunchSetup` no longer tells the container by the hint's text.

### D5. The author in effect, for the page and the checks

`in_effect` follows git's own order without running a commit:

1. the project's author, when the place is a project's (its repositories, a new one);
2. for a repository: each remote URL in its config (`git config --get-regexp
   '^remote\..*\.url$'`), the saved server `git_servers.server_for` finds for it; of those
   with an author, the last by host (`git_servers.variables` lays servers by host, so the
   later include wins, as the living spec of git-servers says);
3. LADO's author;
4. `git_own(path)`;
5. none.

It answers the page's lines (LADO's block: LADO's, else git's own, else none; a project's
repositories, each with its author and source) and the refusals of D4. Apart from the order,
`author_variables(layers)` names those of `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`,
`GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL` the agents' environment holds (the layers the
server already reads for the logins, `server.launch.environment`, with the project's
variables on the project page): the page names them, as the launch does (D7), and
`in_effect` does not let them change its answer, so the refusals of D4 stay the same.

### D6. git 2.31 where LADO's or a project's author is set

Plain entries need only `GIT_CONFIG_COUNT` (git 2.31), not 2.36. Setting LADO's or a
project's author is refused with an older git on LADO's PATH (`git_servers.check_git`'s
words); a launch is refused while either applies and the agents' git is older, naming the
version, 2.31 and the command that clears it (`lado git-server author --clear`, `lado
project author <id> --clear`). The servers' 2.36 rule stays as it is.

### D7. The launch's warning covers every LADO author

`runtime._git_server_warnings` names each of `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`,
`GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL` in the agent's environment when LADO's author,
the project's author or a server's author is set, with the text `<NAME> is set for <agent>:
it wins over LADO's commit authors`. A project variable of that name counts: it is in the
agent's environment like an outside one.

### D8. CLI

- `lado git-server author [<address>] [--name N --email E | --clear]`: without an address it
  is LADO's author. Set: `Agents commit as <author> where no project or git server has an
  author of its own.`; clear: `LADO has no commit author now.` and the line of what is in
  effect; show: `<author>`, or `LADO has no commit author: agents commit as <author> from
  your git config.`, or `LADO has no commit author and git knows none: agents cannot commit.
  Set one: lado git-server author --name "Your Name" --email you@example.com`; then the
  restart line `AUTHOR_RESTART` after a change. Setting or clearing LADO's author is the
  human's alone (`_human_only`); a server's stays as it is.
- `lado git-server list` prints `LADO's commit author: <author>` (`-` for none) on its first
  line, before the table or the "No git servers" line.
- `lado project author <id> [--name N --email E | --clear]`: the project's, with the same
  words for `in project <id>`; human-only as every `lado project` command. `lado project
  show` gets a line `  author:  <author>` after `made:` (`-` for none).
- `--name` without `--email`, the other way round, or `--clear` with either: exit 2, as
  today.

### D9. Server API

- `GET /api/git-servers`'s `GitServers` gets `author: AuthorInfo | null` (LADO's),
  `git_author: AuthorInfo | null` (`git_own` outside any repository, for the line "from
  your git config") and `author_variables: list[str]` (D5); `AuthorInfo {name, email}`.
- `PUT /api/git-author` (`{name, email}`) and `DELETE /api/git-author`, both →
  `GitAuthorDone {author, git_author, line}`; a refusal is the git entries' 400 with its
  field. Not under `/api/git-servers/…`: `DELETE /api/git-servers/{host}` would take
  `author` for a host.
- `ProjectInfo` gets `author: AuthorInfo | null`, `author_variables` (with the project's
  variables) and, per repository, `commit_author: {author: AuthorInfo | null, source}`
  (D5); `PUT` and `DELETE /api/projects/{id}/author` →
  the project as `GET` answers it.
- `ScratchInfo.author` and `SetupInfo.author` keep their shape (`{text, hint}`), with D4's
  text and hint; the server's `scratch`/`setup` checks pass the project when the target is a
  project's.
- `make web-types` after the models change.

### D10. lado doctor and the container

`doctor.check_git_author`: `[ok  ] git author: LADO's commit author set` when LADO's author
is; else as today (`user.name and user.email set`), and `WARN` with D4's hint; it still
never prints a name or an email. The entrypoint's warning becomes `lado: warning: git has no
user.name or user.email; set LADO_GIT_NAME and LADO_GIT_EMAIL, or the commit author in
Settings → Git servers` (it cannot read lado.db, so it no longer says agents cannot commit).
`LADO_GIT_NAME`/`LADO_GIT_EMAIL` keep writing git's global config.

### D11. The UI

Built to the screens and texts the design flow `ui-design/lad-312-ui` settles and the human
approves (its spec and mockup become this change's `git-servers-page` and `projects` UI
requirements and `docs/design/ui.md`'s sections). Fixed here: LADO's author on Settings →
Git servers above the servers, showing the author in effect; a server's and a project's
author optional and less visible; the start-from-scratch places show a link to Settings →
Git servers and Check again, never fields of their own; one result line at a time on the
page, as today.

### D12. Tests

Each requirement's test layer is named in the plan
(`docs/superpowers/plans/2026-11-24-commit-author-levels.md`): unit for the storage, the
levels, the entries against a real git (`git config --get` under the laid variables), the
CLI and the API; integration with the fake agent for the agents' commits (LADO's author in a
repository without a remote and no git config; a project's author over a server's in a
project session's clone; the `GIT_AUTHOR_EMAIL` warning) and for `lado start --new` with
LADO's author and no git config; vitest and UI e2e for the three screens; a container test
for the clean start without `LADO_GIT_NAME`.

## Risks / Trade-offs

- A repository's own `user.name` loses to LADO's author once it is set: accepted (#8086);
  the human sets a project's or a server's author for another name.
- A git older than 2.31 with LADO's author set refuses every launch: loud, with the command
  that clears it; macOS's Apple git and current distributions are newer.
- The page's author in effect is LADO's server's view (its git config), not the agents'
  login shell's: `GIT_AUTHOR_*` there are named at the launch, not on the page.
