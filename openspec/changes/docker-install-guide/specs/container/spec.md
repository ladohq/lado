## ADDED Requirements

### Requirement: The image knows GitHub's ssh host keys

The image SHALL hold GitHub's published public ssh host keys for `github.com` in
`/etc/ssh/ssh_known_hosts`, copied from `docker/ssh_known_hosts`, so the first ssh to
github.com on a new home volume asks no question and ssh still refuses a key that is not
GitHub's. The file SHALL hold only lines for `github.com`, one per key type GitHub
publishes (ed25519, ecdsa-sha2-nistp256, rsa).

#### Scenario: The first ssh on a new volume
- **WHEN** a container on a new home volume, with no ssh agent, runs `ssh -T -o
  BatchMode=yes git@github.com` in `lado`'s login shell
- **THEN** it fails on the missing key (`Permission denied (publickey)`), never with
  `Host key verification failed`, and `~/.ssh/known_hosts` gets no line

#### Scenario: The file
- **WHEN** `tests/test_docker.py` reads `docker/ssh_known_hosts`
- **THEN** every line names `github.com`, and its key types are ed25519,
  ecdsa-sha2-nistp256 and rsa

### Requirement: The image holds no private data

The image SHALL hold no key, login, password or token of any person: the human gives
their own at run time (the secrets folder, logins on the home volume, the host's ssh
agent). The only keys the build puts in it SHALL be public host keys. The build context
SHALL stay the allowlist of `docker/Dockerfile.dockerignore`, which names each file the
build takes.

#### Scenario: The build context
- **WHEN** `tests/test_docker.py` reads `docker/Dockerfile.dockerignore`
- **THEN** it lets in only `dist/lado-*.whl`, `docker/profile.sh`,
  `docker/entrypoint.sh`, `docker/ssh-agent-socket.sh`, `docker/ssh-agent-env.sh` and
  `docker/ssh_known_hosts`

### Requirement: The install guide leads with compose and runs the headers' commands

docs/install.md SHALL have a section `Docker` that leads with compose: get `compose.yaml`,
write `.env`, make `secrets/`, start, open the UI, log in to the agent CLIs, ssh, update
and go back, a second LADO, the sessions, removal and the pitfalls; README's Install SHALL
link to it. Its start, update and way-back commands SHALL be exactly those of
`docker/compose.yaml`'s header, which the container tests run. Its `.env` SHALL name every
variable compose reads but `LADO_IMAGE` and `LADO_SECRETS`. It SHALL remove only its own
container and volume, by name, and nothing in the guide or the headers SHALL run a
`docker ... prune`. The guide SHALL say to check `env | grep -E '^(LADO|COMPOSE)_'` and `unset` what the
shell sets, since a shell's variable beats `.env`.

README's Install and docs/install.md's opening SHALL present the two ways to install,
Docker first and recommended, then PyPI, each with what it is for and what it needs; PyPI's
differences by system (macOS, Linux, Windows inside WSL2) SHALL be named there too.

#### Scenario: Two ways, Docker first
- **WHEN** `tests/test_docker.py` reads README's Install and docs/install.md's opening
- **THEN** each names Docker as recommended before PyPI, and docs/install.md's `## Docker`
  comes before its systems' sections

#### Scenario: The commands agree
- **WHEN** `tests/test_docker.py` reads the guide's code blocks and the header
- **THEN** the guide's start commands, its update (`docker compose up -d`) and its way
  back (`way_back()`) are the header's

#### Scenario: Removal by name
- **WHEN** the test reads the guide's removal
- **THEN** it runs `docker compose down` and `docker volume rm` of the project's own
  `home` volume, and README.md, docs/*.md and docker/ hold no `prune` (docs/research/ and
  docs/superpowers/ are records, not read as instructions)

## MODIFIED Requirements

### Requirement: The host's ssh agent reaches the agents without root's group

`docker/compose.yaml` SHALL bind the path that `LADO_SSH_AGENT` names (default
`/dev/null`: no ssh agent) at `/run/lado/ssh-agent.sock`, refusing to start when that
path does not exist. When that path in the container is a socket, the image SHALL set
`SSH_AUTH_SOCK=/run/lado/ssh-agent.sock` for every login shell, so for every agent, and
for the UI server, whose Clone from URL and branch listing run git over ssh: one rule,
`docker/ssh-agent-env.sh` at `/etc/profile.d/lado-ssh-agent.sh`, which the entrypoint
sources before the command, after the step below.

At every start, the entrypoint SHALL check, as `lado`, whether `lado` can use the socket:
- when it cannot and the socket belongs to uid 0, it SHALL run through `sudo` the image's
  program `/usr/local/bin/lado-ssh-agent-socket`, which takes no argument and keeps no
  variable of its caller (no `SETENV`). That program SHALL give that one path, only when
  it is a socket that is no symbolic link and belongs to uid 0, to `lado`'s uid, keeping
  its group.
- when `lado` still cannot use it, `docker logs` SHALL get one line, `lado: warning: lado
  (uid <uid>) cannot use the ssh agent socket of uid <owner>: <reason>`, and the server
  SHALL start.

The container SHALL need no `group_add`. The headers SHALL give `LADO_SSH_AGENT` for a
Mac (`/run/host-services/ssh-auth.sock`, Docker Desktop's) and for Linux (the host's
`$SSH_AUTH_SOCK`), and SHALL say that every agent of the container may then use the
host's keys.

#### Scenario: Docker Desktop's root-owned socket
- **WHEN** an ssh agent holding a test key listens on a socket owned by uid 0 at
  `/run/lado/ssh-agent.sock` (made by another container on a shared volume) and LADO's
  container starts, or restarts
- **THEN** `ssh-add -l` in an agent's login shell lists the test key, the UI server's
  process has `SSH_AUTH_SOCK=/run/lado/ssh-agent.sock`, and `id -G` of `lado` has no 0

#### Scenario: A Linux host's socket of the projects' owner
- **WHEN** the socket belongs to the uid of the projects' owner, which `lado` takes
- **THEN** `ssh-add -l` in an agent's login shell lists the key, and the socket's owner is
  unchanged

#### Scenario: No ssh agent
- **WHEN** `LADO_SSH_AGENT` is not set
- **THEN** agents and the UI server have no `SSH_AUTH_SOCK` from the image, and `docker
  logs` has no ssh line

#### Scenario: The rule gives no root
- **WHEN** an agent runs `sudo -n /usr/local/bin/lado-ssh-agent-socket` with any variable
  or argument
- **THEN** it can at most give that socket to `lado`, and `sudo -n true` fails
