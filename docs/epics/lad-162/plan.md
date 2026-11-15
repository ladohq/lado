# Plan: Git servers (LAD-162)

## State
Phase: plan · Epic run: epic/epic-git-servers · Branch: base (main)
In work: — · Next: S1 · Open checks: the human's check on the company GitLab, after S5
Standing rules of the human:
- One tracker task at a time, created when its step is reached, linked `derived` to LAD-162; findings and leftovers of a step go into the next step (2026-11-15, #7064).
- Explain to the human in plain words, technical details after.
- The statement's decisions (brief.md) are not reopened.
Last review: 2026-11-15, base at e0e27c02

## Steps

### S1 — Git servers: the list and https access for agents (walking skeleton)
Status: planned
Check: an integration test with a local https git server (self-signed CA trusted only by
the test, a token required): a server added through the API is used by an agent process
(the fake agent) and by LADO's own git (`clone`, `gitcache`) to clone and push by https
with no prompt, and `git@<host>:<path>` addresses of a listed host go over https; a host
not in the list behaves as before; `~/.gitconfig` and the system config unchanged; a UI
e2e test adds and removes a server in Settings → Git servers; the docs describe what was
built (docs/cli.md or install, docs/design/ui.md). Way back: the server list is new data
(likely a schema migration): an older LADO ignores it, github.com keeps today's path.
Touches: a new module of server kinds (github, gitlab), `agent_env.py`, `runtime.py`
(the agent's environment), a credential helper command of `lado`, `state.py`, `server/app.py`,
`web/src/` (Settings), docs.
Notes: Settings → Git servers with kind, address (prefilled for github.com, gitlab.com),
token with a "where to get it" link, remove. The token in LADO's secret store, never
written to a git config file. Model servers (`model_settings.py`, Settings → Models) are
the nearest precedent for a saved list with a secret. The analyst may split it into core
and screen (two pull requests) at design.

### S2 — The commit author, "Check", `lado doctor` and clone hints from the list
Status: planned
Check: unit tests per server kind against a fake API (`GET /user`): "Check" says "works,
this is <name>" or why not in plain words (wrong token, missing rights, server
unreachable; untrusted certificate waits for S4); an agent's commit to a listed host
carries the server's author (name, email), otherwise LADO's; `lado doctor` lists the
servers and their check; a failed clone from a listed host names its entry, from an
unlisted host suggests adding it, in the UI too; UI e2e for the author fields and "Check";
docs describe what was built.
Touches: the server kinds module, `agent_env.py`, `doctor.py`, `clone.py`, `server/`,
`web/src/` (Settings, clone window), docs.
Notes: leftovers of S1 come in here.

### S3 — Today's GitHub login becomes the github.com entry
Status: planned
Check: an integration test of an upgrade: a user with `GH_TOKEN` (a variable or a secret)
or `gh auth login` on the home volume sees a github.com entry in Settings that "Check"
confirms, agents clone and push as before; nothing is deleted (`GH_TOKEN` and gh's login
stay), so a rollback to 0.47 keeps working — checked by running the old path after the
upgrade; the docs say where the GitHub login is now. Way back: as stated.
Touches: the server kinds module (github), `logins.py`, `agent_env.py`, `clone.py`
(today's `_github_login` hint), `docker/Dockerfile` (the system helper for github.com),
docs.
Notes: decided at intake (D5). The analyst decides whether the entry is stored or
derived from the existing login (one source of truth).

### S4 — The company certificate
Status: planned
Check: an integration test with the local https server whose certificate is signed by a
test CA: without the server's certificate "Check" says the server is not trusted and the
clone fails with that reason; with it uploaded, LADO's git, the agents' git and the hosts'
tools (`gh`) clone, push and check; the user's and the system's trust stores unchanged;
docs describe what was built.
Touches: the server kinds module, `agent_env.py`, `server/`, `web/src/` (Settings), docs.

### S5 — GitLab: `glab` in the image, agents open merge requests
Status: planned
Check: a container test: `glab` is in the image at a pinned version and, for an agent of a
session whose repository is on a listed GitLab, is configured from the entry (host,
token, certificate) with no login of its own (`glab auth status` against a fake server);
the image's size growth stays under the threshold of the step's brief; docs describe what
was built. Then the human's check (Docker on a Mac, the company GitLab over the company's
VPN): Settings → Git servers → "Check" green; an agent clones, commits with the given
author, pushes and opens a merge request; github.com works as before.
Touches: `docker/Dockerfile`, `scripts/` pins, the server kinds module (gitlab),
`agent_env.py`, `tests/container/`, docs.

### S6 — The guide "Connect your own git server"
Status: planned
Check: the guide in `docs/` in plain words: where to create a token on GitHub and GitLab,
which rights it needs, what each "Check" failure means and what to do; its links work
(the docs checks pass); the human reads it.
Touches: `docs/` only — can run alongside S5.

## Open questions

None open: the questions of intake are answered (decisions.md).

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
