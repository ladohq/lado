Task: LAD-303

## Why

A saved GitLab gives the agents' git its token, its certificate and its commit author, but
nothing more: an agent cannot open a merge request there. LADO's image has no `glab`, and
outside the image an agent's `glab` either is not logged in or uses the human's own login,
which may be for another account or host. Nor does any agent know, without its kit saying so,
on which kind of server its repository lives and which tool goes with it: a kit that names
`gh` sends an agent to GitHub's tool on a GitLab repository. LADO knows both from the saved
server, so LADO should say it and sign the tool in.

## What Changes

- **`glab` in the image** at a pinned version (1.130.0), checked by its SHA-256 per
  architecture, in a layer of its own under `/opt/tools`; its update check and usage
  statistics off. The image grows by about 56 MB (amd64), under the 60 MB limit.
- **The agents' `glab` is signed in from the saved GitLab servers.** Each agent's launch
  gives `glab` its own configuration folder (`GLAB_CONFIG_DIR`) holding one entry per saved
  GitLab server: its host, protocol, path, its certificate when one is saved (`ca_cert`),
  and the token sent as a header that LADO's helper reads from the server's token file at
  each call. No token lands in the configuration; the human's own `glab` configuration is
  not read or changed.
- **Agents get no GitLab variable from outside LADO**, as for GitHub: `GITLAB_TOKEN`,
  `GITLAB_ACCESS_TOKEN`, `GITLAB_HOST`, `GITLAB_URI`, `GL_HOST`, `GLAB_CONFIG_DIR`,
  `GITLAB_API_HOST` and `GITLAB_REPO` of any layer are dropped; `lado doctor` names them,
  and the human's own `glab` login, as not used, and an `OAUTH_TOKEN` agents keep as one
  their glab sends to a GitLab not in the list.
- **Each agent is told its repository's server and tool.** When the session repository's
  `origin` is on a saved server, every agent's instructions carry one line naming the
  server's kind and host, its tool (`gh` or `glab`, from the kind) and what it is for (pull
  requests or merge requests), and that it is logged in, or why it is not (tool missing, too
  old, no token, `gh` without the certificate). A host not in the list gets no line.
- **A missing or too old tool is said loudly, never refused.** The launch warns when the
  repository's server's tool is not on the agents' `PATH`, or is `glab` older than 1.114.0
  (the first that sends a header from a command); `lado doctor` has one line per tool of the
  saved servers' kinds, with its version.
- **A GitLab token without `api` is named.** `read_api` reads the API only, so glab cannot
  open a merge request with a token of `read_repository, write_repository, read_api`. The
  token page's hint asks for `api`; a check of a token without it still works for git and
  says `glab cannot open merge requests: the token lacks api`, and `lado doctor` warns.
- **A live test** per Claude Code and Codex: an agent with a model commits and pushes to a
  repository of a saved server (a local https git server with a token and a test
  certificate).
- **docs/install.md** gets a GitLab part: the token and its scopes, Check, what agents do
  with `glab`, and the old `glab` outside Docker.

## Scope

`docker/Dockerfile`, `docker/profile.sh`, `src/lado/git_kinds/` (the tool's minimum version
and the word for a change request), `src/lado/git_servers.py` (the glab configuration, the
agent's line, the tool check), `src/lado/git_credential.py` (the token for glab),
`src/lado/agent_env.py` (GitLab variables dropped), `src/lado/runtime.py` (the
instruction line, the launch warning, `GLAB_CONFIG_DIR`), `src/lado/doctor.py`, the check's ok line (`git_servers.check`), tests (unit,
integration with the fake agent, container, live; the UI test and vitest fixture of the
GitLab scopes text), `docs/install.md`, `docs/cli.md`,
`docs/design/agents.md`, `docs/design/modules.md`, `docs/testing.md`, CHANGELOG.md (0.48.0,
unreleased).

## Out of scope

- The certificate for `gh`: `gh` reads no authority per host; kept under Later (#7489).
  The agent's line and the launch say that `gh` cannot reach such a server.
- An agent's own https requests (curl, Node, MCP servers) to the server with the
  certificate: only git and `glab` get it, as the task's frame says.
- ssh for a server, Bitbucket and Gitea: Later.
- Kits' own texts that name `gh` (kit-sdlc's `Code host`, its analyst and integrator,
  kit-epic's `gh api`, kit-builder's commands rule): separate tasks after this one, with the
  human's yes; LADO's line is what they will rely on.
- Installing `glab` outside Docker: LADO says it is missing or old, the human installs it.
- A token written into `glab`'s configuration for an older `glab`: one way only (the
  header), an older `glab` is named as too old.
- The guide "Connect your git server": a later task of its own.
- Pinning `gh` in the image: it stays Debian's package from GitHub's apt source, as today.
