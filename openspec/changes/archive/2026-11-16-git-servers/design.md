## Context

LADO reaches a git server only through access that exists outside it: `gh auth
git-credential` for `https://github.com` in the image's system git config (`docker/Dockerfile`,
requirement "git over https to GitHub uses gh's token"), the human's own helpers on a host,
and ssh through `LADO_SSH_AGENT`. Agents start from layered environments
(`agent_env.layers`: login shell, outside folder, LADO's secrets, the project) with LADO's
and the provider's variables over them (`runtime._launch_env`, `_ours`); LADO's own network
git calls run in `agent_env.for_git` plus `gitcache.NO_PROMPT` (`gitcache._git`,
`clone._env`). The model server store is the pattern for a saved list with secrets: rows in
`lado.db`, a key in `<LADO_HOME>/model-servers/<id>/key` written by
`project_secrets.write_at`, a CLI `lado model-server add|list|remove` reading the key
without echo (`cli._read_secret`), a probe with no redirect and a cut per request
(`model_servers._ask`). LADO's own Python processes start through
`interpreter.run_module`, which keeps the working folder off `sys.path`. `runtime.GIT_MIN`
is already 2.31 (the providers' folder-trust lookup), and `lado doctor` warns below it.

The epic's design (`git-servers-design.md`, attached to LAD-162) and the step brief fix:
one token per server, a server chosen by the host of the repository's address, https with
a token only, the global and system git configs untouched, the kind told by LADO with
`--kind` as the fallback, github.com not taken in this change.

The human's answers to question #7098: the scale; a server added while agents run reaches
them after their restart; only the standard ssh port is rewritten; the way back names the
token folders that stay, as for model server keys.

Facts checked by hand on git 2.39.5 (LADO's image): an empty `credential.<url>.helper`
given through `GIT_CONFIG_*` drops a `credential.helper=store` of `~/.gitconfig`, so `git
credential approve` calls only LADO's helper and writes no `~/.git-credentials`;
`url.<base>.insteadOf` given the same way rewrites `git@host:` for `git ls-remote`.

## Goals / Non-Goals

Goals: a saved list of GitHub Enterprise and GitLab servers with their tokens; agents and
LADO's own git reach them over https with no prompt, ssh forms included; nothing else
changes for a host not in the list. Non-goals: the proposal's Out of scope.

## Decisions

### D1. Modules

- `src/lado/git_kinds/` — one module per kind: `base.py` (`Kind`: `name` (`github`,
  `gitlab`), `title`, `request(root, token) -> (url, headers)`, `login(answer) -> str |
  None`, `refuses(answer) -> bool`, `git_user`, `tool`, `token_page(root)`), `github.py`,
  `gitlab.py`, and `__init__.py` with `KINDS`, the one tuple that names them (`--kind`'s
  choices, the probe's requests). A new kind is a module and its entry there.
- `src/lado/git_servers.py` — the address (D3), the probe (D2), the store (D4), the git
  variables (D5), the old-git check (D8). It imports `state`, `project_secrets`,
  `git_kinds`, `model_servers` (requests), `interpreter`.
- `src/lado/git_credential.py` — the helper (D6), importing only `project_secrets` and the
  standard library: it starts in every git credential call.
- `cli.py` — `lado git-server add|list|remove` (D9).

Why not inside `model_servers.py`/`model_settings.py`: different rules (one per host, no
names, kinds instead of APIs); sharing them would tie two lists that change apart.

### D2. The probe

Every kind of `KINDS` is asked at once (a thread per kind, as `model_servers._all`), one
GET each, cut at `model_servers.TIMEOUT` (5 s, name lookup included), no redirect followed,
the answer read up to `model_servers.MAX_ANSWER`. The request and answer type come from
`model_servers` (its `_ask`, `_no_answer`, `_NoRedirect` and `Answer` made public as
`ask`, `no_answer`, `NoRedirect`, `Answer`; renames only), so one HTTP path serves both
probes. GitLab: `GET <root>/api/v4/user`, header `PRIVATE-TOKEN: <token>`; recognised by
200 + JSON object with a string `username`; refuses by 401 + JSON object with `message`,
and by 403 + `{"error": "insufficient_scope"}` as "the token lacks the scope read_api".
GitHub: `GET <root>/api/v3/user`, `Authorization: token <token>`, `Accept:
application/vnd.github+json`; recognised by 200 + `login`; refuses by 401 + `message`.
Verdict: exactly one recognised → that kind and its login; one refuses → "refuses the
token" (even with `--kind`); two recognised → refused naming both (`--kind` picks);
none answering at all → "does not answer: <why>" with the hint naming `--kind`; answers
that neither kind tells (404, HTML) → "answers as neither GitHub nor GitLab" with the same
hint; a redirect → names its target (the cause is mostly an SSO page or a wrong address).
TLS failure (`Answer.tls`) → "its certificate is not trusted on this machine". The token
goes in the headers alone (no message is built from headers), as in `model_servers`.

### D3. The address

`git_servers.address(text) -> Address(root, host, port, scheme)`: no scheme → `https://`;
`http`/`https` only; userinfo, query, fragment refused; host lowercased; a default port
(443/80) dropped; a path kept without its trailing `/`. The identity is `host[:port]`
(`Address.key`). `github.com`, `www.github.com`, `api.github.com` are refused before the
token is asked. `http://` warns (`PLAIN_HTTP` of this module, in the model servers' words
for a token). Exit 2 for an address not taken, as `lado model-server add`.

### D4. The store

Schema 41, migration step `MIGRATIONS[40] = [GIT_SERVERS_TABLE]`:

```sql
CREATE TABLE IF NOT EXISTS git_servers (
    id TEXT PRIMARY KEY,          -- 12 hex, never changes (token folder's name)
    address TEXT NOT NULL,        -- the root (git_servers.address)
    host TEXT NOT NULL UNIQUE,    -- host[:port], the server's identity
    kind TEXT NOT NULL,           -- a name of git_kinds.KINDS
    login TEXT,                   -- NULL: saved with --kind, not checked
    added_at TEXT NOT NULL
);
```

`state.GitServer` with `state.git_servers()`, `state.git_server_by_host()`,
`state.save_git_server()` (insert, or update by host keeping the id), `state.remove_git_server()`.
`tests/agent_helpers.schema_before` gets the step undone (drop the table).
Token: `<LADO_HOME>/git-servers/<id>/token`, written by `project_secrets.write_at(("git-servers",
id), …)` and removed by `remove_at` plus the folder, as `model_settings` does for keys. Nothing
is written before the check passes. A new server: its token file first, then its row; a
failed row removes the new folder. A replaced server keeps its id: its row is updated, then
its token file is replaced whole by the rename, so a failure leaves the old token or the new
one, never none.

### D5. The git variables

`git_servers.variables(env, servers) -> dict` returns the `GIT_CONFIG_*` to lay over `env`.
It starts at `n = int(env.get("GIT_CONFIG_COUNT", 0))` (a non-number counts as 0 and its
entries are overwritten; `lado doctor` is not told: it is no state LADO made), and per server
adds, in this order:

1. `credential.<root>.helper` = `` (drops every helper set before it for that address, the
   image's or the human's `store`/`osxkeychain` included, so nothing else stores the token);
2. `credential.<root>.helper` = `!<shlex-quoted interpreter.run_module("lado.git_credential",
   "--home", <LADO_HOME>, "--server", <id>, "--user", <kind.git_user>, "--address", <root>)>`;
3. `url.<root>/.insteadOf` = `git@<host>:`;
4. `url.<root>/.insteadOf` = `ssh://git@<host>/`;
5. `url.<root>/.insteadOf` = `ssh://git@<host>:22/`;

where `<host>` is the bare host (an ssh address has no https port), then sets
`GIT_CONFIG_COUNT`. With no server it returns `{}`. The helper's arguments carry everything
it needs, so it never opens `lado.db` (a `lado.db` migrated under a running agent cannot
break it) and needs no `LADO_HOME` in its environment.

Where it is laid:
- Agents: `runtime._ours` adds `git_servers.variables(base_env, state.git_servers())` before
  the provider's `launch.env`; the names go into `LADO_LAUNCH_VARS` like LADO's other
  variables. Read once per launch (one query), so a server added later reaches agents launched
  later (the human's answer).
- LADO's own git: `agent_env.for_git(project, remote)` gets the remote and lays the same
  variables over its result; `gitcache._git` and `clone._env` pass their remote. Read at each
  call.

### D6. The helper

`python -c LOADER lado.git_credential --home H --server ID --user U --address R <op>` (git
appends the operation). `get`: reads `H/git-servers/ID/token` through the link-refusing
reader of LADO's secrets (`project_secrets.open_chain` + read, mode not checked here: `lado
doctor`'s later check), prints `username=U` and `password=<token>`; consumes stdin. A missing
or unreadable file: prints `quit=1` and one stderr line `lado: no token for <R>; add it again:
lado git-server add <R> --token`. `store`, `erase`, anything else: reads stdin, prints
nothing, exit 0. No `lado.db`, no other import of LADO beyond the secrets reader, so a call
costs one Python start (≈50 ms).

Why an argument and not a lookup by host: the host git sends is what the remote URL says;
the helper is registered per address, so git only calls it for that server anyway.

### D7. No prompt

For a listed host the helper either gives the token or says `quit=1`; git then neither tries
`GIT_ASKPASS` nor the terminal. A token the server refuses ends in git's own
`Authentication failed` without a prompt (git does not prompt after a helper's credential
fails). `GIT_TERMINAL_PROMPT` is not set for agents: hosts not in the list go as before.

### D8. git older than 2.31

`git_servers.check_git(env)`: `git --version` on `env`'s PATH (`runtime.git_version`'s parse,
`doctor._git_numbers` moved to `runtime.git_numbers`); below `runtime.GIT_MIN` raises
`GitTooOld` naming the version, 2.31 and `lado git-server remove <address>`. Called:
by `add` (LADO's PATH); by the launch of every agent when `state.git_servers()` is not empty
(the agent's PATH, before anything is started, in `runtime`'s pre-launch checks beside
`_check_commands`); by `for_git` when the remote's host is saved. A git that does not run is
left to the existing folder check and git's own error. `doctor.check_git`'s hint names git
servers too.

### D9. The command

- `lado git-server add <address> --token [--kind github|gitlab]`: `--token` takes no value
  (`nargs="?"`, a value refused like `model-server add --key`), the token read by
  `cli._read_secret("Token of the server (not shown): ")`; the parser's errors name no argv
  word (`_ServerParser`'s refusal texts, one for `git-server add`). Output: the probe's line
  (`GitLab, signed in as ivan.petrov`), then `Saved git server <root>.` or `Replaced git
  server <root>.`, then `Agents started from now on reach it; restart running agents to give
  it to them.` Warnings (`http://`, not checked) on stderr as `lado: warning: …`.
- `lado git-server list`: `ADDRESS  KIND  LOGIN  TOKEN` (`not checked` for no login,
  `yes`/`no` for the token file), `cli._table`.
- `lado git-server remove <address>`: by `Address.key`; `Removed git server <root>.`
- `lado git-server` alone prints its help.

### D10. No server API in this change

The brief allows it, and no screen uses one yet; the Settings page's task adds the API with
its screen and its UI test.

### D11. The way back

`self_update`'s plan: `git servers` joins the list of what is lost, and `_keys_left` gets a
sibling for `git-servers/` (folders with a `token` file whose id the copy lacks), printed as
`Git server tokens stay on disk; remove them when you no longer need them:`. Nothing removes
them: the older LADO does not know them, and the human may upgrade again.

### D12. Codex's sandbox

Codex runs shell commands of a host agent in its sandbox (`workspace-write` with LADO's
profile; in LADO's container it runs without one). Reading files is not restricted (checked
for the git profile, codex.py) and the agent's environment passes into commands (the
model-server review saw the key in `env`), so the helper can run and read its token. Network
in `workspace-write` is Codex's own rule, unchanged: a `git push` asks to run outside the
sandbox as today. The proof: a smoke test runs `codex sandbox -- git credential fill` with
LADO's variables (no network needed: git calls the helper for `get` before any request) and
expects the token; and `codex sandbox -- git ls-remote <local https server>` where Codex lets
the sandbox reach loopback. Where the sandbox cannot start (a container without user
namespaces) the test skips naming why. If the sandbox blocks the helper or the token, the
developer stops and brings it to the human (the brief's threshold).

### D13. Tests

A local https git server for tests (`tests/fake_git_server.py`): `git http-backend` behind
Python's `http.server` with TLS, a certificate made per test by `openssl` (skip naming why when
`openssl` is missing), trusted only through the test's `GIT_SSL_CAINFO`/`SSL_CERT_FILE`; Basic
auth required, the token as password; it records each request's user and path and answers a
fake `/api/v4/user` or `/api/v3/user`. Unit tests use a fake API in process (as
`tests/fake_model_server.py`). Layers per requirement: the plan.

### D14. Version

Minor: a new CLI command and schema migration 41. CHANGELOG under the next minor's
`(unreleased)` heading, group Added.

## Risks / Trade-offs

- A human's own `GIT_CONFIG_COUNT` that is not a number is overwritten: rare, and a broken
  value breaks their git anyway.
- An agent's own `git -c credential.helper=…` or a repository's local config after LADO's
  entries can still add helpers: the command scope is the last scope; LADO's entries come
  before `-c`. Accepted: it is the agent's own choice.
- A removed server keeps its helper in running agents until restart; git fails there with
  a line naming `lado git-server add` (requirement "The helper stops git when it has no
  token").
- `codex sandbox` cannot be checked in LADO's container (no user namespaces): the smoke
  cells on macOS and Linux runners are the proof, plus the manual check of the pull request.
