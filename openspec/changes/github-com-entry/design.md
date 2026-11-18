## Context

Saved git servers (`lado.git_servers`, schema 41–42) give agents and LADO's own git a token
through `GIT_CONFIG_*` variables: an empty `credential.<origin>.helper` that drops every
helper before it, then LADO's helper (`lado.git_credential`), which reads the token file
`<LADO_HOME>/git-servers/<id>/token`. `add` refuses github.com (`check_not_github`), and the
GitHub kind asks `<root>/api/v3/user`, which github.com does not have (its API is
`https://api.github.com/user`).

github.com is reached today by four logins LADO does not own:

- a `GH_TOKEN` file of the outside folder (`LADO_ENV_DIR`, `/run/secrets` in the image),
  which reaches the agents' environment as a layer (`agent_env.outside`) and LADO's own git
  (`agent_env.for_git`);
- a `GH_TOKEN` (or `GITHUB_TOKEN`) of the login shell, the agents' base layer;
- a project's `GH_TOKEN` secret, the project's layer (`project_secrets.layer`), suggested
  by `clone._github_login`;
- `gh`'s own login: `~/.config/gh/hosts.yml` (the home volume in Docker; the keychain on a
  Mac), reached by `gh` itself and, in the image, by git through the system helper
  `credential.https://github.com.helper = !/usr/bin/gh auth git-credential`
  (`docker/Dockerfile`).

`gh` takes, for github.com, `GH_TOKEN`, then `GITHUB_TOKEN`, then its own login; for any
other host `GH_ENTERPRISE_TOKEN`, then `GITHUB_ENTERPRISE_TOKEN`, then its own login. Inside
a repository it takes the host from the remote; `GH_HOST` names the host where none can be
inferred. `GH_CONFIG_DIR` moves its config and login folder.

An agent's launch merges the layers (`runtime.agents_env` → `agent_env.merge`) and lays
LADO's variables over them (`runtime._ours`); the result goes to the window through a file
readable by the user alone, removed when read (`agent_env.command`). A worker an agent
spawns drops the launch's own variables (`agent_env.without_launch`, `LAUNCH_VARS`).

`lado update` and the human's own rollback rely on the copy `backups/lado.db.schema-<N>`
that a schema migration writes (`state.migrate`); 0.48.0, which brings git servers, is
unreleased, so a user of 0.47.0 moves from schema 40 to 43 at once and goes back to the
copy of 40.

**Root cause.** Git servers were built for hosts LADO had no access to at all; github.com
was left to the logins that already worked (decision P6 of the epic), so it has no entry,
and the agents' environment still passes every outside GitHub variable through. The human
has now decided that git access lives only in LADO's settings (#7388, #7389).

## Goals / Non-Goals

Goals: one github.com entry agents and LADO use, made once from today's login without the
human doing anything; nothing outside LADO used afterwards, and said so by doctor and the
commands; `gh` for GitHub Enterprise; github.com on the page as any server; Docker and the docs without the old login;
the four leftovers of the last change. Non-goals: the proposal's Out of scope.

## Decisions

### D1. github.com is a row of `git_servers`, its API told by the kind

The entry is an ordinary saved server: address `https://github.com`, host `github.com`,
kind `github`, its token file, login and author as any server's. `GitHub.request` asks
`https://api.github.com/user` for the host github.com, `<root>/api/v3/user` otherwise; for
github.com the probe and the check ask the GitHub kind only (no GitLab request to
github.com) and no `--kind` is taken. `www.github.com` and `api.github.com` are taken as
`https://github.com`; another port or a path on github.com is refused. `check_not_github`
goes, and the page's Add form takes github.com as any address (D7).

Options weighed:
- a. **Chosen**: a row like any server. Check, author, helper, doctor and the page come
  for free; one source of truth.
- b. A table of its own for github.com: a second path for every rule of a server; it
  would drift.
- c. Keep github.com outside and only read the outside login: against the human's #7389.

### D2. Schema 43: the takeover's record

`MIGRATIONS[42]` adds a table `github_takeover` of at most one row: when it ran, the source
in words (`GH_TOKEN in /run/secrets`, `GH_TOKEN of your shell`, `the GitHub CLI's login`;
NULL for none found), and its outcome (`saved`, `unchecked`, `refused`, `none`, `kept` for
an entry already saved). Doctor reads it; the page does not (#7403). The new SCHEMA has the
empty table, so a new LADO_HOME takes over on its first start too. The way back is the
usual one: `backups/lado.db.schema-42` (or `-40` from 0.47.0) is the copy before, `lado
update <older>` restores it, and the older LADO sees no github.com row; an older LADO that
kept a row would ask `/api/v3/user` on github.com and fail its check.
`tests/agent_helpers.previous_schema` drops the table.

Options weighed:
- a. **Chosen**: a table of the takeover's own: "ran once" survives a removal of the entry.
- b. A mark on the github.com row: gone with Remove, so the takeover would run again and
  bring back a login the human removed.
- c. A file under `LADO_HOME`: a second store beside lado.db, not restored by a rollback.

### D3. The takeover runs once, on the first start, before any agent

`github_takeover.run()` (a new module) is called by the UI server's start and by every
launch of agents (`runtime`, before the layers are merged), after the migration. With a
row in `github_takeover` it returns at once (one read). Otherwise, under the git servers'
lock (`git_servers._locked`):

1. a github.com entry already saved: outcome `kept`, nothing else;
2. the token: `GH_TOKEN`, else `GITHUB_TOKEN`, of the agents' layers with no project
   (`agent_env.layers`, the highest layer that sets it; a layer named as the source), else
   `gh auth token --hostname github.com` run with those layers less the GitHub variables
   (10 s at most); none: outcome `none`;
3. the probe of D1 with that token, 5 s per request: a login, `saved`; no answer,
   `unchecked` (saved without a login, as `--kind`); refused, `refused` (not saved);
4. the row.

When `gh auth token` fails for a reason other than "not logged in" (a keychain closed to a
process outside the Mac's graphical session, gh crashing), no row is written and the
takeover runs again at the next start; doctor says so. The command that took over prints
one line: `LADO took your GitHub login (<source>) into Settings → Git servers: github.com,
signed in as <login>.`, or for a refused token `GitHub refused the token of <source>: add
github.com in Settings → Git servers.` (the UI server writes it to its log). The page says
nothing of it (#7403).

Options weighed:
- a. In the SQL migration: it cannot run a shell, `gh` or a request, and a migration of
  `lado ls` would block on the network.
- b. **Chosen**: at the first start that launches agents or the UI, recorded in lado.db.
- c. On every start while no entry exists: a login made later outside LADO would come
  back after the human signed out, against "only settings".

### D4. The agents' and LADO's own GitHub variables come from the entries only

`agent_env.GITHUB_VARIABLES` = `GH_TOKEN`, `GITHUB_TOKEN`, `GH_ENTERPRISE_TOKEN`,
`GITHUB_ENTERPRISE_TOKEN`, `GH_HOST`, `GH_CONFIG_DIR`: dropped from every layer of an
agent's launch (`runtime.agents_env`) and of `for_git`. `git_servers.gh_variables(servers,
remote)` then gives, among LADO's variables of the launch (`_ours`, so `LAUNCH_VARS` names
them and a spawned worker gets its own):

- `GH_CONFIG_DIR` = `<the agent's config folder>/gh` (for `for_git`: `<LADO_HOME>/gh`),
  an empty folder LADO makes: `gh` sees no login of its own, and `gh`'s config stays the
  agent's;
- `GH_TOKEN` = the github.com entry's token, when saved with its token file;
- for the GitHub Enterprise entry that holds the session's repository's `origin`
  (`server_for`), else the only GitHub Enterprise entry: `GH_ENTERPRISE_TOKEN` = its token,
  and `GH_HOST` = its host (with its port) for the repository's server only.

The token reaches the agent's environment, as API keys do, through the launch file removed
when read; the token rule of git servers says so (spec). `gh` reads a token only from its
environment or its own login, so there is no helper path as for git.

Options weighed:
- a. Write `hosts.yml` with the tokens into the agent's `GH_CONFIG_DIR`: a second copy of
  each token on disk, against the token rule.
- b. **Chosen**: environment variables over an empty `GH_CONFIG_DIR`.
- c. Leave `GH_CONFIG_DIR` alone: after Remove `gh`'s own login would still reach agents
  while github.com is not in Settings.

Cost: `gh`'s own config of the human (aliases, protocol) does not reach agents; extensions
live in its data folder and still do.

### D5. The login outside is named by doctor and the commands, not by the page

`github_takeover.unused(layers, projects)` names, never with a value, each GitHub variable
of the outside folder (`GH_TOKEN in <folder>`), of the login shell (`GH_TOKEN of your
shell`) and of the projects' secrets (`GH_TOKEN of project <id>`). Doctor prints one `warn`
line `GitHub login outside LADO: <names> set but not used: github.com takes its token from
Settings → Git servers`, and one `info` line while `gh` is logged in (`gh auth status` with
the human's environment). `lado project set <project> <GitHub name>` saves and says
`<NAME> is not given to agents: …`. The page shows none of it: the human wants github.com's
row like any other (#7403). Without a screen this is no silent drop: the takeover's
command says what it took, doctor says what is ignored, and the one command that sets such
a variable warns.

### D6. Docker loses the system helper of github.com

The two `git config --system credential.https://github.com.helper` lines go: with an entry
LADO's empty helper dropped them anyway; without one they would let `gh`'s login on the
home volume reach LADO's own git. The comments of the Dockerfile, `compose.yaml` and
`install.sh` stop offering `GH_TOKEN` and `gh auth login` and point at Settings → Git
servers; the outside folder stays for other variables. A rollback runs the older image,
which brings the helper back with its own LADO.

### D7. The page treats github.com as any server

github.com is a row of Servers, sorted as the others, with the panel of any server:
Sign-in (`Check`, `Replace token`), Commit author, `Remove server`. Without an entry it is
not on the page; `+ Add server` adds it: the address check without the token asks
`https://api.github.com/user` (D1), whose 401 tells `GitHub answers.`, and Token links
`https://github.com/settings/tokens` with `scope repo`. The Add form's github.com refusal
goes; Servers' ⓘ says "Your GitLab, gitlab.com, GitHub or GitHub Enterprise: agents clone
and push there, and run gh, with the token you give. Running agents get a change after
they restart." No new API field: the existing listing, check, add, author and remove
endpoints take the host `github.com`.

Options weighed:
- a. A block of its own with Sign in and Sign out (the first mockup): declined by the human
  (#7403), as github.com is an entry like the others.
- b. **Chosen**: one more row.

### D8. github.com's clone hints follow a saved server's

`_github_login` goes. A failed clone from github.com with an entry gets the saved server's
reason and hint (`lado git-server check https://github.com`, the replace line); without
one, as any unsaved host: `github.com asks for a login` with `Add it as a git server with a
token:` `lado git-server add https://github.com --token` and the page's way `add` (the Add
form with Address `https://github.com`). `access_denied` and `not_found` lose `gh auth status`.

### D9. GitHub Enterprise under a port or a path

`GH_HOST` is the saved host with its port (`ghe.test:8443`), as `Address.key`; a GitHub
Enterprise saved under a path gets the token but `gh` cannot reach its API there. Neither
is checked against a real server; the pull request names them as not verified.

### D10. The leftovers

- `runtime.Hint` takes several commands, each on its own line with its own words: `Check
  the git server:` `lado git-server check <root>` and `If its token expired or was revoked,
  replace it:` `lado git-server add <root> --token`. The UI's FolderHint shows each.
- The author's Edit and Set author are off while its Remove or Undo asks.
- A saved server's failure reason names `Address.key` (host with its port).
- doctor's git servers and GitHub lines catch `sqlite3.OperationalError` (locked longer than
  10 s): one `warn` line `not checked: lado.db is busy`, the other lines follow.

### D11. Tests by layer

- Unit: the kind's github.com request; the takeover's sources, outcomes, once, `kept`,
  retry after a gh failure; the variables dropped and given (github.com, Enterprise, none);
  `unused`; doctor's lines; migration 42 → 43 and the copy; clone hints; CLI.
- Integration (fake agent, `tests/fake_git_server.py` behind `ConnectProxy` as
  github.com and `api.github.com`, a fake `gh` on PATH that records its environment and
  answers `auth token`): the upgrade test of the spec (a `GH_TOKEN` in the outside folder,
  then a `gh` login, each taken over once; the agent clones and pushes with the entry's
  token; changing or removing the outside token changes nothing; doctor names it); a
  project's `GH_TOKEN` secret unused; no entry and no login; GitHub Enterprise: the
  agent's `gh api -X POST repos/<o>/<r>/pulls` reaches the fake API with the token and the
  host; the update and rollback (`test_update_process.py`, schema 43's copy, the older
  LADO's session).
- Container: the image without the system helper; the real `gh` in it takes the entry's
  `GH_TOKEN` and its own `GH_CONFIG_DIR` (`gh auth status` against the fake API through the
  proxy).
- vitest and UI e2e (no network): github.com in Servers (Check, Commit author, Remove),
  the Add form with `github.com` (`GitHub answers.`, the token page, saved), the author's
  buttons off while asking.
- The real `gh pr create` (GraphQL) is not faked: the human's check opens a real pull
  request on github.com.

## Risks / Trade-offs

- A Mac whose keychain is closed to the process that starts LADO first (ssh): the takeover
  waits for a start inside the graphical session; until then github.com is not in the list
  and doctor says why.
- A token of `GH_TOKEN` that only a project's secret gave is not taken over: the human adds
  github.com once; doctor names the project's secret as unused.
- The page does not say the login was taken over or that an outside token is ignored
  (#7403): a human who reads neither the command's line nor doctor learns it from
  CHANGELOG and docs/install.md.
- `GH_HOST` with a port and GitHub Enterprise under a path are passed as LADO saved them;
  `gh`'s handling of them is not checked against a real server.
- The human's own `gh` config does not reach agents (D4).

## Migration Plan

Schema 42 → 43 (D2), from 40 or 41 through the earlier steps. Rollback: the copy
`backups/lado.db.schema-<N>` restored by `lado update <older>` or by hand (docs/install.md);
`secrets/GH_TOKEN`, the shell's variables and `gh`'s login are never touched, so the older
LADO works as before. In Docker the older image brings its system helper back.

## Open Questions

None left: the human's answers to #7395 and #7403 are in the decisions above.
