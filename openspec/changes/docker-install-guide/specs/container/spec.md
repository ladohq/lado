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
  `docker/entrypoint.sh`, `docker/ssh-agent-socket.sh` and `docker/ssh_known_hosts`

### Requirement: The install guide leads with compose and runs the headers' commands

docs/install.md SHALL have a section `Docker` that leads with compose: get `compose.yaml`,
write `.env`, make `secrets/`, start, open the UI, log in to the agent CLIs, ssh, update
and go back, a second LADO, the sessions, removal and the pitfalls; README's Install SHALL
link to it. Its start, update and way-back commands SHALL be exactly those of
`docker/compose.yaml`'s header, which the container tests run. Its `.env` SHALL name every
variable compose reads but `LADO_IMAGE` and `LADO_SECRETS`. It SHALL remove only its own
container and volume, by name, and nothing in the guide or the headers SHALL run a
`docker ... prune`. The guide SHALL say to check `env | grep LADO` and `unset` what the
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
