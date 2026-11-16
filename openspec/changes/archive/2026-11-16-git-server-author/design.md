## Context

`lado.git_servers.variables` lays `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_<n>`/`GIT_CONFIG_VALUE_<n>`
over a process's environment: per saved server an empty credential helper, LADO's helper and
three `url.<address>/.insteadOf` rewrites of its ssh addresses. An agent gets them at its
launch (`runtime._ours`), LADO's own network git at each call (`agent_env.for_git`). The
rewrite does not change what a clone writes: a clone of `git@host:team/app.git` keeps that
address as `remote.origin.url`.

git takes `user.name`/`user.email` from its config scopes (system, global, local, worktree,
command; the last wins) and from `GIT_AUTHOR_*`/`GIT_COMMITTER_*` above them all. Since 2.36,
`includeIf "hasconfig:remote.*.url:<glob>".path` includes a file when any remote's URL as
written in the config matches the glob. Checked by hand on git 2.39 (2026-11-16): such an
entry given through `GIT_CONFIG_*` (command scope) is honoured; it wins over the repository's
local `user.name`; it is seen from a linked worktree; the glob is wildmatch with `/` special,
so `git@host:**` does not match `git@host:team/app.git` (`**` not next to `/` is `*`) while
`git@host:*/**` does, and `git@host:*` is needed for a path with no `/`; a git older than
2.36 skips the unknown condition silently.

The human's answers (#7165): the scale full; refuse git older than 2.36 where an author is
set (setting it, and a launch); the server's author wins over the repository's own, the
`GIT_AUTHOR_*` variables win over it with a launch warning; the two limits (no remote yet,
remotes on two servers) documented; option 1 of the mockup (✎ on the row, no author in Add
server); `lado git-server author` with `--name`/`--email`/`--clear`, the list's last column,
name and email together. The lead's requirement (#7167): the rule matches the forms LAD-289
rewrites, with an integration test of a clone by its `git@` address; the author file holds
only the name and email.

## Goals / Non-Goals

Goals: a commit author per saved server, set and cleared from the command and the page, given
to agents per repository by its remotes, through the process environment and files under
`LADO_HOME` only. Non-goals: the proposal's Out of scope.

## Decisions

### D1. Per-repository author through `includeIf hasconfig` in `GIT_CONFIG_*`

For each saved server with an author, the agent's launch adds, after that server's credential
and rewrite entries in the same numbering, one `includeIf.hasconfig:remote.*.url:<glob>.path`
entry per glob, all with the value of the author file's absolute path (D3). The globs of a
server with address `<scheme>://<netloc><path>` and host name `<h>` (`[<h>]` for IPv6, as in
`_entries`):

1. `<scheme>://<netloc><path>/**`
2. `<scheme>://*@<netloc><path>/**` (a URL with a user, `https://oauth2@host/…`)
3. `git@<h>:*` and 4. `git@<h>:*/**` (the scp form: one segment, and groups)
5. `ssh://git@<h>/**` and 6. `ssh://git@<h>:22/**`

These are the forms `server_for` and `_entries` take for the server, so the token's rule and
the author's agree. A glob has no `[`, `?` or `*` from the address itself: an address holding
one of them gets them escaped with `\` (wildmatch's escape). The entries live in a new
function `git_servers.author_entries(server, path) -> list[tuple[str, str]]`; `variables(env,
servers, authors=None)` takes `authors: Mapping[str, Path]` (server id → file) and adds them
for each server it names. Rejected: `GIT_AUTHOR_*` per agent (proposal, option B), local
config per worktree (option C).

### D2. Agents only; LADO's own git gets no author

`agent_env.for_git` (kits, packs, marketplaces, clones) calls `variables` without `authors`:
LADO commits nothing to a server's repository, and writing files at each such call would be
work for nothing. `runtime._ours` passes them.

### D3. The author file: in the agent's config folder, written at each launch

`<config_dir(agent)>/git-authors/<server id>.gitconfig` (`providers.base.config_dir`, written
anew at each launch, removed when the agent stops), mode 600, written whole by a rename,
holding exactly:

```
[user]
	name = "<name>"
	email = "<email>"
```

each value in double quotes with `\` and `"` escaped as git's config syntax wants (D5 already
refuses control characters). No token, no path, no other key (#7167). The row in lado.db is the
one source: no file outside an agent's folder, so a rollback (D7) leaves nothing in use and a
server's token folder (`git-servers/<id>/`, whose removal expects only `token`) is untouched.
A running agent keeps the file of its launch: a change reaches it after a restart, as the
token does.

### D4. Storage: schema 42, two nullable columns

`MIGRATIONS[41] = ["ALTER TABLE git_servers ADD COLUMN author_name TEXT", "ALTER TABLE
git_servers ADD COLUMN author_email TEXT"]`, `SCHEMA_VERSION = 42`, the same columns in the
table's `CREATE` for a new lado.db, `tests/agent_helpers.previous_schema` updated.
`state.GitServer` gains `author_name: str | None`, `author_email: str | None` (both or
neither); `state.set_git_server_author(id, name, email)` (None, None clears) returns the
server or None for an unknown id. `save_git_server`'s `ON CONFLICT … DO UPDATE` names only
address, kind and login, so adding a server again keeps its author (a test pins it).

### D5. The author's checks, one place

`git_servers.check_author(name, email) -> tuple[str, str]` trims both and refuses
(`Refused` with `field` `name` or `email`): an empty name (`the author's name is empty`); a
name with `<`, `>` or a control character (`the author's name holds no < or > or line
break`); an email that is not `local@domain` with both parts non-empty, exactly one `@`, no
whitespace, `<`, `>` or control character (`not an email address: name@host`); a value over
256 characters (`the author's name is longer than 256 characters` / the email's). No DNS, no
further email syntax: git and the server decide the rest. `git_servers.set_author(at, name,
email)` and `clear_author(at)` find the server by `Address.key` (unknown: the same refusal as
remove, `<address> is no saved git server`), check, call `check_author_git(os.environ)` (D6)
before setting, and save; the command and the page call them alone.

### D6. git 2.36 where an author is set

`runtime.GIT_AUTHOR_MIN = (2, 36)`. `git_servers.check_author_git(env)` refuses as
`check_git` does: `git <v> is older than 2.36, which a commit author of a git server needs;
update git` and, for the launch, `, or clear the author (lado git-server author <address>
--clear)` naming the first server with an author. `runtime._check_commands` calls it after
`check_git` when any saved server has an author; nothing else changes for a launch without
one. The page shows the setting's refusal under the buttons (field ""). `check_git`'s 2.31
rule is untouched.

### D7. The way back

A rollback restores `backups/lado.db.schema-41` (taken by `migrate` before 41 → 42): the
columns and every author are gone; a build of schema 41 never reads them. The author files
exist only in running agents' config folders and are rewritten (here: not written) at the
next launch. Tests: `test_state.py` migrates a schema-41 lado.db with a server (kept, no
author, the backup holds the old table) and, after setting an author, puts the backup back
and checks that `git_servers()` has no author and `variables(…, authors=…)` for those servers
adds no `includeIf` entry.

### D8. The author variables of the environment win, and the launch says so

git's `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL` beat
every config. When a server has an author and the agent's environment before LADO's own
(`base_env`) holds one of them, the launch adds the warning `<VAR> is set for <agent>: it wins
over the commit author of the git servers` (one line per variable) to the launch's warnings,
next to `_layer_warnings`' (a start's `Started.warnings`, a spawn's held lines). LADO does not
remove them: they are the human's own choice.

### D9. The command

`lado git-server author <address> [--name N --email E | --clear]` in `cli.py`, its parser
with `_GIT_…` errors as `add`'s: a bad address exits 2 (as `remove`), `--name` without
`--email` or the reverse, or `--clear` with either, exits 2 (`--name and --email go together`
/ `--clear takes no --name or --email`). Lines: set — `Agents commit to <address> as <name>
<<email>>.` then `Agents started from now on commit so; restart running agents to give it to
them.`; clear — `Agents commit to <address> with your own git author again.` and the same
second line (also when there was none: clearing is idempotent, exit 0); show —
`<name> <<email>>`, or `<address> has no commit author: agents commit there with your own git
author.` A refusal is `lado: <line>` with exit 1. `lado git-server list` adds `AUTHOR` last:
`<name> <<email>>` or `-`.

### D10. The server API and the page

`models.GitServerInfo` gains `author_name: str | None`, `author_email: str | None`.
`PUT /api/git-servers/{host}/author` (`GitServerAuthor {name, email}`) and `DELETE
/api/git-servers/{host}/author`, under `guard.changes`, both answer `GitServerAuthorDone
{server: GitServerInfo, line: str}` (the command's first line); a refusal is a 400 with
`EntryRefused` (`field` `name`, `email` or ""). `make web-types`. `GitServers.tsx`: the row's
`mx-acts` gets ✎ before 🗑 (`mx-icon`, `aria-label="Commit author of <address>"`, title
`Commit author`, `aria-pressed`), one panel under a row at a time (author form or remove
question; opening one closes the other); the form `mx-form` with the note `Agents' commits to
this server's repositories carry this name and email; elsewhere your own git author.`, Name
and Email in a `launch-grid` (side by side when wide, stacked on a phone), Save author
(`primary`, on when both trimmed values are non-empty and differ from the saved), Remove
author (`danger`, only when saved, no question: setting it again is as easy), Cancel (`quiet`),
Esc cancels; the focus on Name when opened. Done: the form closes, the saved lines
(`SavedLines`' look) above the row: the API's `line` and `Agents started from now on commit
so; restart running agents to give it to them.`, until the next change on the page; the focus
on the row. The row's third line `commits as <name> <<email>>` (`mx-l2`) when set.

## Risks / Trade-offs

- Ubuntu 22.04's git (2.34) cannot use an author: refused loudly; the human decided (#7165 q1).
- A glob case: git compares the URL as written; a remote typed with another case of the host
  (`GitLab.Corp.ru`) does not match. Accepted: clones take the address as given, and LADO's
  addresses are lower-case hosts.
- Remotes on two listed servers with authors: the later server wins (git's last include);
  documented (#7165 q3).
- Commits before a remote exists take the usual author (#7165 q3).

## Migration Plan

Schema 41 → 42 by `migrate` (backup first, as every migration). Rollback: D7.
