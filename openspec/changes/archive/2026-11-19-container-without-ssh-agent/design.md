## Context

The container reaches the host's ssh agent through five pieces: compose's bind of
`${LADO_SSH_AGENT:-/dev/null}` at `/run/lado/ssh-agent.sock`; the entrypoint's block that
checks the socket with `ssh-add -l` and, for a root's socket, runs
`/usr/local/bin/lado-ssh-agent-socket` (`docker/ssh-agent-socket.sh`) through the sudo rule
`/etc/sudoers.d/lado-ssh-agent`; `docker/ssh-agent-env.sh` at
`/etc/profile.d/lado-ssh-agent.sh`, which sets `SSH_AUTH_SOCK` for login shells and which
the entrypoint sources for the server; `/run/lado` made root's 755; and
`docker/ssh_known_hosts` at `/etc/ssh/ssh_known_hosts`. `install.sh`'s `find_ssh_agent`
writes `LADO_SSH_AGENT` on a fresh install; `install.ps1` runs `install.sh` and never
names it.

A saved git server already sends `git@<host>:`, `ssh://git@<host>/` and
`ssh://git@<host>:22/` over https with its token (`git_servers._entries`, `insteadOf`). So
with no agent, ssh runs only for a host with no saved server, an ssh address on another
port or with another user, or ssh that is not git.

`clone._told` tells a failure by its kind; the ssh kinds (`ssh_denied`, `host_key`) get
`_reason`'s hint about this machine's key. `ServerWay("add", …)` is offered today only for
an http(s) access failure (`_server_way`). The UI shows a way as `GitServerNote`
(`Add git server ↗`, opening Settings → Git servers with the address), no change needed.

The add form opens with `addAt ?? (gitlab.com saved ? "" : GITLAB_COM)`
(`web/src/GitServers.tsx`).

## Goals / Non-Goals

Goals: no way into the container's ssh from outside; a clone's hint in Docker that points
at Settings → Git servers; an add form that fills in no server; guides that say all this.

Non-goals: LADO outside Docker; any line about `LADO_SSH_AGENT` in the container (#7456);
an ssh key per git server.

## Decisions

### D1. Remove every piece of the ssh agent, and GitHub's host keys with it

Removed: compose's bind and its header lines, the entrypoint's block and its `source`,
`docker/ssh-agent-socket.sh`, `docker/ssh-agent-env.sh`, `docker/ssh_known_hosts`, the
Dockerfile's `COPY`s, the sudo rule, `mkdir /run/lado`, their allowlist lines in
`Dockerfile.dockerignore`, the comment in `profile.sh`. GitHub's host keys go too ("only
what is used"): ssh to github.com now runs only when github.com is not saved, and then it
fails anyway, with the keys on `Permission denied (publickey)` and without them on `Host
key verification failed`; D4 tells both the same way. Kept: the ssh client (`openssh-client`
in the Dockerfile's `apt-get install`, its comment changed from "for the agents' pushes"):
without it git fails on an ssh address with `cannot run ssh`, which no kind tells, and a
key a user puts on the home volume by hand still works; LADO neither offers nor documents
that.

Alternatives: keep the host keys (a cleaner `Permission denied` for an unsaved
github.com, but a file to rotate when GitHub changes a key, for a path LADO no longer
supports); keep the socket's machinery unused (dead code under a sudo rule).

### D2. The container learns nothing of `LADO_SSH_AGENT`

The human's decision (#7456): compose passes nothing, the entrypoint and `lado doctor` say
nothing. A socket bound at the old path by an old `compose.yaml` or `docker run -v` lies
unused: no file of the image reads `/run/lado/ssh-agent.sock` any more.

### D3. The installer keeps the line and says once per run that it is unused

`find_ssh_agent` and its `.env` line go. `rerun` adds the note when `env_value
LADO_SSH_AGENT` is not empty, on every rerun (an update or a start of the same version),
since the line stays until the human removes it. `rewrite_env` keeps every other line
already, so the line stays without a change there. Removing the line was rejected: the
way back to a version before reads it with the old `compose.yaml.bak`.

### D4. The clone's ssh hint in the container

In `clone._told`, for the ssh kinds when `update.in_container()` and the address's scheme
is `ssh` (scp form included):

- port `None` or 22 and no saved server whose host is the address's host: reason
  `LADO's container has no ssh key for <host>`, hint `Add it as a git server with a
  token:` `lado git-server add https://<host> --token`, `ServerWay("add", key, root,
  page)` with `git_servers.address(f"https://{host}")`, page `Add <host> as a git server
  with a token: its git@ addresses then go over https too.`;
- otherwise (another port, another user such as `alice@host:`, or a saved host that ssh
  still reached): reason `LADO's container has no ssh: clone by the repository's https
  address`, no hint, no way.

Saved servers are read only for these kinds in the container (`_saved_servers`, which
makes no lado.db). `gitcache.explain` (kits, packs, marketplaces) takes the same text, as
it does today. Outside the container nothing changes. The check sits in `clone.py`, above
`providers/`: it depends on LADO's image, not on an agent CLI, so it holds for every
provider.

### D5. The add form fills in nothing

`initial={addAt ?? ""}`; the constant `GITLAB_COM` goes (its one use); Address's
placeholder becomes `github.com or gitlab.example.com`. The way out of a failure still
opens the form with its address (`?add=`). GitHub's `scopes="scope repo"` stays.

### D6. The way back

The way back keeps the new `compose.yaml` (docs/install.md, Go back), which binds no
socket: a version before 0.48.0 then runs without the ssh agent. The guide says to put
`compose.yaml.bak` back as well to get it. `installer` never goes back (its own rule).

### D7. Tests per layer

- unit: `tests/test_docker.py` (compose has no ssh bind, the image's files and allowlist,
  the headers' words, no `SSH_AUTH_SOCK` anywhere in `docker/`), `tests/test_install_sh.py`
  (fresh install writes none on macOS and Linux with a socket; an update keeps the line
  and prints the note once; a same-version rerun prints it too),
  `tests/test_clone.py` (the two container texts, the way, the saved-host case, outside
  unchanged; `update.in_container` patched);
- UI e2e: `tests/ui/` the empty form with its placeholder on an empty list and with
  gitlab.com saved; github.com typed gives `scope repo`; the clone's `Add git server ↗`
  in a container (server started with the container's mark) for an ssh failure;
- container: `tests/container/test_access.py` loses the ssh agent's tests and gets one:
  `.env` with `LADO_SSH_AGENT` naming a real socket on the host starts, no socket inside,
  no `SSH_AUTH_SOCK` in a login shell or the server, no ssh line in logs or doctor,
  `sudo -n -l` grants nothing; `tests/container/test_image.py` drops the socket from its
  bind filter;
- integration: none new; the ssh rewrite of a saved server is covered already
  (`git_servers` integration tests), and nothing here crosses processes anew.

## Risks / Trade-offs

- A user who used ssh from agents to other machines loses it in Docker; the guide and
  CHANGELOG say so (#7451, point 1).
- A user with an unsaved GitLab over ssh sees the clone fail until the server is saved;
  the hint names the way.
