# The commit author of a git server: design

Task: LAD-291. Change: `openspec/changes/git-server-author/` (proposal, delta of `git-servers`
and `git-servers-page`, `design.md` with decisions D1–D10). Mockup: the run's artifact
`mockup-commit-author.html`, option 1 (frames 1a–1d) and the command; option 2 was not taken.

## What the human sees

A saved git server may carry a commit author: a name and an email. Agents launched from then
on commit to that server's repositories with that name and email (author and committer); to
every other repository as before. Running agents get it after a restart.

### The command

```
$ lado git-server author gitlab.corp.example --name "Ivan Petrov" --email ivan.petrov@corp.example
Agents commit to https://gitlab.corp.example as Ivan Petrov <ivan.petrov@corp.example>.
Agents started from now on commit so; restart running agents to give it to them.

$ lado git-server author gitlab.corp.example
Ivan Petrov <ivan.petrov@corp.example>

$ lado git-server list
ADDRESS                      KIND    LOGIN        TOKEN  AUTHOR
https://gitlab.com           GitLab  ivan.petrov  yes    -
https://gitlab.corp.example  GitLab  ivan.petrov  yes    Ivan Petrov <ivan.petrov@corp.example>

$ lado git-server author gitlab.corp.example --clear
Agents commit to https://gitlab.corp.example with your own git author again.
Agents started from now on commit so; restart running agents to give it to them.
```

Refusals (`lado: …`, exit 1): no such server (`<address> is no saved git server`, hint `see
them: lado git-server list`), an empty name, a name with `<`/`>`/a line break, `not an email
address: name@host`, a value over 256 characters, git older than 2.36 on this PATH. Usage
errors (exit 2): a bad address, `--name` without `--email` or the reverse, `--clear` with
either.

### Settings → Git servers

As frames 1a–1d of the mockup:

- A row with an author has a third line `commits as Ivan Petrov <ivan.petrov@corp.example>`;
  a row without one shows nothing about authors.
- ✎ (`Commit author`) before 🗑 opens a form under the row: the note `Agents' commits to this
  server's repositories carry this name and email; elsewhere your own git author.`, Name and
  Email (the saved values, else empty; the focus on Name), Save author (on once both are
  filled and differ from the saved), Remove author (only when one is saved), Cancel; Esc
  cancels. ✎ and 🗑 share the place under the row: opening one closes the other.
- A refusal shows under Name or Email (git too old: under the buttons).
- Done: the form closes; above the row `Agents commit to <address> as <name> <<email>>.` (or
  `… with your own git author again.`) and `Agents started from now on commit so; restart
  running agents to give it to them.` until the next change on the page.
- Add server is unchanged: the author is set on the saved row.

### At a launch

- While a server has an author and the agents' git is older than 2.36, the launch is refused:
  `git 2.34.1 is older than 2.36, which a commit author of a git server needs; update git, or
  clear the author (lado git-server author https://gitlab.corp.example --clear)`.
- When the agent's environment holds `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`,
  `GIT_COMMITTER_NAME` or `GIT_COMMITTER_EMAIL` and a server has an author, the launch warns
  `<VAR> is set for <agent>: it wins over the commit author of the git servers`.

## How it works

Decisions D1–D10 of `design.md`. In short: per server with an author, six
`includeIf.hasconfig:remote.*.url:<glob>.path` entries among the agent's `GIT_CONFIG_*`
variables (after the server's credential and rewrite entries), pointing to
`<agent config folder>/git-authors/<server id>.gitconfig`, which holds only `[user] name` and
`email`. git includes it in a repository whose remote, as written, matches one of the forms:
`<address>/**`, `<scheme>://*@<netloc><path>/**`, `git@<host>:*`, `git@<host>:*/**`,
`ssh://git@<host>/**`, `ssh://git@<host>:22/**`. lado.db (schema 42) keeps the author in the
server's row; the file is derived at each launch and goes with the agent's folder.

## Tests per requirement

| Requirement | Layer | Tests |
|---|---|---|
| git-servers: lado git-server author sets, shows and clears … | unit | `tests/test_cli_git_server.py`: set, show, clear, clear with none, unknown server exit 1, bad address exit 2, half author exit 2, `--clear` with a value exit 2 |
| git-servers: A commit author's name and email are checked | unit | `tests/test_git_servers.py`: `check_author` each refusal and its field, trimming, 256 limit |
| git-servers: Agents commit to a listed server's repositories as its author | unit + integration + smoke | unit `test_git_servers.py`: `author_entries` per address form (root with a path, a port, IPv6), escaping, order after the server's entries, `variables` without `authors` unchanged; integration `tests/integration/test_git_server_author.py` (real git, fake agent, `fake_git_server`): clone by https and by `git@` → author and committer of the pushed commit are the server's; a repository with a remote on another host and one with no remote → the fake HOME's `~/.gitconfig` author; a repository with a local `user.name` → the server's; clear + restart → the human's own; `~/.gitconfig` and the system config (`GIT_CONFIG_SYSTEM` file) byte-equal before and after; smoke `tests/smoke/test_codex_git_server.py`: a commit inside `codex sandbox` in a repository with a `git@` remote takes the server's author |
| git-servers: A commit author's file holds only the name and email | unit + integration | unit: the file's text for names with `"` and `\`, mode 600; integration: the file of a launched agent is exactly the `[user]` section, holds no token canary and no path, and is gone after the agent stops |
| git-servers: A commit author needs git 2.36 | unit | `test_git_servers.py` and `tests/test_runtime_git_servers.py` with a fake git on PATH reporting 2.34.1: setting refused; launch refused with an author, goes without |
| git-servers: The author variables … are named at its launch | unit | `test_runtime_git_servers.py`: `GIT_AUTHOR_EMAIL` in the layers → the warning; no author → none |
| git-servers: lado git-server list (modified) | unit | `test_cli_git_server.py`: the `AUTHOR` column, `-` |
| git-servers: One git server per host (modified) | unit | `test_git_servers.py`: add again keeps the author |
| git-servers: The saved git servers are kept in lado.db (modified) | unit | `tests/test_state.py`: schema 41 → 42 with a server (kept, no author, backup); rollback by the backup (no author, no `includeIf` entry); `set_git_server_author` set/clear/unknown |
| git-servers-page: A server's commit author is set and removed on its row | unit + vitest + UI | `tests/test_server_git_servers.py` (PUT/DELETE, refusals with fields, info carries the author); `web/src/GitServers.test.tsx` (✎ opens, one panel at a time, Save on/off, Remove only when set, Esc); UI `tests/ui/test_git_servers_section.py`: set an author, see the row's line and `lado git-server list`'s, a wrong email under Email, remove it; screenshots |

Regression: `make lint`, `make test`, `uv run pytest -m integration -n auto
tests/integration/test_git_server_author.py tests/integration/test_git_server_access.py`,
`uv run pytest -m ui tests/ui/test_git_servers_section.py tests/ui/test_settings_pages.py`,
`make web` (stale types), the openspec checks of `.lado/sdlc.md`; the smoke test runs in CI.

## Docs

- `docs/cli.md`: `lado git-server author`, the list's `AUTHOR` column, the author in "What a
  saved server gives" (the forms, who wins, the two limits, git 2.36 where an author is set),
  schema 42.
- `docs/design/ui.md`: Git servers — the row's third line, ✎ and its form, the done lines,
  the two routes and the model fields.
- `docs/design/agents.md`: the `includeIf` entries and the author files among the launch's
  `GIT_CONFIG_*`.
- `docs/design/modules.md`: `git_servers.py` (`check_author`, `set_author`, `clear_author`,
  `author_entries`, `check_author_git`).
- CHANGELOG.md: the 0.48.0 git servers entry gains the commit author (git 2.36 for it).

## Manual check (for the pull request)

In a fresh clone in a temporary folder, branch `feature/lad-291-git-server-author`:
`env | grep -E '^(GIT_|GH_|LADO_)'` and `unset` what a previous check left; `uv sync`; `make
web`; `export LADO_HOME=$(mktemp -d) LADO_TMUX_SOCKET=lado-check`; keep a copy of
`~/.gitconfig` (`cp ~/.gitconfig $LADO_HOME/../gitconfig.before`).

1. **[human: token]** `uv run lado git-server add gitlab.com --token` with a gitlab.com token
   (or the company GitLab's address).
2. `uv run lado git-server author gitlab.com --name "Test Author" --email test-author@example.com`
   → the two lines; `uv run lado git-server list` ends with `Test Author <test-author@example.com>`.
3. `uv run lado ui`: Settings → Git servers shows `commits as Test Author <…>`; ✎ opens the
   form with the values; type `bad` in Email → refused under Email; Cancel.
4. Start a session on a scratch folder (`uv run lado start --new $(mktemp -d)`) and ask the
   agent: **[human: a repository of yours on that server]** clone it by its `git@gitlab.com:`
   address, make an empty commit, show `git log -1 --format='%an <%ae> / %cn <%ce>'` → `Test
   Author <test-author@example.com>` twice; then `git init` another folder with no remote,
   commit, and the same log shows your own author. Push nothing unless you want to.
5. In Settings remove the author (✎, Remove author), restart the agent (`lado stop` /
   `lado start`), commit again in the clone → your own author.
6. `diff ~/.gitconfig $LADO_HOME/../gitconfig.before` → no difference; `git config --system
   --list` is as before.
7. `uv run lado git-server remove gitlab.com`; `lado stop` the session.
