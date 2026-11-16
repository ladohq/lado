Task: LAD-289

## Why

LADO's agents reach a git server over https only when something outside LADO already gives
git a credential for it: in LADO's image that is `gh auth git-credential`, set for
`https://github.com` alone in the image's system git config; on a host it is whatever
helper the human set up. A human whose code lives on gitlab.com or on their company's
GitLab or GitHub Enterprise has no way to give LADO a token for it: an agent's `git push`
there fails with `could not read Username … terminal prompts disabled`, and a clone of such
a URL from the UI fails the same way. A remote of the form `git@gitlab.corp.ru:group/app.git`
needs an ssh key that LADO's image does not have (only `LADO_SSH_AGENT`, which many
humans do not run).

Root cause: LADO has no notion of a git server. Every way to a remote is GitHub's (`gh` in
the image), or the human's own machine setup, and LADO cannot hand an agent a credential
by the host of a repository's address.

Options weighed (cost over the epic's coming stages: Settings page, commit author, check,
GitHub login moved into the list, company certificate, `glab`):

- A (taken): a list of git servers in `lado.db` with each server's token in LADO's secret
  store, and LADO's own git credential helper given to each agent process and to LADO's own
  git through `GIT_CONFIG_*` variables, per listed host, with `git@host:` and
  `ssh://git@host/` rewritten to https. The global and system git configs stay untouched;
  the token stays in one file under `LADO_HOME`, read by the helper when git asks. Each
  coming stage adds a field or a variable to the same per-host block (author, CA file) or a
  kind module (Bitbucket, Gitea); nothing is redone.
- B: write the token into a `~/.git-credentials` of LADO's own (a `credential.helper=store`
  with a file under `LADO_HOME`). Simpler, but the token then sits in a second file in
  git's plain format, the store helper also saves any other host's credential there, and
  removing a server must edit that file. Rejected by the epic's rule: the secret only in
  LADO's store.
- C: hand the token to agents as a variable (`GITLAB_TOKEN`) and leave git to the agent.
  Nothing makes git use it, an agent prints it with `env`, and LADO's own clone does not
  benefit. Rejected.

## What Changes

- New command `lado git-server add <address> --token`, `lado git-server list`,
  `lado git-server remove <address>`; `lado git-server` alone prints its help.
- `add` asks the server's API with the token and tells what it is: `GitLab, signed in as
  <login>` or `GitHub, signed in as <login>`. A server that does not answer, refuses the
  token or is neither is not saved, with the reason in plain words; `--kind github|gitlab`
  saves one that does not answer or is not recognised, with a warning that it could not be
  checked. `http://` is taken with a warning that the token goes unencrypted. github.com is
  refused: it keeps working through `gh`'s login. Adding a server already listed replaces
  its token and kind.
- Each kind of server is a module of its own (GitHub, GitLab): how its API is asked, how its
  answer is told, the user name git sends with the token, its host tool and its token page.
- The token is kept in `<LADO_HOME>/git-servers/<id>/token` (folders 700, file 600, written
  by the link-refusing writer of LADO's secrets), never in `lado.db`, output or logs.
- Each agent process, at its launch, and each of LADO's own network git calls get, for each
  listed server, through `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_<n>`/`GIT_CONFIG_VALUE_<n>`:
  LADO's credential helper (with every helper set before it for that address dropped, so
  no other helper stores the token), and `git@<host>:` and `ssh://git@<host>/` rewritten to
  the server's https address. A host not in the list goes as before.
- LADO's credential helper `lado.git_credential` runs with LADO's own Python by an absolute
  path, so it is found without `lado` on the agent's PATH; it answers `get` with the
  token from its file and never stores or erases anything; with no token file it tells git
  to stop, so git never prompts.
- git older than 2.31 (which has no `GIT_CONFIG_COUNT`) is refused loudly where a listed
  server is needed: `add`, an agent's launch while the list is not empty, LADO's own git
  for a listed host. `lado doctor`'s git line names git servers among what needs 2.31.
- Schema 41: table `git_servers`. The plan of an update to an older schema names git
  servers among what is lost and lists the token folders that stay on disk.
- Docs: `docs/cli.md` (the command), `docs/design/modules.md`, `docs/design/agents.md` (the
  agent's git variables), `docs/install.md` (going back), AGENTS.md's Layout lines,
  CHANGELOG.md.

## Scope

`src/lado/git_servers.py` (new), `src/lado/git_kinds/` (new: `__init__.py`, `base.py`,
`github.py`, `gitlab.py`), `src/lado/git_credential.py` (new), `src/lado/state.py` (table,
migration 41), `src/lado/cli.py` (the command), `src/lado/runtime.py` (the agent's launch
variables), `src/lado/agent_env.py` (`for_git`), `src/lado/gitcache.py` and
`src/lado/clone.py` (the old-git refusal for a listed host), `src/lado/model_servers.py`
(its request function made public for the kinds), `src/lado/self_update.py` (the plan's
warning), `src/lado/doctor.py` (the git line's hint), tests (unit, integration, smoke,
`tests/agent_helpers.previous_schema`), the docs above.

## Out of scope

- A Settings page for git servers and a server API for it: no screen uses an API yet
  (AGENTS.md, "Only what is used"); the next task of the work adds both.
- github.com in the list, and a token for `gh`: github.com keeps working through `gh`'s
  login as now; moving it into the list is a task of its own.
- Commit author per server, a company certificate per server, `glab`: later tasks, each a
  field or variable in the same per-host block.
- Checking a saved server again (`lado git-server check`, a "Check" button) and
  `lado doctor`'s checks of the servers: a later task.
- Clone hints from the list: a later task.
- An ssh address with a port other than 22 (`ssh://git@host:2222/…`): git's rewrite matches
  a fixed prefix, and LADO cannot learn a server's ssh port from its https address; such an
  address goes over ssh as before (the human's answer to question #7098).
- Agents already running when a server is added or removed: they get the list at their
  launch, so a change reaches them after a restart (question #7098); LADO's own git reads
  the list at each call.
- ssh keys, Bitbucket and Gitea, several accounts on one server, a change to
  `LADO_SSH_AGENT`: outside this work.
- Removing the token folders on the way back to an older version: the older LADO does not
  know them; the warning names them, as it names model server keys (question #7098).

## Impact

- Minor version: a new CLI command and a schema migration (41).
- Agents get new `GIT_CONFIG_*` variables only while the list is not empty; with no server
  listed, their environment and LADO's git are as before.
- A human's `GIT_CONFIG_COUNT` in the agent's layers is kept: LADO's entries come after
  theirs.
