# Git servers: a list of servers and the agents' access over https

Task LAD-289. Change: `openspec/changes/git-servers/` (decisions D1–D14 in its `design.md`).

## What the human gets

A human whose code is on gitlab.com, a company GitLab or GitHub Enterprise adds the server
once:

```
$ lado git-server add gitlab.corp.ru --token
Token of the server (not shown):
GitLab, signed in as ivan.petrov
Saved git server https://gitlab.corp.ru.
Agents started from now on reach it; restart running agents to give it to them.

$ lado git-server list
ADDRESS                 KIND    LOGIN        TOKEN
https://gitlab.corp.ru  GitLab  ivan.petrov  yes

$ lado git-server remove gitlab.corp.ru
Removed git server https://gitlab.corp.ru.
```

From then on every agent started by LADO, and LADO's own clone, kits and marketplaces, reach
`https://gitlab.corp.ru/...` with that token and never ask for a password; a remote written
as `git@gitlab.corp.ru:team/app.git` or `ssh://git@gitlab.corp.ru/team/app.git` goes there
over https too. A host not in the list, github.com included, goes exactly as before.

What the human sees when it does not work:

| Case | Output (stderr, exit 1 unless said) |
|---|---|
| No answer | `lado: gitlab.corp.ru does not answer: <the name is not found / the connection is refused / it did not answer in 5 s>` and the hint `lado: if the server is there for git but its API is not reachable from here, save it unchecked: lado git-server add https://gitlab.corp.ru --token --kind gitlab` |
| Untrusted certificate | `lado: gitlab.corp.ru does not answer: its certificate is not trusted on this machine` with the same hint |
| Token refused | `lado: GitLab at https://gitlab.corp.ru refuses the token` and `lado: make a token at https://gitlab.corp.ru/-/user_settings/personal_access_tokens (scopes read_repository, write_repository, read_api)` |
| Neither kind | `lado: https://git.corp.ru answers as neither GitHub nor GitLab` and the `--kind` hint |
| Redirect | `lado: https://gitlab.corp.ru sends to https://sso.corp.ru/login; give the server's own address` |
| Both kinds | `lado: https://x.corp.ru answers as GitHub and as GitLab; say which: --kind github or --kind gitlab` |
| `--kind` against the answer | `lado: https://gitlab.corp.ru answers as GitLab, not GitHub` |
| `http://` | warning `lado: warning: the token goes to git.lan over plain http://, unencrypted; use https:// if the server has it`, then saved |
| Unchecked with `--kind` | warning `lado: warning: https://git.lan could not be checked; saved as GitLab` (exit 0) |
| github.com | `lado: github.com is reached through gh's login (GH_TOKEN or gh auth login); LADO keeps no token for it` |
| Old git | `lado: git 2.30.2 is older than 2.31, which git servers need; update git, or remove the servers (lado git-server remove <address>)` |
| Bad address (exit 2) | `lado: <address> is not a server address: <why>` |
| Removed server, running agent | git: `lado: no token for https://gitlab.corp.ru; add it again: lado git-server add https://gitlab.corp.ru --token` then git's `credential helper … told us to quit` |

Token pages (`Kind.token_page`): GitLab `<root>/-/user_settings/personal_access_tokens`
(scopes `read_repository`, `write_repository`, `read_api`); GitHub Enterprise
`<root>/settings/tokens` (scope `repo`). The `read_api` scope lets the check read
`/api/v4/user`; without it GitLab answers 403, which the GitLab kind tells as "the token
lacks the scope read_api" (refused, as a refused token).

## How it works

```
lado git-server add ──► git_servers.probe ──► git_kinds.{gitlab,github}.request  (at once)
        │                                      model_servers.ask (no redirect, 5 s)
        ▼
 lado.db git_servers row  +  LADO_HOME/git-servers/<id>/token (600, by project_secrets)

agent launch (runtime._ours) ──┐
LADO's git (agent_env.for_git)─┴─► git_servers.variables(env, servers)
        GIT_CONFIG_COUNT=n+5k
        credential.<root>.helper = ""                     (drops other helpers)
        credential.<root>.helper = !<python> -c LOADER lado.git_credential --home … --server <id> …
        url.<root>/.insteadOf   = git@<host>:   ssh://git@<host>/   ssh://git@<host>:22/

git ──(401)──► LADO's helper `get` ──► reads the token file ──► username=<kind user>, password=<token>
                 no file ──► quit=1 (no prompt)        store / erase ──► nothing
```

Every piece of the per-server block is a `(key, value)` pair built in one function, so the
coming fields (commit author, CA file) are more pairs of the same block.

## Docs

- `docs/cli.md`: a section `lado git-server` after `lado model-server`: add (the check, the
  kinds, `--kind`, `http://`, github.com, replacing a token, the token never on the command
  line, agents after restart), list (columns), remove; what agents get (https with the token,
  the ssh forms, standard ssh port only; hosts not in the list as before; the global and
  system git configs untouched); git 2.31.
- `docs/design/modules.md`: `git_servers.py`, `git_kinds/`, `git_credential.py`; `runtime.py`
  and `agent_env.py` (`for_git`'s remote) lines.
- `docs/design/agents.md`: the agent's environment gets LADO's `GIT_CONFIG_*` entries after the
  layers' own.
- `docs/install.md`: "Going back to an older version" names git servers and their token
  folders.
- AGENTS.md Layout: `git_servers.py`, `git_kinds/`, `git_credential.py` in one line each
  (or one combined line), keeping the file under 200 lines.
- CHANGELOG.md, Added: **Your own git servers** — `lado git-server add <address> --token` adds a
  GitLab or GitHub Enterprise server; agents and LADO clone and push there over https without
  a password, `git@…` addresses included.
