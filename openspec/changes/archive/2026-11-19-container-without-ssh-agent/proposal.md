Task: LAD-300

## Why

LADO's container gives every agent the host's ssh agent when `.env` names its socket
(`LADO_SSH_AGENT`): compose binds it at `/run/lado/ssh-agent.sock`, a sudo rule and a
program of the image hand a root's socket to `lado`, a profile file sets `SSH_AUTH_SOCK`,
and the image carries GitHub's ssh host keys. This was the way to git over ssh before
git servers existed. Now every git server, github.com included, is an entry of Settings →
Git servers whose `git@<host>:` and `ssh://git@<host>/` addresses go over https with its
token. The human decided (#7388, #7389) that access to git servers is set up only in
LADO's settings, never outside at Docker's start, and that backward compatibility is no
goal in itself (#7422). The host's ssh agent is the last way in from outside.

Two leftovers of the github.com entry's manual check go with it (#7446): the add form
fills in `https://gitlab.com` on an empty list although github.com is now an entry like
any other, and the install guide still says `git@github.com:` goes with an ssh key.

## What Changes

- **No ssh in the container.** compose binds no ssh socket. The image drops the socket's
  program and sudo rule, its profile file and GitHub's ssh host keys. An agent in Docker
  has no ssh at all: neither git over ssh to a host that is no saved server nor ssh to
  another machine. Outside Docker nothing changes.
- **`LADO_SSH_AGENT` is ignored without a word in the container.** The human decided
  (#7456) that the container gets nothing about it: no line in `docker compose logs`, none
  in `lado doctor`.
- **The installer** no longer asks for or writes `LADO_SSH_AGENT`. A rerun keeps the line
  in an old `.env`, so the way back to the version before still has it, and prints one
  note that it is no longer used.
- **The clone's hint in Docker.** An ssh address of a host no saved server has fails with
  `LADO's container has no ssh key for <host>` and the way out "add the server": the CLI's
  hint `lado git-server add https://<host> --token`, the UI's `Add git server ↗`. An ssh
  address with a port other than 22 says `LADO's container has no ssh: clone by the
  repository's https address`. Outside Docker the hint about the machine's ssh key stays.
- **The add form starts empty.** `+ Add server` opens Address empty, with the
  placeholder `github.com or gitlab.example.com`, on any list. GitHub's token hint stays at
  its minimum, the scope `repo`.
- **Docs and CHANGELOG.** docs/install.md: the `.env` examples lose `LADO_SSH_AGENT`; "git
  over ssh" says that a saved server's ssh addresses go over its token and that the
  container has no ssh, to other machines too; the token line names `read:org` and
  `workflow` as optional extras; "Go back" says how to get the ssh agent back. The compose
  and Dockerfile headers, docs/design/modules.md, docs/testing.md, docs/cli.md and
  docs/design/ui.md follow. CHANGELOG says that Docker has no ssh, to other machines too.

## Scope

In: `docker/compose.yaml`, `docker/Dockerfile`, `docker/Dockerfile.dockerignore`,
`docker/entrypoint.sh`, `docker/profile.sh`, `docker/install.sh`; the removal of
`docker/ssh-agent-socket.sh`, `docker/ssh-agent-env.sh` and `docker/ssh_known_hosts`;
`src/lado/clone.py`; `web/src/GitServers.tsx`; the docs above; tests of each layer.

## Out of scope

- **LADO without Docker**: it uses the user's own ssh as now; `SSH_AUTH_SOCK` stays in the
  agents' base environment (`agent_env.SHELL_BASE`).
- **A line about `LADO_SSH_AGENT` in the container's log or `lado doctor`**: the human
  decided against it (#7456), and it would need a new channel from compose into the
  container.
- **Noticing a socket at the old path** (an old `compose.yaml` kept by hand, `docker run
  -v`): it falls with the line above; the socket then lies unused.
- **An ssh key per git server**, a company's certificate, `glab`, `GITHUB_TOKEN` for
  GitHub Models: later tasks of the git servers.
- **`install.ps1`**: it never wrote `LADO_SSH_AGENT`; it runs `install.sh`, which changes.
- **Removing `LADO_SSH_AGENT` from an old `.env`**: the way back to the version before
  reads it.

## Impact

- Users of the container who cloned or pushed over ssh to a host that is no saved server,
  or used ssh to other machines from an agent, lose it; the clone's hint and the guide
  name the way through Settings → Git servers.
- Version: minor (a capability removed and the installer's questions changed); 0.48.0 is
  already the minor of the unreleased heading.
- No schema change, no API or MCP change; `web/openapi.json` is unchanged.
