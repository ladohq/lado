# Plan: Git servers (LAD-162)

## State
Phase: plan · Epic run: epic/epic-git-servers · Branch: base (main), decided at intake (#7068 q2)
In work: — · Next: S1a · Open checks: the human's check on the company GitLab, on the release candidate that carries S5
Standing rules of the human:
- One tracker task at a time, created when its step is reached, linked `derived` to LAD-162; findings and leftovers of a step go into the next step (2026-11-15, #7064).
- Explain to the human in plain words, technical details after.
- The statement's decisions (brief.md) are not reopened.
Last review: 2026-11-15, base at e0e27c02

## Steps

Every step merges into main, so releases between steps carry part of the feature (a list
without "Check", for example); each part works on its own, and the docs describe only what
is built.

The way back, the same for every step that stores data: a rollback (`lado update`'s, or
installing the previous version) puts back the copy of lado.db made before the migration
(`backups/lado.db.schema-<N>`); an older LADO refuses a newer schema, so there is no
"old LADO with the new data". After the rollback the stored entries are gone, files the
step keeps in `LADO_HOME` (tokens, certificates) stay without an entry and are not used;
git for a host that was listed goes the old way. Each such step checks it with an upgrade
and rollback test, as earlier migrations do, and names whether its files are cleaned up.

### S1a — Git servers: the list and https access for agents (walking skeleton)
Status: planned
Check: an integration test with a local https git server that requires a token: a server
added with `lado git-server add` (and through the API) is used by an agent process (the
fake agent) and by LADO's own git (`clone`, `gitcache`) to clone and push by https with
no prompt; `git@<host>:<path>` and `ssh://git@<host>[:port]/<path>` addresses of a listed
host go over https; a host not in the list behaves as before; a removed server's host
behaves as before; `~/.gitconfig` and the system config unchanged; git older than the
version that reads `GIT_CONFIG_*` from the environment (2.31) is refused loudly where a
server is listed, and `lado doctor` says so; a real CLI's git uses the entry — the smoke
layer for Claude Code and Codex (Codex in its sandbox), or a manual check in the pull
request for those it cannot cover; the upgrade and rollback test of the way back; the
docs describe what was built (docs/cli.md).
Touches: a new module of server kinds (github, gitlab), `agent_env.py`, `runtime.py`,
`providers/` (where a sandbox needs the helper), `cli.py` (`lado git-server add|list|remove`,
a credential helper command), `state.py`, `server/app.py` (API), `doctor.py`, tests, docs/cli.md.
Notes: `lado model-server add|list|remove` and `model_settings.py` are the precedent for
a saved list with a secret. The token lives in LADO's secret store under `LADO_HOME`
(as a model server's key), never in a git config file or an agent's worktree. A github.com
entry is not accepted until S3 (plan decision, P6): github.com keeps today's path through
`gh` until S3 settles which source wins.

### S1b — Settings → Git servers
Status: planned
Check: a UI e2e test adds a gitlab.com and a self-hosted server (kind, address prefilled
for gitlab.com, token with a "where to get it" link) and removes one; the list matches
`lado git-server list`; docs/design/ui.md and the user's docs describe the screen.
Touches: `web/src/` (Settings), `server/app.py` if the API needs a field, docs/design/ui.md.

### S2a — The commit author of a server
Status: planned
Check: an integration test: an agent's commit to a listed host carries the server's author
(name, email) in both author and committer, otherwise LADO's as today; Settings and
`lado git-server` set and clear it (UI e2e); the way back (above) with its upgrade and
rollback test; docs describe what was built.
Touches: the server kinds module, `agent_env.py`, `state.py`, `cli.py`, `web/src/`, docs.

### S2b — "Check", `lado doctor` and clone hints from the list
Status: planned
Check: unit tests per server kind against a fake API (`GET /user`): "Check" in Settings
and `lado git-server check` say "works, this is <name>" or why not in plain words (wrong
token, missing rights, server unreachable); `lado doctor` lists the servers and their
check; a failed clone from a listed host names its entry, from an unlisted host suggests
adding it, in the UI too (UI e2e); docs describe what was built.
Touches: the server kinds module, `doctor.py`, `clone.py`, `server/`, `web/src/` (Settings,
the clone window), docs.

### S3 — GitHub from the list: today's login becomes the github.com entry, `gh` takes the entry's token
Status: planned
Check: an integration test of an upgrade: a user with `GH_TOKEN` (an outside variable or a
project's secret) or `gh auth login` on the home volume sees a github.com entry that
"Check" confirms, and agents clone, push and run `gh` as before; a GitHub Enterprise entry
(kind GitHub, own address) gives `gh` its token and host (`GH_ENTERPRISE_TOKEN`,
`GH_HOST`) so an agent can open a pull request there (against a fake API); a project's own
`GH_TOKEN` is handled as the human decides (open question 1); nothing is deleted
(`GH_TOKEN` and gh's login stay), so after a rollback (the way back above) the old path
works — checked by running it after the rollback; the docs say where the GitHub login is now.
Touches: the server kinds module (github), `logins.py`, `agent_env.py`, `clone.py`
(`_github_login`), `docker/Dockerfile` (the system helper for github.com), docs.
Notes: decided at intake (D5). The analyst decides whether the entry is stored or derived
from the existing login (one source of truth).

### S4 — The company certificate
Status: planned
Check: an integration test with the local https server signed by a test CA: without the
certificate "Check" says the server is not trusted and the clone fails with that reason;
with it uploaded, LADO's git, the agents' git and `gh` clone, push and check; the user's and
the system's trust stores unchanged; the way back (above): after a rollback the
certificate file stays unused under `LADO_HOME` and git for that host fails as before the
step, checked by the upgrade and rollback test; docs describe what was built.
Touches: the server kinds module, `agent_env.py`, `state.py`, `server/`, `web/src/`
(Settings), docs.

### S5 — GitLab: `glab` in the image, agents open merge requests
Status: planned
Check: a container test: `glab` is in the image at a pinned version and, for an agent whose
repository is on a listed GitLab, is configured from the entry (host, token, certificate)
with no login of its own (`glab auth status` against a fake server); the image grows by at
most 60 MB (past it: ask the human before merging); docs describe what was built (the
GitLab part of docs/install.md). Then the human's check, on the release candidate that
carries S5 (Docker on a Mac, the company GitLab over the company's VPN): Settings → Git
servers → "Check" green; an agent clones, commits with the given author, pushes and opens
a merge request; github.com works as before.
Touches: `docker/Dockerfile`, `scripts/` pins, the server kinds module (gitlab),
`agent_env.py`, `tests/container/`, docs/install.md.

### S6 — The guide "Connect your own git server"
Status: planned
Check: a new guide file in `docs/` in plain words: where to create a token on GitHub and
GitLab, which rights it needs, what each "Check" failure means and what to do; its links
work (the docs checks pass); the human reads it.
Touches: the new guide file and a link to it from docs/install.md's table of contents
only — a candidate to run alongside S5 if the human asks for two at once.

## Open questions

1. A project's own `GH_TOKEN` secret after S3 (`clone.py` suggests `lado project set
   <project> GH_TOKEN --secret` today): which wins for that project's git and `gh` — the
   project's token or the github.com entry? Recommended: the project's token while it
   exists, with Settings and `lado doctor` naming the project that overrides the entry, so
   nothing that works today stops working. Asked when S3's brief is drafted.

## Later

- ssh for a server (an optional "ssh key" field, host key confirmation) — out by the
  statement; the server entry leaves room for it.
- Bitbucket and Gitea as new server kinds — out by the statement; the kinds module is
  meant for them.
- Several accounts on one server — out: LADO is single-user.
- The host's ssh agent (`LADO_SSH_AGENT`): not developed further; whether to remove it is
  decided apart.
- Kit sdlc: a `.lado/sdlc.md` example for GitLab and "merge request" wording — in the
  kit-sdlc repository; its task is created on the human's yes after S5 (D6).
- A company certificate for model servers inside the company — the same file may serve
  them; not asked for now.
